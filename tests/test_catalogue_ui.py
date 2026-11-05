import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ui.server import Handler


class CatalogueUI(unittest.TestCase):
    def test_project_catalogue_is_visible_to_mission_control(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'
        def get(path):
            req = Request(base + path, headers={'Host': 'localhost:8765'})
            try:
                with urlopen(req) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, json.load(error)
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project / 'designs').mkdir()
            (project / 'designs' / 'part.py').write_text('# fixture')
            item = {'id': 'my-board', 'name': 'My board', 'dimensions': {}}
            (project / 'catalogue.json').write_text(json.dumps([item]))
            status, data = get('/api/library?project=' + quote(folder))
            self.assertEqual(status, 200)
            self.assertIn('my-board', [c['id'] for c in data['_components']])
            status, data = get('/api/library?project=' + quote(folder + '/missing'))
            self.assertEqual(status, 400)
            self.assertTrue(data['message'])
            self.assertEqual(get('/api/library')[0], 200)

if __name__ == '__main__':
    unittest.main()
