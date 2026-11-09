"""The designer role (#61) at the app seam: a brief card in, a design that passes every gate out.

The writer is a scripted fake (`ScriptedFakeDesigner`): each attempt writes a canned source, so the
loop, the gates, the event stream, interrupt and accept are tested without a language model.
The real Claude Code writer is exercised against the stream-json CLI fixture in
tests/test_claude_designer.py and for real in evals/run_designer.py.
"""
import tempfile
import threading
import unittest
from pathlib import Path

from engine.api import Engine, Handler
from engine.designer import DesignLoop, ScriptedFakeDesigner
from engine.projects import ProjectError
from engine.versions import create_project_from_brief, list_versions, unsaved

BRIEF = """name: block
function: >
  A test block whose one hard dimension is its width along X.
hard_dimensions:
  width: {width}
measures:
  width: {{probe: bbox_x}}
interfaces: []
soft_preferences: []
assumptions: []
params:
  width: {{value: {width}, min: {low}, max: {high}, unit: mm, intent: Block width}}
  height: {{value: 10.0, min: 8.0, max: 12.0, unit: mm, intent: Block height}}
"""

GOOD = '''"""A block sized by the brief."""
from build123d import Align, Box

PARAMS = {{
    "width": ({width}, {low}, {high}),   # mm, {low}..{high}: block width along X
    "height": (10.0, 8.0, 12.0),         # mm, 8..12: block height
}}


def build(width, height):
    block = Box(width, height, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    block.label = "block"
    return block
'''

HARDCODED = '''"""Fails gate 1: a dimension that is not in PARAMS."""
from build123d import Box

PARAMS = {"width": (20.0, 10.0, 30.0)}


def build(width):
    return Box(width, 13, 13)
'''


def brief(width=20.0, low=10.0, high=30.0):
    return BRIEF.format(width=width, low=low, high=high)


def good(width=20.0, low=10.0, high=30.0):
    return GOOD.format(width=width, low=low, high=high)


def snapshot(project):
    return {str(p.relative_to(project)): p.read_bytes() for p in Path(project).rglob('*')
            if p.is_file() and '.git' not in p.parts and '.magic' not in p.parts}


class DesignerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def project(self, text=None):
        card = Path(self.tmp.name) / 'block.yaml'
        card.write_text(text or brief())
        return create_project_from_brief(Path(self.tmp.name) / 'project', card)

    def handler(self, steps):
        handler = Handler.__new__(Handler)
        self.writer = ScriptedFakeDesigner(steps)
        handler.engine = Engine(designer=DesignLoop(self.writer))
        self.addCleanup(handler.engine.artifacts.cleanup)
        self.addCleanup(handler.engine.close)
        return handler

    def propose(self, handler, project, **design):
        status, pending = handler.post_proposal({'project': str(project),
                                                 'design': {'brief': 'block', 'samples': 6, **design}})
        self.assertEqual(status, 202)
        return pending, handler.engine.proposals[pending['id']]

    def test_a_brief_only_project_is_version_one_with_no_design(self):
        project = self.project()
        self.assertEqual(len(list_versions(project)), 1)
        self.assertFalse((project / 'designs').exists() and any((project / 'designs').glob('*.py')))
        self.assertTrue((project / 'briefs/block.yaml').is_file())
        self.assertTrue((project / 'library/__init__.py').is_file())

    def test_iterates_on_gate_feedback_then_accept_saves_a_passing_version(self):
        project = self.project()
        handler = self.handler([{'designs/block.py': HARDCODED}, {'designs/block.py': good()}])
        pending, proposal = self.propose(handler, project, attempts=3)
        session = proposal['session']
        self.assertTrue(session.wait_for('ready', 400), session.error)
        kinds = [e['type'] for e in session.events]
        self.assertEqual(kinds.count('attempt_started'), 2)
        self.assertIn('gate_started', kinds)
        self.assertIn('gate_finished', kinds)
        reports = [e for e in session.events if e['type'] == 'gate_report']
        self.assertFalse(reports[0]['pass'])
        self.assertEqual(reports[0]['mode'], 'quick')
        self.assertEqual(reports[-1], {**reports[-1], 'pass': True, 'mode': 'full'})
        gates = {g['name']: g['status'] for g in reports[-1]['designs'][0]['gates']}
        self.assertEqual(gates['Sweep'], 'PASS')
        # The second attempt was told why the first failed.
        self.assertIn('hard-coded', self.writer.feedback[1])
        summary = handler.proposal_summary(proposal)
        self.assertEqual(summary['kind'], 'design')
        self.assertEqual(summary['files'], ['designs/block.py'])
        self.assertTrue(summary['gate_report']['pass'])
        self.assertEqual(summary['previews'].get('before', []), [])   # nothing existed before
        self.assertEqual(len(summary['previews']['after']), 1)
        self.assertFalse((project / 'designs/block.py').exists())    # held until accepted
        status, accepted = handler.accept_proposal(pending['id'], {'wait': True, 'samples': 6})
        self.assertEqual(status, 200)
        self.assertTrue(accepted['run']['verdict']['pass'])
        versions = list_versions(project)
        self.assertEqual(len(versions), 2)
        self.assertIn('block', versions[0]['message'])
        self.assertEqual((project / 'designs/block.py').read_text(), good())
        self.assertEqual(unsaved(project), [])

    def test_an_unsatisfiable_brief_ends_within_budget_with_no_version(self):
        project = self.project(brief(width=300.0, low=280.0, high=320.0))   # wider than the 256 mm bed
        before = snapshot(project)
        handler = self.handler([{'designs/block.py': good(300.0, 280.0, 320.0)}] * 5)
        _, proposal = self.propose(handler, project, attempts=2)
        session = proposal['session']
        self.assertTrue(session.wait_for('error', 400), session.state)
        self.assertIn('could not reach a passing design', session.error)
        self.assertIn('2 attempts', session.error)
        self.assertIn('3 Printability', session.error)       # the last gate report, not a silent partial
        self.assertEqual(len(self.writer.feedback), 2)
        self.assertEqual(len(list_versions(project)), 1)
        self.assertEqual(snapshot(project), before)

    def test_the_wall_time_budget_ends_the_loop(self):
        project = self.project()
        def slow(session):   # an attempt that takes longer than the whole wall-time budget
            threading.Event().wait(.3)
            (Path(session['workspace']) / 'designs').mkdir(exist_ok=True)
            (Path(session['workspace']) / 'designs/block.py').write_text(HARDCODED)
        handler = self.handler([slow] * 5)
        _, proposal = self.propose(handler, project, attempts=5, seconds=0.2)
        session = proposal['session']
        self.assertTrue(session.wait_for('error', 120), session.state)
        self.assertIn('could not reach a passing design', session.error)
        self.assertEqual(len(self.writer.feedback), 1)

    def test_edits_outside_designs_are_refused_and_reverted(self):
        project = self.project()
        handler = self.handler([{'briefs/block.yaml': brief(width=25.0), 'designs/block.py': good()},
                                {'designs/block.py': good()}])
        _, proposal = self.propose(handler, project, attempts=3)
        session = proposal['session']
        self.assertTrue(session.wait_for('ready', 400), session.error)
        refused = [e for e in session.events if e['type'] == 'refused_edit']
        self.assertEqual(refused[0]['files'], ['briefs/block.yaml'])
        self.assertIn('briefs/block.yaml', self.writer.feedback[1])
        self.assertEqual(handler.proposal_summary(proposal)['files'], ['designs/block.py'])
        draft = Path(proposal['workspace'])
        self.assertEqual((draft / 'briefs/block.yaml').read_text(), brief())

    def test_interrupt_leaves_the_project_and_versions_untouched(self):
        project = self.project()
        before = snapshot(project)
        writing = threading.Event()
        def blocked(session):
            (Path(session['workspace']) / 'designs').mkdir(exist_ok=True)
            (Path(session['workspace']) / 'designs/block.py').write_text('# half written')
            writing.set()
            while not session['interrupted']:
                threading.Event().wait(.05)
        handler = self.handler([blocked, {'designs/block.py': good()}])
        pending, proposal = self.propose(handler, project, attempts=3)
        session = proposal['session']
        self.assertTrue(writing.wait(30))
        handler.control_agent(pending['id'], 'interrupt')
        self.assertTrue(session.wait_for('interrupted', 30), session.state)
        self.assertEqual(snapshot(project), before)
        self.assertEqual(len(list_versions(project)), 1)
        # The half-written attempt is rolled back in the draft, and resuming redoes it.
        self.assertFalse((Path(proposal['workspace']) / 'designs/block.py').exists())
        handler.control_agent(pending['id'], 'resume')
        self.assertTrue(session.wait_for('ready', 400), session.error)
        handler.reject_proposal(pending['id'])
        self.assertEqual(snapshot(project), before)
        self.assertEqual(len(list_versions(project)), 1)

    def test_refuses_a_missing_or_invalid_brief_before_starting(self):
        project = self.project()
        handler = self.handler([])
        with self.assertRaises(ProjectError):
            handler.post_proposal({'project': str(project), 'design': {'brief': 'nothing'}})
        (project / 'briefs/broken.yaml').write_text('name: broken\n')
        from engine.versions import save_version
        save_version(project, 'A broken brief')
        with self.assertRaises(ProjectError):
            handler.post_proposal({'project': str(project), 'design': {'brief': 'broken'}})
        with self.assertRaises(ProjectError):
            handler.post_proposal({'project': str(project), 'design': {'brief': 'block', 'attempts': 0}})


if __name__ == '__main__':
    unittest.main()
