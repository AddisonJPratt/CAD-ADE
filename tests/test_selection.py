"""Selection at both seams: the harness face map, and a structured selection reaching the agent.

    .venv/bin/python -m unittest tests.test_selection
"""
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

from engine.api import Engine, make_server
from engine.agents import ScriptedFakeAgent
from engine.projects import run_project
from engine.versions import create_project
from harness.execute import run_worker
from tests import test_parameters as parameter_cases

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/named_features.py'
FACE_MAP = ROOT / 'tests/fixtures/faces_map/plate.faces.json'


def rounded(value, places=6):
    if isinstance(value, float):
        return round(value, places)
    if isinstance(value, list):
        return [rounded(v, places) for v in value]
    if isinstance(value, dict):
        return {k: rounded(v, places) for k, v in value.items()}
    return value


def selection(design='named_features.py'):
    """A selection as Studio sends it: one named face, one unnamed face, and their distance."""
    return {'design': design, 'picks': [
        {'instance': 'plate', 'kind': 'face', 'feature': 'lid pocket', 'face': 11,
         'description': 'a flat face on the "lid pocket" feature of body "plate" facing up (+Z), area ≈ 64 mm², centred at (0.0, 0.0, 9.0) mm',
         'point': [0.4, -0.2, 9.0], 'normal': [0, 0, 1], 'centroid': [0, 0, 9], 'area': 64.0, 'flat': True, 'note': None, 'locked': False},
        {'instance': 'plate', 'kind': 'face', 'feature': None, 'face': 1,
         'description': 'a flat face on body "plate" facing front (−Y), area ≈ 432 mm², centred at (0.0, -18.0, 6.0) mm',
         'point': [1.0, -18.0, 5.0], 'normal': [0, -1, 0], 'centroid': [0, -18, 6], 'area': 432.0, 'flat': True, 'note': 'keep this flat', 'locked': True}],
        'measurement': {'value': 20.12, 'kind': 'centre to centre', 'from': [0, 0, 9], 'to': [0, -18, 6]}}


