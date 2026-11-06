"""Parameter controls exercise the engine's public HTTP contract."""
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from engine.api import make_server
from engine.versions import create_project, save_version

ROOT = Path(__file__).resolve().parents[1]


class ParameterApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'project', ROOT / 'designs/cable_clip.py')
        self.server = make_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}' + path,
                                         data=data, method=method,
                                         headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_reads_all_parameters_with_declared_units_without_executing_design(self):
        source = self.project / 'designs/cable_clip.py'
        source.write_text(source.read_text() + '\nraise RuntimeError(\"Do not execute to read parameters\")\n')
        save_version(self.project, 'Fixture refuses execution')
        query = urllib.parse.urlencode({'project': str(self.project), 'design': 'cable_clip.py'})
        status, response = self.request('GET', '/projects/parameters?' + query)
        self.assertEqual(status, 200)
        self.assertEqual(response['parameters'], [
            {'name': 'clip_width', 'value': 12.0, 'min': 8.0, 'max': 20.0,
             'unit': 'mm', 'intent': 'Print height of the clip', 'integer': False},
            {'name': 'cable_dia', 'value': 6.0, 'min': 3.0, 'max': 10.0,
             'unit': 'mm', 'intent': 'Round cable diameter', 'integer': False},
            {'name': 'arm_thickness', 'value': 1.6, 'min': 1.2, 'max': 2.4,
             'unit': 'mm', 'intent': 'Flexing arm wall', 'integer': False},
        ])
        bad = urllib.parse.urlencode({'project': str(self.project), 'design': '../magic.py'})
        self.assertEqual(self.request('GET', '/projects/parameters?' + bad)[0], 400)

    def test_structured_edit_validates_bounds_and_reject_leaves_version_unchanged(self):
        query = urllib.parse.urlencode({'project': str(self.project), 'design': 'cable_clip.py'})
        versions = '/projects/versions?' + urllib.parse.urlencode({'project': str(self.project)})
        before = self.request('GET', versions)[1]
        for value in [2, 11, '8', True, None, float('inf'), float('nan')]:
            status, _ = self.request('POST', '/proposals', {
                'project': str(self.project), 'selection': {'design': 'cable_clip.py'},
                'parameter': {'name': 'cable_dia', 'value': value}})
            self.assertEqual(status, 400, value)
        status, pending = self.request('POST', '/proposals', {
            'project': str(self.project), 'selection': {'design': 'cable_clip.py'},
            'parameter': {'name': 'cable_dia', 'value': 8}})
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 120
        while pending['state'] not in ('ready', 'error') and time.monotonic() < deadline:
            time.sleep(0.1)
            _, pending = self.request('GET', '/proposals/' + pending['id'])
        self.assertEqual(pending['state'], 'ready', pending.get('error'))
        self.assertEqual(pending['changes'], [{'parameter': 'cable_dia', 'old': 6.0, 'new': 8}])
        self.assertEqual(self.request('GET', '/projects/parameters?' + query)[1]['parameters'][1]['value'], 6)
        self.assertEqual(self.request('POST', '/proposals/' + pending['id'] + '/reject', {})[0], 200)
        self.assertEqual(self.request('GET', versions)[1], before)
        self.assertEqual(self.request('GET', '/projects/parameters?' + query)[1]['parameters'][1]['value'], 6)

    def test_integer_parameter_rejects_fractional_edits(self):
        project = create_project(Path(self.tmp.name) / 'gears', ROOT / 'designs/gear_pair.py')
        status, _ = self.request('POST', '/proposals', {
            'project': str(project), 'selection': {'design': 'gear_pair.py'},
            'parameter': {'name': 'teeth_a', 'value': 22.5}})
        self.assertEqual(status, 400)

    def test_accepted_edit_keeps_brief_defaults_in_sync_without_changing_requirements(self):
        import yaml
        brief = self.project / 'briefs/cable_clip.yaml'
        before = yaml.safe_load(brief.read_text())
        _, pending = self.request('POST', '/proposals', {
            'project':str(self.project), 'selection':{'design':'cable_clip.py'},
            'parameter':{'name':'cable_dia','value':8}})
        deadline = time.monotonic() + 120
        while pending['state'] not in ('ready','error') and time.monotonic() < deadline:
            time.sleep(.1)
            _, pending = self.request('GET', '/proposals/' + pending['id'])
        self.assertEqual(pending['state'],'ready',pending.get('error'))
        status, accepted = self.request('POST', '/proposals/' + pending['id'] + '/accept', {'wait':True,'samples':7})
        self.assertEqual(status,200)
        self.assertTrue(accepted['run']['verdict']['pass'])
        after = yaml.safe_load(brief.read_text())
        self.assertEqual(after['hard_dimensions'],before['hard_dimensions'])
        self.assertEqual(after['measures'],before['measures'])
        self.assertEqual(after['params']['cable_dia']['value'],8)
        self.assertEqual(after['params']['cable_dia']['min'],3)
        self.assertEqual(after['params']['cable_dia']['max'],10)
