"""Real process transport at the engine seam, with a local stream-json CLI fixture."""
import sys
import os
import time
import unittest

from engine.api import Engine, make_server
from engine.versions import create_project
from tests import test_parameters as parameter_cases
ROOT = parameter_cases.ROOT


class ClaudeAdapterTest(unittest.TestCase):
    request = parameter_cases.ParameterApiTest.request
    tearDown = parameter_cases.ParameterApiTest.tearDown
    def setUp(self):
        import tempfile
        import threading
        from pathlib import Path
        from engine.claude_agent import ClaudeCodeAgent
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'project', ROOT / 'tests/fixtures/good_two_parts.py')
        self.pid_file = Path(self.tmp.name) / 'runtime.pid'
        runtime = ClaudeCodeAgent(command=[sys.executable, str(ROOT / 'tests/fixtures/claude_stream.py'), '--pid-file', str(self.pid_file)])
        self.runtime = runtime
        self.server = make_server(port=0, engine=Engine(agent=runtime))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def wait_state(self, ident, states):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            _, result = self.request('GET', '/proposals/' + ident)
            if result['state'] in states:
                return result
            time.sleep(.1)
        self.fail('proposal did not reach ' + repr(states))

    def test_cli_proposal_is_held_until_accept_and_gates_save_version(self):
        status, pending = self.request('POST','/proposals', {'project':str(self.project), 'message':'increase size'})
        self.assertEqual(status,202)
        ready = self.wait_state(pending['id'], ('ready','error'))
        self.assertEqual(ready['state'],'ready',ready.get('error'))
        self.assertEqual(ready['changes'][0]['new'],24)
        self.assertIn('20.0', (self.project / 'designs/good_two_parts.py').read_text())
        status, accepted = self.request('POST',f"/proposals/{pending['id']}/accept",{'wait':True,'samples':5})
        self.assertEqual(status,200)
        self.assertTrue(accepted['run']['verdict']['pass'])

    def test_interrupt_and_resume_leave_original_project_unchanged(self):
        original = (self.project / 'designs/good_two_parts.py').read_bytes()
        _, pending = self.request('POST','/proposals', {'project':str(self.project), 'message':'slow request'})
        deadline = time.monotonic() + 10
        while not self.pid_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        pid = int(self.pid_file.read_text())
        self.assertEqual(self.request('POST',f"/proposals/{pending['id']}/interrupt",{})[0],200)
        self.assertEqual(self.wait_state(pending['id'],('interrupted','error'))['state'],'interrupted')
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertEqual(self.request('POST',f"/proposals/{pending['id']}/resume",{})[0],200)
        deadline = time.monotonic() + 10
        while int(self.pid_file.read_text()) == pid and time.monotonic() < deadline:
            time.sleep(.05)
        resumed_pid = int(self.pid_file.read_text())
        self.assertNotEqual(resumed_pid, pid)
        self.assertEqual(self.request('POST',f"/proposals/{pending['id']}/reject",{})[0],200)
        with self.assertRaises(ProcessLookupError):
            os.kill(resumed_pid, 0)
        self.assertEqual((self.project / 'designs/good_two_parts.py').read_bytes(), original)

    def test_timeout_returns_error_without_changing_source(self):
        self.runtime.timeout = .2
        original = (self.project / 'designs/good_two_parts.py').read_bytes()
        _, pending = self.request('POST','/proposals', {'project':str(self.project), 'message':'slow request'})
        state = self.wait_state(pending['id'], ('error',))
        self.assertIn('timed out', state['error'])
        self.assertEqual((self.project / 'designs/good_two_parts.py').read_bytes(),original)

    def test_unsupported_request_is_not_replaced_with_an_invented_edit(self):
        original = (self.project / 'designs/good_two_parts.py').read_bytes()
        _, pending = self.request('POST','/proposals', {'project':str(self.project), 'message':'unsupported request'})
        state = self.wait_state(pending['id'], ('error',))
        self.assertIn('beyond M0', state['error'])
        self.assertEqual((self.project / 'designs/good_two_parts.py').read_bytes(),original)

    def test_interrupt_while_initial_prompt_is_blocked_remains_resumable(self):
        self.runtime.command.append('--pause-before-read')
        _, pending = self.request('POST','/proposals', {
            'project':str(self.project), 'message':'slow request' + ' ' * 1_000_000})
        deadline = time.monotonic() + 10
        while not self.pid_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertTrue(self.pid_file.exists())
        self.assertEqual(self.request('POST',f"/proposals/{pending['id']}/interrupt",{})[0],200)
        result = self.wait_state(pending['id'], ('interrupted','error'))
        self.assertEqual(result['state'],'interrupted',result.get('error'))
        self.assertEqual(self.request('POST',f"/proposals/{pending['id']}/resume",{})[0],200)
        self.assertEqual(self.request('POST',f"/proposals/{pending['id']}/reject",{})[0],200)