class FaceMapTest(unittest.TestCase):
    """The worker writes <part>.faces.json beside each STL: named feature faces, geometry for the rest."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        result = run_worker(FIXTURE, cls.tmp.name)
        assert result['ok'], result.get('traceback')
        cls.part = result['parts'][0]
        cls.map = json.loads(Path(cls.part['faces']).read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_named_features_label_the_faces_their_cutters_leave(self):
        self.assertEqual(self.map['part'], 'plate')
        self.assertEqual(self.map['features'], ['lid pocket', 'mount hole'])
        by_feature = {}
        for face in self.map['faces']:
            by_feature.setdefault(face['feature'], []).append(face)
        self.assertEqual(len(by_feature['lid pocket']), 5)       # four walls and the floor
        self.assertEqual([f['kind'] for f in by_feature['mount hole']], ['cylinder'])
        self.assertAlmostEqual(by_feature['mount hole'][0]['radius'], 2.0)
        floor = next(f for f in by_feature['lid pocket'] if f['normal'] == [0.0, 0.0, 1.0])
        self.assertAlmostEqual(floor['centre'][2], 9.0)          # height 12 minus pocket depth 3
        self.assertAlmostEqual(floor['area'], 324.0)                # (size / 2)²

    def test_unnamed_faces_keep_a_geometric_description(self):
        unnamed = [f for f in self.map['faces'] if f['feature'] is None]
        self.assertEqual(len(unnamed), 6)                        # the plate's own six faces
        top = next(f for f in unnamed if f['normal'] == [0.0, 0.0, 1.0])
        self.assertAlmostEqual(top['centre'][2], 12.0)
        self.assertTrue(all(f['kind'] == 'plane' and f['area'] > 0 and f['bbox']['min'] <= f['bbox']['max'] for f in unnamed))
        # The top face has the pocket in its middle: its sample point still lies on the face itself.
        self.assertGreater(max(abs(top['centre'][0]), abs(top['centre'][1])), 9.0)

    def test_the_committed_fixture_matches_a_fresh_export(self):
        self.assertEqual(rounded(json.loads(FACE_MAP.read_text())), rounded(self.map),
                         'tests/fixtures/faces_map/plate.faces.json is stale: review the change and copy the new export over it')

    def test_feature_helper_validates_and_records_in_order(self):
        from build123d import Box
        from library import declared_features, feature, reset_features
        reset_features()
        with self.assertRaises(ValueError):
            feature('', Box(1, 1, 1))
        with self.assertRaises(ValueError):
            feature('slot', 'not a shape')
        box = feature(' slot ', Box(1, 1, 1))
        self.assertEqual(box.label, 'slot')
        feature('boss', Box(2, 2, 2))
        self.assertEqual([name for name, _ in declared_features()], ['slot', 'boss'])
        reset_features()
        self.assertEqual(declared_features(), [])


class FakeAgentSelectionTest(unittest.TestCase):
    """The scripted agent keeps the selection it was handed and narrates each pick."""

    def test_selection_is_kept_and_each_pick_becomes_a_plan_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(Path(tmp) / 'project', FIXTURE)
            chosen = selection()
            session = ScriptedFakeAgent().start(project, None, chosen, 'size 32')
            self.assertEqual(session['selection'], chosen)
            self.assertEqual(session['changes'], [{'parameter': 'size', 'old': 36.0, 'new': 32.0}])
            narrated = [e['message'] for e in session['events'] if e['type'] == 'plan']
            self.assertEqual(narrated[1:], ['Selected: ' + p['description'] for p in chosen['picks']])
            self.assertIsNone(ScriptedFakeAgent().start(project, None, None, 'size 34')['selection'])


class SelectionHttpSeamTest(unittest.TestCase):
    """Engine HTTP seam: the face map is a version artifact, and a selection round-trips through a proposal."""
    request = parameter_cases.ParameterApiTest.request
    tearDown = parameter_cases.ParameterApiTest.tearDown

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'project', FIXTURE)
        _, verdict = run_project(self.project, samples=9)  # min/default/max of 4 params
        self.assertTrue(verdict['pass'], verdict)
        self.server = make_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def test_face_map_is_served_with_the_version_and_the_selection_reaches_the_agent(self):
        query = urllib.parse.urlencode({'project': str(self.project)})
        status, versions = self.request('GET', '/projects/versions?' + query)
        self.assertEqual(status, 200)
        current = next(v for v in versions['versions'] if v['current'])
        stored = json.loads((self.project / '.magic' / 'verdicts' / f"{current['id']}.json").read_text())
        self.assertIn('named_features/plate.faces.json', stored['designs'][0]['artifacts'])
        status, models = self.request('GET', '/projects/version-artifacts?' + urllib.parse.urlencode({'project': str(self.project), 'version': current['id']}))
        self.assertEqual(models, {'models': ['named_features/plate.stl']})
        status, face_map = self.request('GET', '/projects/version-artifacts?' + urllib.parse.urlencode(
            {'project': str(self.project), 'version': current['id'], 'path': 'named_features/plate.faces.json'}))
        self.assertEqual(status, 200)
        self.assertEqual(face_map['features'], ['lid pocket', 'mount hole'])
        self.assertEqual(rounded(face_map), rounded(json.loads(FACE_MAP.read_text())))

        chosen = selection()
        status, pending = self.request('POST', '/proposals', {'project': str(self.project), 'message': 'size 32', 'selection': chosen})
        self.assertEqual(status, 202, pending)
        self.assertEqual(pending['selection'], chosen)
        status, again = self.request('GET', '/proposals/' + pending['id'])
        self.assertEqual(status, 200)
        self.assertEqual(again['selection'], chosen)
        self.assertEqual(again['changes'], [{'parameter': 'size', 'old': 36.0, 'new': 32.0}])
        self.assertEqual(self.request('POST', f"/proposals/{pending['id']}/reject", {})[0], 200)


class ClaudeAdapterSelectionTest(unittest.TestCase):
    """The Claude Code adapter hands the structured selection to the CLI inside its context."""
    request = parameter_cases.ParameterApiTest.request
    tearDown = parameter_cases.ParameterApiTest.tearDown

    def setUp(self):
        from engine.claude_agent import ClaudeCodeAgent
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'project', FIXTURE)
        self.prompt_file = Path(self.tmp.name) / 'prompt.txt'
        agent = ClaudeCodeAgent(command=[sys.executable, str(ROOT / 'tests/fixtures/claude_stream.py'), '--prompt-file', str(self.prompt_file)])
        self.server = make_server(port=0, engine=Engine(agent=agent))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def test_selection_is_in_the_prompt_the_cli_receives(self):
        chosen = selection()
        status, pending = self.request('POST', '/proposals', {'project': str(self.project), 'message': 'make the pocket deeper', 'selection': chosen})
        self.assertEqual(status, 202, pending)
        self.assertEqual(pending['selection'], chosen)
        deadline = time.monotonic() + 120
        while not self.prompt_file.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        prompt = self.prompt_file.read_text()
        context = json.loads(prompt[prompt.index('{'):])
        self.assertEqual(context['selection'], chosen)
        self.assertEqual(context['request'], 'make the pocket deeper')
        self.assertEqual(self.request('POST', f"/proposals/{pending['id']}/reject", {})[0], 200)


if __name__ == '__main__':
    unittest.main()
