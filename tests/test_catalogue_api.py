import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from engine.api import make_server


class CatalogueAPI(unittest.TestCase):
    def test_catalogue_and_user_measurements(self):
        server = make_server(0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_address[1]}'
        with tempfile.TemporaryDirectory() as folder:
            def request(method, path, body=None):
                data = json.dumps(body).encode() if body is not None else None
                req = Request(base + path, data=data, method=method,
                              headers={'Content-Type': 'application/json'} if data else {})
                try:
                    with urlopen(req) as response:
                        return response.status, json.load(response)
                except HTTPError as error:
                    return error.code, json.load(error)
            component = {'id': 'my-board', 'name': 'My board', 'dimensions': {'length': 31.2, 'width': 20.0, 'height': 4.0}}
            unrelated = Path(folder) / 'catalogue.json'
            unrelated.write_text('[]')
            self.assertEqual(request('POST', '/catalogue', {'project': folder, 'component': component})[0], 400)
            self.assertEqual(unrelated.read_text(), '[]')
            unrelated.unlink()
            (Path(folder) / 'designs').mkdir()
            (Path(folder) / 'designs' / 'fixture.py').write_text('# fixture')
            path = '/catalogue?project=' + quote(folder)
            status, catalogue = request('GET', path)
            self.assertEqual(status, 200)
            board = next(c for c in catalogue['components'] if c['id'] == 'esp32-devkitc-v4')
            self.assertEqual(board['dimensions']['length']['value'], 48.26)
            self.assertEqual(board['dimensions']['length']['provenance'], 'datasheet-verified')
            self.assertTrue(any(v['purpose'] == 'usb-access' for v in board['keepouts']))
            self.assertEqual(request('GET', '/catalogue')[0], 400)
            standard = json.loads((Path(__file__).resolve().parent.parent / 'library' / 'standard_parts.json').read_text())
            for category in ('screws', 'heatset_inserts', 'bearings', 'motor_mounts', 'extrusions', 'grids'):
                for part, dimensions in standard[category].items():
                    for dimension, value in dimensions.items():
                        if isinstance(value, (int, float)):
                            self.assertEqual(standard['_dimension_provenance'][category][part][dimension], 'unverified')
            self.assertIn('M2.5', standard['screws'])
            self.assertIn('M2.5', standard['heatset_inserts'])
            component = {'id': 'my-board', 'name': 'My board', 'dimensions': {'length': 31.2, 'width': 20.0, 'height': 4.0}}
            status, saved = request('POST', '/catalogue', {'project': folder, 'component': component})
            self.assertEqual(status, 201)
            self.assertEqual(saved['component']['dimensions']['length']['provenance'], 'user-measured')
            self.assertEqual(saved['component']['keepouts'][0]['dimensions'], ['width', 'length', 'height'])
            self.assertIn('length along y', saved['component']['coordinate_system'])
            self.assertTrue(saved['component']['keepouts'][0]['placement'])
            status, catalogue = request('GET', path)
            self.assertIn('my-board', [c['id'] for c in catalogue['components']])
            self.assertEqual(request('POST', '/catalogue', {'project': folder, 'component': component})[0], 409)
            component['id'] = '../outside'
            self.assertEqual(request('POST', '/catalogue', {'project': folder, 'component': component})[0], 400)

if __name__ == '__main__':
    unittest.main()
