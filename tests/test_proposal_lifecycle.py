"""Exercise asynchronous proposal lifecycle without binding a server socket."""
import tempfile
import unittest
from pathlib import Path

from engine.api import Engine, Handler
from engine.versions import create_project, list_versions


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


if __name__ == '__main__':
    unittest.main()
