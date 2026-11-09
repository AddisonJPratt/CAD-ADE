""""Join these two parts with a snap-fit" on two picks: a previewed assembly change (#54).

    XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m unittest tests.test_join_proposal -v
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.api import Engine, Handler
from engine.joins import joined_source, requested_joint
from engine.projects import ProjectError
from engine.versions import create_project, list_versions, save_version

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'assembly_joints'
UNJOINED = (FIXTURE / 'assembly.py').read_text().replace('    asm.join("snap_fit", "cap", "base")\n', '')


def pick(body, feature=None):
    return {'instance': body, 'kind': 'face', 'feature': feature, 'parameters': {},
            'description': f'Face on {body}', 'point': [0, 0, 0], 'normal': [0, 0, 1]}


class RequestTest(unittest.TestCase):
    def test_requested_joint(self):
        self.assertEqual(requested_joint('Join these two parts with a snap-fit'), 'snap_fit')
        self.assertEqual(requested_joint('join them with a press fit'), 'press_fit')
        self.assertEqual(requested_joint('connect the leaves with a print-in-place hinge'), 'print_in_place_hinge')
        self.assertIsNone(requested_joint('size 24'))
        self.assertIsNone(requested_joint('make the snap hook longer'))

    def test_joined_source_adds_one_line_to_assemble(self):
        source = joined_source(UNJOINED, 'snap_fit', 'cap', 'base')
        self.assertEqual(source.count('asm.join('), 1)
        self.assertTrue(source.rstrip().endswith('asm.join("snap_fit", "cap", "base")'))
        with self.assertRaises(ProjectError):
            joined_source(source, 'snap_fit', 'base', 'cap')


class JoinProposalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'box', FIXTURE / 'designs' / 'base_block.py')
        shutil.copy2(FIXTURE / 'designs' / 'cap_block.py', self.project / 'designs')
        (self.project / 'assembly.py').write_text(UNJOINED)
        save_version(self.project, 'Add the cap and the assembly')
        self.handler = Handler.__new__(Handler)
        self.handler.engine = Engine()

    def tearDown(self):
        self.handler.engine.artifacts.cleanup()
        self.tmp.cleanup()

    def propose(self, message, picks):
        return self.handler.post_proposal({'project': str(self.project), 'message': message,
                                           'selection': {'design': 'base_block.py', 'picks': picks}})

    def test_snap_fit_on_two_picks_is_previewed_then_kept(self):
        status, pending = self.propose('Join these two parts with a snap-fit',
                                       [pick('cap block'), pick('base block')])
        self.assertEqual(status, 202)
        proposal = self.handler.engine.proposals[pending['id']]
        self.assertTrue(proposal['session'].wait_for('ready', 240), proposal['session'].error)
        ready = self.handler.proposal_summary(proposal)
        change = ready['changes'][0]
        self.assertEqual((change['kind'], change['joint'], change['parts']), ('joint', 'snap_fit', ['cap', 'base']))
        self.assertEqual((change['fit'], change['material'], change['clearance']), ('sliding', 'PLA', 0.25))
        self.assertEqual(len(ready['previews']['before']), 2)
        self.assertEqual(len(ready['previews']['after']), 2)
        # Nothing changed in the project until the change is kept.
        self.assertNotIn('asm.join', (self.project / 'assembly.py').read_text())
        status, accepted = self.handler.accept_proposal(pending['id'], {'wait': True, 'samples': 11})
        self.assertEqual(status, 200)
        self.assertIn('asm.join("snap_fit", "cap", "base")', (self.project / 'assembly.py').read_text())
        verdict = accepted['run']['verdict']
        self.assertIsNotNone(verdict, accepted['run'])
        self.assertTrue(verdict['assembly']['pass'], verdict['assembly'])
        joints = next(c for c in verdict['assembly']['checks'] if c['name'] == 'Joints')
        self.assertEqual(joints['status'], 'PASS')
        self.assertTrue(any(c['tier'] == 'needs physical test' and c['claim'].startswith('Joint ')
                            for c in verdict['assembly']['claims']))
        self.assertEqual(len(list_versions(self.project)), 3)

    def test_one_pick_is_refused_with_a_reason(self):
        with self.assertRaisesRegex(ProjectError, 'Pick a face on each of the two parts'):
            self.propose('Join these two parts with a snap-fit', [pick('cap block')])

    def test_a_joint_that_needs_a_frame_is_refused(self):
        with self.assertRaisesRegex(ProjectError, 'needs a joint frame'):
            self.propose('Join these with a dovetail', [pick('cap block'), pick('base block')])


if __name__ == '__main__':
    unittest.main()
