"""Texture requests on a selection (#52): parse, source edit, and the proposal at the HTTP boundary.

    .venv/bin/python -m unittest tests.test_texture_request
"""
import ast
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from engine.api import make_server
from engine.projects import ProjectError
from engine.texture_request import add_params, selector, texture_kind, texture_request
from engine.versions import create_project, list_versions
from harness.lint import lint_design

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/named_features.py'


def floor_pick():
    """The lid pocket floor of named_features.py, as Studio sends a pick of it."""
    return {'instance': 'plate', 'kind': 'face', 'feature': 'lid pocket', 'parameters': {'pocket_depth': 3.0},
            'face': 11, 'description': 'a flat face on the "lid pocket" feature of body "plate" facing up (+Z)',
            'point': [0.4, -0.2, 9.0], 'normal': [0, 0, 1], 'centroid': [0, 0, 9], 'area': 324.0, 'flat': True,
            'note': None, 'locked': False}


class ParseTest(unittest.TestCase):
    def test_texture_words(self):
        self.assertEqual(texture_kind('Add knurling to this face'), 'knurl')
        self.assertEqual(texture_kind('add a diamond texture here'), 'diamond')
        self.assertEqual(texture_kind('put hex studs on it'), 'hex')
        self.assertEqual(texture_kind('apply ribbing'), 'ribbing')
        self.assertIsNone(texture_kind('size 24'))
        self.assertIsNone(texture_kind('make the ribs thicker 3'))   # a parameter edit, not a texture
        self.assertFalse(texture_request('Add knurling to this face', None))
        self.assertTrue(texture_request('Add knurling to this face', {'design': 'x.py', 'picks': [floor_pick()]}))

    def test_selector_from_a_pick(self):
        self.assertEqual(selector(floor_pick())[0], 'facing="+Z", feature=\'lid pocket\'')
        side = dict(floor_pick(), feature=None, normal=[0, -1, 0])
        self.assertEqual(selector(side)[0], 'facing="-Y"')
        curved = dict(floor_pick(), feature=None, flat=False, normal=[0.6, 0.8, 0.0])
        self.assertEqual(selector(curved)[0], 'kind="cylinder"')
        with self.assertRaises(ProjectError):
            selector(dict(floor_pick(), normal=[0, 0.6, 0.8]))
        with self.assertRaises(ProjectError):
            selector(dict(floor_pick(), flat=False, normal=[0, 0.6, 0.8]))

    def test_add_params_keeps_the_literal_and_adds_a_missing_comma(self):
        source = 'PARAMS = {\n    "a": (1.0, 0.0, 2.0)  # mm, a\n}\n'
        edited = add_params(source, [('b', (2.0, 1.0, 3.0), 'mm, b')])
        params = ast.literal_eval(next(n.value for n in ast.parse(edited).body if isinstance(n, ast.Assign)))
        self.assertEqual(params, {'a': (1.0, 0.0, 2.0), 'b': (2.0, 1.0, 3.0)})
        self.assertIn('# mm, b', edited)


class TextureProposalTest(unittest.TestCase):
    def test_add_knurling_to_a_picked_face_previews_and_passes_the_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(Path(tmp) / 'project', FIXTURE)
            server = make_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'

            def request(method, path, body=None, timeout=1200):
                data = json.dumps(body).encode() if body is not None else None
                req = urllib.request.Request(base + path, data=data, method=method,
                                             headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as error:
                    return error.code, json.load(error)

            try:
                design = project / 'designs/named_features.py'
                before = design.read_text()
                status, proposal = request('POST', '/proposals', {
                    'project': str(project), 'message': 'Add knurling to this face',
                    'selection': {'design': 'named_features.py', 'picks': [floor_pick()], 'measurement': None}})
                self.assertEqual(status, 202, proposal)
                deadline = time.monotonic() + 300
                while proposal['state'] not in ('ready', 'error') and time.monotonic() < deadline:
                    time.sleep(0.5)
                    _, proposal = request('GET', f"/proposals/{proposal['id']}")
                self.assertEqual(proposal['state'], 'ready', proposal.get('error'))
                self.assertEqual([(c['parameter'], c['old']) for c in proposal['changes']],
                                 [('knurl_pitch', None), ('knurl_depth', None)])
                with urllib.request.urlopen(base + proposal['previews']['before'][0]) as response:
                    before_mesh = response.read()
                with urllib.request.urlopen(base + proposal['previews']['after'][0]) as response:
                    after_mesh = response.read()
                self.assertGreater(len(after_mesh), len(before_mesh))   # the grooves are real geometry
                self.assertEqual(design.read_text(), before)            # nothing written until accepted
                status, accepted = request('POST', f"/proposals/{proposal['id']}/accept", {'wait': True, 'samples': 13})
                self.assertEqual(status, 200, accepted)
                run = accepted['run']
                self.assertTrue(run['verdict']['pass'], json.dumps(run['verdict'], indent=1)[:3000])
                edited = design.read_text()
                self.assertIn('"knurl_pitch"', edited)
                self.assertEqual(lint_design(design), [])
                self.assertEqual(len(list_versions(project)), 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
