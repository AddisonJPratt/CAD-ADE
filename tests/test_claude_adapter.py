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


class ClaudeAdapterContractTest(unittest.TestCase):
    """Failure paths and the credential/interface contract, against the local CLI fixture."""
    request = parameter_cases.ParameterApiTest.request
    tearDown = parameter_cases.ParameterApiTest.tearDown

    def setUp(self):
        import tempfile
        import threading
        from pathlib import Path
        from engine.claude_agent import ClaudeCodeAgent
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'project', ROOT / 'tests/fixtures/good_two_parts.py')
        self.argv_file = Path(self.tmp.name) / 'argv.json'
        self.runtime = ClaudeCodeAgent(command=[sys.executable, str(ROOT / 'tests/fixtures/claude_stream.py'),
                                                '--argv-file', str(self.argv_file)])
        self.server = make_server(port=0, engine=Engine(agent=self.runtime))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def snapshot(self):
        return {str(p.relative_to(self.project)): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}

    def propose_error(self, *flags, message='increase size'):
        self.runtime.command.extend(flags)
        before = self.snapshot()
        status, pending = self.request('POST', '/proposals', {'project': str(self.project), 'message': message})
        self.assertEqual(status, 202, pending)
        state = ClaudeAdapterTest.wait_state(self, pending['id'], ('ready', 'error'))
        self.assertEqual(state['state'], 'error')
        self.assertEqual(self.snapshot(), before, 'a failed proposal must leave the project unchanged')
        return state['error']

    def test_adapter_interface_is_the_four_method_seam(self):
        from engine.agents import AgentAdapter
        from engine.claude_agent import ClaudeCodeAgent
        self.assertEqual(AgentAdapter.__abstractmethods__, frozenset({'start', 'stream_events', 'interrupt', 'resume'}))
        self.assertTrue(issubclass(ClaudeCodeAgent, AgentAdapter))
        public = {n for n in vars(ClaudeCodeAgent) if not n.startswith('_') and callable(getattr(ClaudeCodeAgent, n))}
        self.assertEqual(public, {'start', 'stream_events', 'interrupt', 'resume'})

    def test_uses_existing_cli_login_without_passing_or_writing_credentials(self):
        import json as json_
        _, pending = self.request('POST', '/proposals', {'project': str(self.project), 'message': 'increase size'})
        self.assertEqual(ClaudeAdapterTest.wait_state(self, pending['id'], ('ready', 'error'))['state'], 'ready')
        recorded = json_.loads(self.argv_file.read_text())
        argv = recorded['argv']
        # Auth stays with the CLI: no key, token or settings override on the command line, and the
        # child sees exactly the auth environment the user already had, nothing the app injected.
        self.assertFalse([a for a in argv if any(w in a.lower() for w in ('api-key', 'apikey', 'token', '--settings'))], argv)
        expected = {k: v for k, v in os.environ.items() if k.startswith(('ANTHROPIC', 'CLAUDE'))}
        self.assertEqual(recorded['auth_env'], expected)
        # Headless, no persisted CLI session, read-only built-in tools, only the two CAD MCP servers.
        for flag in ('-p', '--no-session-persistence', '--strict-mcp-config'):
            self.assertIn(flag, argv)
        tools = argv[argv.index('--tools') + 1].split(',')
        self.assertEqual(sorted(tools), ['Glob', 'Grep', 'Read'])
        servers = json_.loads(argv[argv.index('--mcp-config') + 1])['mcpServers']
        self.assertEqual(sorted(servers), ['build123d', 'magic-cad'])
        self.assertIn(str(ROOT / '.claude/skills'), argv)
        self.assertEqual(self.request('POST', f"/proposals/{pending['id']}/reject", {})[0], 200)

    def test_missing_cli_reports_install_and_login(self):
        self.runtime.command[:] = ['/nonexistent/claude']
        status, result = self.request('POST', '/proposals', {'project': str(self.project), 'message': 'increase size'})
        self.assertEqual(status, 400, result)
        self.assertIn('claude auth login', result['error'])

    def test_unavailable_cad_mcp_server_stops_the_proposal(self):
        self.assertIn('MCP services are unavailable', self.propose_error('--mcp-down'))

    def test_cli_error_result_points_at_login_without_changing_source(self):
        self.assertIn('claude auth status', self.propose_error('--cli-error'))

    def test_result_without_structured_edit_is_an_error(self):
        self.assertIn('no structured parameter edit', self.propose_error('--no-structured'))
