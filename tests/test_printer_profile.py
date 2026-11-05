"""Printer selection and build volume through the engine's HTTP interface."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from engine.api import make_server


class PrinterProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / 'designs').mkdir()
        (self.project / 'designs' / 'part.py').write_text('''from build123d import Box, Align
PARAMS = {"width": (257.0, 257.0, 258.0), "side": (10.0, 9.0, 11.0)}
def build(width, side):
    return Box(width, side, side, align=(Align.CENTER, Align.CENTER, Align.MIN))
''')
        self.server = make_server(port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, method=method,
                                         headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_selection_and_oversize_gate(self):
        query = urllib.parse.urlencode({'project': str(self.project)})
        status, result = self.request('GET', '/projects/printer?' + query)
        self.assertEqual(status, 200)
        self.assertEqual(result['profile']['build_volume_mm'], [256, 256, 256])
        self.assertEqual(result['material'], 'PLA')
        status, result = self.request('POST', '/projects/printer',
                                      {'project': str(self.project), 'material': 'PETG'})
        self.assertEqual(status, 200)
        self.assertEqual(result['material'], 'PETG')
        status, result = self.request('POST', '/projects/printer',
                                      {'project': str(self.project), 'material': 'unknown'})
        self.assertEqual(status, 400)
        status, run = self.request('POST', '/runs', {'project': str(self.project), 'wait': True})
        self.assertEqual(status, 200)
        self.assertFalse(run['verdict']['pass'])
        report = json.loads((self.project / 'outputs/part/report.json').read_text())
        self.assertIn('exceeds', str(report['gates']))
        self.assertEqual(report['printer']['material'], 'PETG')


    def test_selected_material_supplies_fit_to_the_design(self):
        design = self.project / 'designs' / 'part.py'
        design.write_text('''from build123d import Box, Align
from library import standard_parts
PARAMS = {"width": (20.0, 19.0, 21.0)}
def build(width):
    clearance = standard_parts()["fits"]["sliding"]
    return Box(width + 2 * clearance, width, width, align=(Align.CENTER, Align.CENTER, Align.MIN))
''')
        # A project-local library can contain old defaults; the selected material wins.
        import shutil
        shutil.copytree(Path(__file__).resolve().parents[1] / 'library', self.project / 'library',
                        ignore=shutil.ignore_patterns('__pycache__'))
        table = self.project / 'library/standard_parts.json'
        data = json.loads(table.read_text())
        data['fits']['sliding'] = 1.0
        table.write_text(json.dumps(data))
        status, _ = self.request('POST', '/projects/printer',
                                 {'project': str(self.project), 'material': 'PETG'})
        self.assertEqual(status, 200)
        status, run = self.request('POST', '/runs', {'project': str(self.project), 'wait': True})
        self.assertEqual(status, 200)
        self.assertTrue(run['verdict']['pass'])
        report = json.loads((self.project / 'outputs/part/report.json').read_text())
        metrics = next(iter(report['printability'].values()))['metrics']
        self.assertAlmostEqual(metrics['extents'][0], 20.5, places=2)
        default_sweep = next(row for row in report['sweep']['rows'] if row['label'] == 'default')
        self.assertAlmostEqual(next(iter(default_sweep['bbox'].values()))[0], 20.5, places=2)
        cli_out = self.project / 'cli-out'
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'magic.py'),
                                 'check', str(design), '--no-sweep', '--out', str(cli_out)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        cli_report = json.loads((cli_out / 'report.json').read_text())
        cli_metrics = next(iter(cli_report['printability'].values()))['metrics']
        self.assertAlmostEqual(cli_metrics['extents'][0], 20.5, places=2)


    def test_volume_boundary_and_height(self):
        design = self.project / 'designs' / 'part.py'
        design.write_text('''from build123d import Box, Align
PARAMS = {"width": (255.0, 254.0, 256.0), "side": (10.0, 9.0, 11.0)}
def build(width, side):
    return Box(width, side, side, align=(Align.CENTER, Align.CENTER, Align.MIN))
''')
        status, run = self.request('POST', '/runs', {'project': str(self.project), 'wait': True})
        self.assertEqual(status, 200)
        self.assertTrue(run['verdict']['pass'])
        design.write_text('''from build123d import Box, Align
PARAMS = {"height": (257.0, 257.0, 258.0), "side": (10.0, 9.0, 11.0)}
def build(height, side):
    return Box(side, side, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
''')
        status, run = self.request('POST', '/runs', {'project': str(self.project), 'wait': True})
        self.assertEqual(status, 200)
        self.assertFalse(run['verdict']['pass'])
        report = json.loads((self.project / 'outputs/part/report.json').read_text())
        self.assertIn('exceeds', str(report['gates']))

if __name__ == '__main__':
    unittest.main()
