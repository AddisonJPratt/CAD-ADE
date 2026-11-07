"""A proposal session can stop an active preview and resume it without losing events."""
import threading
import unittest
from engine.proposal_session import ProposalSession


class ProposalSessionTest(unittest.TestCase):
    def test_interrupt_and_resume_active_preview(self):
        started = threading.Event()
        attempts = []
        def work(side, cancel):
            attempts.append(side)
            if len(attempts) == 1:
                started.set()
                self.assertTrue(cancel.wait(5))
                return {'ok': False, 'interrupted': True}
            return {'ok': True, 'parts': [{'stl': side, 'bbox': {'size': [1, 2, 3]}}]}
        session = ProposalSession('id', work)
        session.start()
        self.assertTrue(started.wait(5))
        session.interrupt()
        self.assertTrue(session.wait_for('interrupted', 5))
        session.resume()
        self.assertTrue(session.wait_for('ready', 5))
        self.assertEqual(attempts, ['before', 'before', 'after'])
        self.assertEqual([event['type'] for event in session.events],
                         ['started', 'interrupted', 'resumed', 'preview', 'preview', 'ready'])


if __name__ == '__main__':
    unittest.main()
