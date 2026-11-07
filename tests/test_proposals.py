"""Proposal behaviour at the engine HTTP boundary."""
import json
import tempfile
import time
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from engine.api import make_server
from engine.versions import create_project


class ProposalTest(unittest.TestCase):
    def test_rejecting_proposal_leaves_project_and_versions_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            project = create_project(Path(tmp) / 'project', root / 'tests/fixtures/good_two_parts.py')
            server = make_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'

            def request(method, path, body=None):
                data = json.dumps(body).encode() if body is not None else None
                req = urllib.request.Request(base + path, data=data, method=method,
                                             headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(req, timeout=120) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as error:
                    return error.code, json.load(error)

            try:
                design = project / 'designs/good_two_parts.py'
                before = design.read_bytes()
                status, proposal = request('POST', '/proposals', {
                    'project': str(project), 'message': 'Make the size 24 mm',
                    'selection': None,
                })
                self.assertEqual(status, 202)
                deadline = time.monotonic() + 120
                while proposal['state'] not in ('ready', 'error') and time.monotonic() < deadline:
                    time.sleep(0.2)
                    _, proposal = request('GET', f"/proposals/{proposal['id']}")
                self.assertEqual(proposal['state'], 'ready', proposal.get('error'))
                self.assertEqual(proposal['changes'][0]['old'], 20.0)
                self.assertEqual(proposal['changes'][0]['new'], 24.0)
                with urllib.request.urlopen(base + proposal['previews']['before'][0]) as response:
                    before_mesh = response.read()
                with urllib.request.urlopen(base + proposal['previews']['after'][0]) as response:
                    after_mesh = response.read()
                self.assertGreater(len(before_mesh), 100)
                self.assertNotEqual(before_mesh, after_mesh)
                status, _ = request('POST', f"/proposals/{proposal['id']}/reject", {})
                self.assertEqual(status, 200)
                self.assertEqual(design.read_bytes(), before)
                status, second = request('POST', '/proposals', {'project': str(project), 'message': 'size 24'})
                self.assertEqual(status, 202)
                deadline = time.monotonic() + 120
                while second['state'] not in ('ready', 'error') and time.monotonic() < deadline:
                    time.sleep(0.2)
                    _, second = request('GET', f"/proposals/{second['id']}")
                self.assertEqual(second['state'], 'ready', second.get('error'))
                status, _ = request('POST', f"/proposals/{second['id']}/accept", {'timeout': 'bad'})
                self.assertEqual(status, 400)
                self.assertEqual(design.read_bytes(), before)
                status, _ = request('POST', f"/proposals/{second['id']}/accept", {'samples': 1})
                self.assertEqual(status, 400)
                self.assertEqual(design.read_bytes(), before)
                status, accepted = request('POST', f"/proposals/{second['id']}/accept", {'wait': True, 'samples': 5})
                self.assertEqual(status, 200)
                self.assertTrue(accepted['run']['verdict']['pass'])
                self.assertIn(b'24.0', design.read_bytes())
                from engine.versions import list_versions
                self.assertEqual(len(list_versions(project)), 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
