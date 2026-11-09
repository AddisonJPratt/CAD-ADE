"""The Claude Code designer writer (#61) over a real process, with a local stream-json CLI fixture."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from engine.api import Engine, Handler
from engine.claude_designer import ClaudeCodeDesigner
from engine.designer import DesignLoop
from engine.versions import create_project_from_brief, list_versions
from tests.test_designer import brief, snapshot

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/claude_designer_stream.py'


class ClaudeDesignerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        card = Path(self.tmp.name) / 'block.yaml'
        card.write_text(brief())
        self.project = create_project_from_brief(Path(self.tmp.name) / 'project', card)
        self.log = Path(self.tmp.name) / 'runs.jsonl'
        self.pid = Path(self.tmp.name) / 'cli.pid'

    def handler(self, *flags):
        handler = Handler.__new__(Handler)
        command = [sys.executable, str(FIXTURE), '--log', str(self.log), '--pid-file', str(self.pid), *flags]
        handler.engine = Engine(designer=DesignLoop(ClaudeCodeDesigner(command=command)))
        self.addCleanup(handler.engine.artifacts.cleanup)
        self.addCleanup(handler.engine.close)
        return handler

    def runs(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_writes_in_the_draft_with_scoped_permissions_and_learns_from_the_gates(self):
        handler = self.handler()
        _, pending = handler.post_proposal({'project': str(self.project),
                                            'design': {'brief': 'block', 'attempts': 3, 'samples': 6}})
        proposal = handler.engine.proposals[pending['id']]
        self.assertTrue(proposal['session'].wait_for('ready', 400), proposal['session'].error)
        runs = self.runs()
        self.assertEqual(len(runs), 2)
        first, second = runs
        self.assertEqual(Path(first['cwd']).resolve(), Path(proposal['workspace']).resolve())  # never the project
        argv = first['argv']
        allowed = argv[argv.index('--allowedTools') + 1].split(',')
        self.assertIn('Edit(designs/**)', allowed)
        self.assertIn('Edit(assembly.py)', allowed)
        self.assertNotIn('Edit', allowed)               # no unscoped writes
        self.assertTrue(any(a.startswith('Bash(') and 'magic.py check' in a for a in allowed))
        hidden = argv[argv.index('--disallowedTools') + 1]
        self.assertIn(f'Read(/{ROOT}/designs/block.py)', hidden)   # the eval can't copy the answer
        self.assertIn('width: 20.0', first['prompt'])               # the brief card
        self.assertIn('clearances_mm_per_side', first['prompt'])
        self.assertIn('magic-kernel-pitfalls', first['prompt'])
        self.assertIn('"last_gate_report": null', first['prompt'])
        self.assertIn('hard-coded', second['prompt'])               # the gate report came back
        summary = handler.proposal_summary(proposal)
        self.assertEqual(summary['files'], ['designs/block.py'])
        kinds = [e['type'] for e in proposal['session'].events]
        self.assertIn('usage', kinds)
        self.assertTrue(any(e.get('message', '').startswith('Using Write') for e in proposal['session'].events))

    def test_interrupt_stops_the_cli_and_leaves_the_project_unchanged(self):
        before = snapshot(self.project)
        handler = self.handler('--slow')
        _, pending = handler.post_proposal({'project': str(self.project), 'design': {'brief': 'block'}})
        deadline = time.monotonic() + 20
        while not self.pid.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        pid = int(self.pid.read_text())
        handler.control_agent(pending['id'], 'interrupt')
        session = handler.engine.proposals[pending['id']]['session']
        self.assertTrue(session.wait_for('interrupted', 20), session.state)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        handler.reject_proposal(pending['id'])
        self.assertEqual(snapshot(self.project), before)
        self.assertEqual(len(list_versions(self.project)), 1)


if __name__ == '__main__':
    unittest.main()
