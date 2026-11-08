"""Note pins (#26): kept with the version they were placed on, and handed to the agent.

Also ties the measure fixture (tests/fixtures/measure/) to a fresh harness run, so Studio's
measurement test compares against what the gate really measures.

    .venv/bin/python -m unittest tests.test_pins
"""
import json
import tempfile
import threading
import unittest
import urllib.parse
from pathlib import Path

from engine.agents import ScriptedFakeAgent
from engine.api import make_server
from engine.pins import PinError, MAX_NOTE, MAX_PINS, load_pins, save_pins
from engine.projects import ProjectError
from engine.versions import create_project, list_versions, save_version
from harness.pipeline import run as run_pipeline
from tests import test_parameters as parameter_cases

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/named_features.py'
STEPPED = ROOT / 'tests/fixtures/stepped_blocks.py'
MEASURE = ROOT / 'tests/fixtures/measure'


def pin(**extra):
    return {'id': 'pin-1', 'instance': 'plate', 'point': [1.0, -2.0, 9.0], 'normal': [0.0, 0.0, 1.0],
            'note': 'a drain hole here', 'feature': 'lid pocket', 'face': 11, **extra}


class PinStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'project', FIXTURE)
        self.version = list_versions(self.project)[0]['id']

    def tearDown(self):
        self.tmp.cleanup()

    def test_pins_are_kept_beside_the_version_and_not_in_its_files(self):
        self.assertEqual(load_pins(self.project, self.version), [])
        saved = save_pins(self.project, self.version, [pin()])
        self.assertEqual(saved, [pin()])
        self.assertEqual(load_pins(self.project, self.version), [pin()])
        stored = self.project / '.magic' / 'pins' / f'{self.version}.json'
        self.assertEqual(json.loads(stored.read_text()), {'version': self.version, 'pins': [pin()]})
        # Pins are notes about a version, not source: saving them never dirties the project.
        from engine.versions import unsaved
        self.assertEqual(unsaved(self.project), [])

    def test_pins_belong_to_one_version(self):
        save_pins(self.project, self.version, [pin()])
        design = self.project / 'designs' / 'named_features.py'
        design.write_text(design.read_text().replace('"height": (12.0,', '"height": (14.0,'))
        save_version(self.project, 'Taller')
        newer = list_versions(self.project)[0]['id']
        self.assertEqual(load_pins(self.project, newer), [])
        self.assertEqual(load_pins(self.project, self.version), [pin()])
        # A short ref resolves to the same version.
        self.assertEqual(load_pins(self.project, self.version[:10]), [pin()])

    def test_bad_pins_are_refused(self):
        bad = [pin(note=''), pin(note='x' * (MAX_NOTE + 1)), pin(point=[1, 2]), pin(normal=['a', 0, 0]),
               pin(instance=''), pin(face='3'), pin(feature=5), {'note': 'only a note'}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(PinError):
                save_pins(self.project, self.version, [value])
        with self.assertRaises(PinError):
            save_pins(self.project, self.version, [pin(id='same'), pin(id='same')])
        with self.assertRaises(PinError):
            save_pins(self.project, self.version, [pin(id=f'p{i}') for i in range(MAX_PINS + 1)])
        with self.assertRaises(ProjectError):  # an unknown version
            save_pins(self.project, 'f' * 40, [pin()])
        # Notes are trimmed; an empty list clears the version's pins.
        self.assertEqual(save_pins(self.project, self.version, [pin(note='  spaced  ')])[0]['note'], 'spaced')
        self.assertEqual(save_pins(self.project, self.version, []), [])
        self.assertEqual(load_pins(self.project, self.version), [])


class PinsReachTheAgentTest(unittest.TestCase):
    def test_the_scripted_agent_narrates_each_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(Path(tmp) / 'project', FIXTURE)
            chosen = {'design': 'named_features.py', 'picks': [], 'measurement': None,
                      'pins': [{**pin(), 'description': 'a pin on the "lid pocket" feature of body "plate" at (1.0, -2.0, 9.0) mm: "a drain hole here"'}]}
            session = ScriptedFakeAgent().start(project, None, chosen, 'size 32')
            narrated = [e['message'] for e in session['events'] if e['type'] == 'plan']
            self.assertIn('Pinned: ' + chosen['pins'][0]['description'], narrated)
            self.assertEqual(session['selection'], chosen)


class PinsHttpTest(unittest.TestCase):
    request = parameter_cases.ParameterApiTest.request
    tearDown = parameter_cases.ParameterApiTest.tearDown

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'project', FIXTURE)
        self.version = list_versions(self.project)[0]['id']
        self.server = make_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def test_pins_round_trip_per_version(self):
        query = urllib.parse.urlencode({'project': str(self.project), 'version': self.version})
        self.assertEqual(self.request('GET', '/projects/pins?' + query), (200, {'version': self.version, 'pins': []}))
        status, body = self.request('POST', '/projects/pins', {'project': str(self.project), 'version': self.version, 'pins': [pin()]})
        self.assertEqual(status, 200, body)
        self.assertEqual(body, {'version': self.version, 'pins': [pin()]})
        self.assertEqual(self.request('GET', '/projects/pins?' + query), (200, {'version': self.version, 'pins': [pin()]}))
        status, body = self.request('POST', '/projects/pins', {'project': str(self.project), 'version': self.version, 'pins': [pin(note='')]})
        self.assertEqual(status, 400)
        self.assertIn('note', body['error'])
        status, _ = self.request('GET', '/projects/pins?' + urllib.parse.urlencode({'project': str(self.project), 'version': 'nope'}))
        self.assertEqual(status, 400)


class MeasureFixtureTest(unittest.TestCase):
    """tests/fixtures/measure/ is a real harness export of stepped_blocks plus the gate's measurement."""

    def test_the_committed_measure_fixture_matches_a_fresh_gate_run(self):
        with tempfile.TemporaryDirectory() as out:
            code, report = run_pipeline(str(STEPPED), str(ROOT / 'tests/fixtures/stepped_blocks.yaml'), out, samples=12)
            self.assertEqual(code, 0, report['gates'])
            gate = json.loads((MEASURE / 'gate.json').read_text())
            measured = {row['name']: row['measured'] for row in report['geometry']['dimensions']}
            for row in gate['dimensions']:
                self.assertAlmostEqual(measured[row['name']], row['measured'], places=6,
                                       msg='tests/fixtures/measure/gate.json is stale')
            for name in ('base', 'riser'):
                self.assertEqual(json.loads((MEASURE / f'{name}.faces.json').read_text()), json.loads((Path(out) / f'{name}.faces.json').read_text()))
                fresh, committed = (Path(out) / f'{name}.stl').read_bytes(), (MEASURE / f'{name}.stl').read_bytes()
                self.assertEqual(fresh[80:], committed[80:], f'tests/fixtures/measure/{name}.stl is stale')


if __name__ == '__main__':
    unittest.main()
