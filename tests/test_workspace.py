"""Projects home, new project and folder browsing at the engine seam (#66)."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from engine.api import Engine, make_server
from tests import test_parameters as parameter_cases

ROOT = parameter_cases.ROOT


class WorkspaceApiTest(unittest.TestCase):
    request = parameter_cases.ParameterApiTest.request
    tearDown = parameter_cases.ParameterApiTest.tearDown

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / 'Magic CAD Projects'
        patch = mock.patch.dict(os.environ, {'MAGIC_PROJECTS_HOME': str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)
        self.server = make_server(port=0, engine=Engine())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def test_new_project_is_created_in_home_listed_and_remembered(self):
        status, starters = self.request('GET', '/workspace/starters')
        self.assertEqual(status, 200)
        bracket = next(s for s in starters['starters'] if s['id'] == 'wall_bracket')
        self.assertEqual(bracket['label'], 'Wall bracket')
        self.assertTrue(bracket['summary'].startswith('L-shaped wall bracket'))

        status, created = self.request('POST', '/workspace/projects', {'name': 'Shelf bracket', 'starter': 'wall_bracket'})
        self.assertEqual(status, 201, created)
        self.assertEqual(created['project'], str((self.home / 'Shelf bracket').resolve()))
        self.assertTrue((self.home / 'Shelf bracket/designs/wall_bracket.py').is_file())
        self.assertEqual(len(created['versions']), 1)

        status, listed = self.request('GET', '/workspace/projects')
        self.assertEqual(status, 200)
        self.assertEqual(listed['home'], str(self.home.resolve()))
        self.assertEqual([p['name'] for p in listed['projects']], ['Shelf bracket'])
        self.assertTrue(listed['projects'][0]['in_home'])
        self.assertIsNotNone(listed['projects'][0]['opened'])
        # Browse starts where projects live once the home exists.
        status, listing = self.request('GET', '/workspace/browse')
        self.assertEqual(listing['path'], str(self.home.resolve()))
        self.assertEqual([(e['name'], e['project']) for e in listing['entries']], [('Shelf bracket', True)])

    def test_refuses_duplicate_bad_names_and_unknown_starters(self):
        self.assertEqual(self.request('POST', '/workspace/projects', {'name': 'A', 'starter': 'wall_bracket'})[0], 201)
        status, body = self.request('POST', '/workspace/projects', {'name': 'A', 'starter': 'wall_bracket'})
        self.assertEqual(status, 400)
        self.assertIn('already exists', body['error'])
        for name in ('../escape', '.hidden', '', 'a/b', 'x' * 81):
            self.assertEqual(self.request('POST', '/workspace/projects', {'name': name, 'starter': 'wall_bracket'})[0], 400, name)
        self.assertFalse((Path(self.tmp.name) / 'escape').exists())
        status, body = self.request('POST', '/workspace/projects', {'name': 'B', 'starter': 'nope'})
        self.assertEqual(status, 400)
        self.assertIn('no such starter', body['error'])

    def test_projects_elsewhere_are_listed_once_opened(self):
        from engine.versions import create_project
        elsewhere = create_project(Path(self.tmp.name) / 'elsewhere', 'wall_bracket')
        self.assertEqual(self.request('GET', '/workspace/projects')[1]['projects'], [])
        self.assertEqual(self.request('POST', '/workspace/recent', {'project': str(elsewhere)})[0], 200)
        projects = self.request('GET', '/workspace/projects')[1]['projects']
        self.assertEqual([(p['name'], p['in_home']) for p in projects], [('elsewhere', False)])
        status, body = self.request('POST', '/workspace/recent', {'project': self.tmp.name})
        self.assertEqual(status, 400)
        self.assertIn('not a project', body['error'])

    def test_browse_lists_visible_subfolders_and_marks_projects(self):
        from engine.versions import create_project
        base = Path(self.tmp.name) / 'browse'
        create_project(base / 'bracket', 'wall_bracket')
        (base / 'notes').mkdir()
        (base / '.secret').mkdir()
        (base / 'file.txt').write_text('x')
        status, listing = self.request('GET', '/workspace/browse?path=' + str(base))
        self.assertEqual(status, 200)
        self.assertEqual(listing['path'], str(base.resolve()))
        self.assertEqual(listing['parent'], str(base.resolve().parent))
        self.assertEqual([(e['name'], e['project']) for e in listing['entries']], [('bracket', True), ('notes', False)])
        self.assertTrue(self.request('GET', '/workspace/browse?path=' + str(base / 'bracket'))[1]['project'])
        self.assertEqual(self.request('GET', '/workspace/browse')[1]['path'], str(Path.home().resolve()))
        self.assertEqual(self.request('GET', '/workspace/browse?path=relative')[0], 400)
        self.assertEqual(self.request('GET', '/workspace/browse?path=' + str(base / 'missing'))[0], 400)


if __name__ == '__main__':
    unittest.main()
