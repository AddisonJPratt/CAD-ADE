"""Exercise asynchronous proposal lifecycle without binding a server socket."""
import json
import tempfile
import unittest
from pathlib import Path

from engine.api import Engine, Handler
from engine.printers import PROFILE, select_printer
from engine.versions import create_project, list_versions, save_version


class ProposalLifecycleTest(unittest.TestCase):
    def test_interrupts_running_preview_and_can_reject_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            project = create_project(Path(tmp) / 'project', root / 'tests/fixtures/hang.py')
            handler = Handler.__new__(Handler)
            handler.engine = Engine()
            status, pending = handler.post_proposal({'project': str(project), 'message': 'size 24'})
            self.assertEqual(status, 202)
            session = handler.engine.proposals[pending['id']]['session']
            handler.control_agent(pending['id'], 'interrupt')
            self.assertTrue(session.wait_for('interrupted', 10))
            status, _ = handler.reject_proposal(pending['id'])
            self.assertEqual(status, 200)
            self.assertTrue(session.wait_for('rejected', 5))
            self.assertEqual(len(list_versions(project)), 1)
            handler.engine.artifacts.cleanup()

    def test_proposal_previews_and_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            project = create_project(Path(tmp) / 'project', root / 'tests/fixtures/good_two_parts.py')
            handler = Handler.__new__(Handler)
            handler.engine = Engine()
            status, pending = handler.post_proposal({'project': str(project), 'message': 'size 24'})
            self.assertEqual(status, 202)
            proposal = handler.engine.proposals[pending['id']]
            session = proposal['session']
            self.assertTrue(session.wait_for('ready', 120), session.error)
            ready = handler.proposal_summary(proposal)
            self.assertEqual(ready['changes'][0]['new'], 24)
            self.assertEqual(len(ready['previews']['before']), 2)
            status, accepted = handler.accept_proposal(pending['id'], {'wait': True, 'samples': 5})
            self.assertEqual(status, 200)
            self.assertTrue(accepted['run']['verdict']['pass'])
            self.assertEqual(len(list_versions(project)), 2)
            handler.engine.artifacts.cleanup()

    def test_preview_uses_the_project_material_clearances(self):
        """A PETG project's preview is built with PETG fits, as its accepted run is."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'sleeve.py'
            source.write_text('''from build123d import Align, Box
from library import standard_parts

PARAMS = {"size": (20.0, 10.0, 30.0)}


def build(size):
    clearance = standard_parts()["fits"]["sliding"]
    return Box(size + 2 * clearance, size, size, align=(Align.CENTER, Align.CENTER, Align.MIN))
''')
            project = create_project(Path(tmp) / 'project', source)
            # The project-local table holds a stale sliding fit; the selected material must win.
            table = project / 'library/standard_parts.json'
            data = json.loads(table.read_text())
            data['fits']['sliding'] = 1.0
            table.write_text(json.dumps(data))
            select_printer(project, PROFILE['id'], 'PETG')
            save_version(project, 'PETG with a stale library fit')
            petg_sliding = PROFILE['materials']['PETG']['fit_clearance_mm_per_side']['sliding']
            handler = Handler.__new__(Handler)
            handler.engine = Engine()
            status, pending = handler.post_proposal({'project': str(project), 'message': 'size 24'})
            self.assertEqual(status, 202)
            proposal = handler.engine.proposals[pending['id']]
            self.assertTrue(proposal['session'].wait_for('ready', 120), proposal['session'].error)
            dimensions = handler.proposal_summary(proposal)['preview_dimensions']
            self.assertAlmostEqual(dimensions['before'][0][0], 20 + 2 * petg_sliding, places=2)
            self.assertAlmostEqual(dimensions['after'][0][0], 24 + 2 * petg_sliding, places=2)
            status, accepted = handler.accept_proposal(pending['id'], {'wait': True, 'samples': 5})
            self.assertEqual(status, 200)
            report = json.loads((project / 'outputs/sleeve/report.json').read_text())
            metrics = next(iter(report['printability'].values()))['metrics']
            self.assertAlmostEqual(metrics['extents'][0], dimensions['after'][0][0], places=2)
            handler.engine.artifacts.cleanup()


if __name__ == '__main__':
    unittest.main()
