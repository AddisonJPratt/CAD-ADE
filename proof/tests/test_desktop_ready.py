"""Desktop handshake must identify the exact server child and preserve host checks."""
import http.client
import importlib.util
import os
from pathlib import Path
import threading
import tempfile
import json
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('proof_desktop_server', Path(__file__).resolve().parents[1] / 'server.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class DesktopReadyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), p.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, host):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('GET', '/__desktop_ready', headers={'Host': host})
        response = conn.getresponse()
        result = (response.status, response.read())
        conn.close()
        return result

    def test_recovery_marks_only_interrupted_valid_records_failed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, 'DATA', Path(tmp)):
            for ident, state in [('a' * 32, 'building'), ('b' * 32, 'passed'), ('invalid', 'building')]:
                dest = Path(tmp) / 'makes' / ident
                dest.mkdir(parents=True)
                (dest / 'make.json').write_text(json.dumps({'status': state}))
            p.recover_interrupted_makes()
            def status(ident):
                return json.loads((Path(tmp) / 'makes' / ident / 'make.json').read_text())['status']
            self.assertEqual(status('a' * 32), 'failed')
            self.assertEqual(status('b' * 32), 'passed')
            self.assertEqual(status('invalid'), 'building')

    def test_ready_is_opt_in_and_identifies_the_child(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.request('127.0.0.1:8766')[0], 404)
        with patch.dict(os.environ, {'MAGIC_PROOF_DESKTOP_TOKEN': 'test-nonce'}, clear=True):
            self.assertEqual(self.request('127.0.0.1:8766'), (200, b'test-nonce'))
            self.assertEqual(self.request('attacker.example')[0], 403)


if __name__ == '__main__':
    unittest.main()
