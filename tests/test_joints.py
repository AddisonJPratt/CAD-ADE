"""Joints between printed parts (#54): library geometry, the assembly API, and the gate's Joints check.

    XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m unittest tests.test_joints -v
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from build123d import Compound

from assembly.gate import evaluate
from library import joints
from library.printer_profiles import PROFILE

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests' / 'fixtures' / 'assembly_joints'
STACK = ROOT / 'tests' / 'fixtures' / 'assembly_stack'


def check(report, name):
    return next(c for c in report['checks'] if c['name'] == name)


def joint_rows(report):
    return {r['type']: r for r in report['joints']}


class LibraryTest(unittest.TestCase):
    def test_clearance_comes_from_the_printer_profile(self):
        for material, entry in PROFILE['materials'].items():
            for fit, value in entry['fit_clearance_mm_per_side'].items():
                self.assertEqual(joints.clearance(fit, material), value)
        patched = json.loads(json.dumps(PROFILE))
        patched['materials']['PETG']['fit_clearance_mm_per_side']['sliding'] = 0.3
        with mock.patch.dict(PROFILE, patched):
            self.assertEqual(joints.clearance('sliding', 'PETG'), 0.3)
        with self.assertRaises(ValueError):
            joints.clearance('sliding', 'unobtainium')

    def test_every_joint_kind_names_a_profile_fit(self):
        fits = set(PROFILE['materials']['PLA']['fit_clearance_mm_per_side'])
        for kind in joints.KINDS:
            fit = joints.spec(kind)['fit']
            self.assertTrue(fit is None or fit in fits, kind)

    def test_socket_is_the_male_grown_by_the_clearance(self):
        for kind in joints.BUILDERS:
            for gap in (0.10, 0.25, 0.35):
                geom = joints.build(kind, gap)
                self.assertTrue(geom.a_add.is_valid, kind)
                other = geom.b_add if geom.b_add is not None else geom.b_cut
                measured = Compound(geom.a_add.faces()).distance_to(Compound(other.faces()))
                self.assertAlmostEqual(measured, gap, places=6, msg=kind)

    def test_snap_fit_rules(self):
        geom = joints.build('snap_fit', 0.25)
        self.assertLess(geom.checks['strain'], geom.checks['max_strain'])
        self.assertGreater(geom.checks['retention'], 0)
        self.assertGreaterEqual(geom.checks['slot'], geom.checks['prong_close'])

    def test_living_hinge_notch_rule(self):
        rule = joints.living_hinge_rule('PLA')
        self.assertEqual((rule['min'], rule['max']), (0.4, 0.8))
        self.assertIsNotNone(rule['note'])
        self.assertIsNone(joints.living_hinge_rule('PETG')['note'])
        with self.assertRaises(ValueError):
            joints.living_hinge_notch(1.5, 1.0, 10.0, 3.0)


class GateTest(unittest.TestCase):
    """Each joint type through the assembly gate, evaluated in process on the joint fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.calibration = tempfile.TemporaryDirectory()
        cls.env = mock.patch.dict(os.environ, {'MAGIC_CALIBRATION': cls.calibration.name})
        cls.env.start()
        cls.reports = {}

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.calibration.cleanup()

    def report(self, name, project=FIXTURE, overrides=None, out=None):
        key = (name, str(project), json.dumps(overrides, sort_keys=True), out is not None)
        if key not in self.reports:
            self.reports[key] = evaluate(FIXTURE / name, project, overrides, out=out)
        return self.reports[key]

    def passes(self, report):
        self.assertTrue(report['pass'], json.dumps([c for c in report['checks'] if c['status'] != 'PASS'], indent=1)
                        + report.get('traceback', ''))

    def test_snap_fit_passes_and_measures_the_sliding_fit(self):
        report = self.report('assembly.py')
        self.passes(report)
        row = joint_rows(report)['snap_fit']
        self.assertEqual(row['sites'], 2)
        self.assertEqual(row['fit'], 'sliding')
        self.assertEqual(row['expected'], PROFILE['materials']['PLA']['fit_clearance_mm_per_side']['sliding'])
        for gap in row['measured']:
            self.assertAlmostEqual(gap, row['expected'], delta=0.02)
        self.assertLessEqual(max(row['overhang_added'].values()), 0.25)
        connection = next(c for c in report['connections'] if c['kind'] == 'joint')
        self.assertEqual(connection['male'], 'cap')   # the pegs grow up from the top-down cap
        self.assertIn('Snap the cap onto the base', report['steps'][1]['text'])

    def test_each_joint_type_passes_at_its_fit(self):
        fits = PROFILE['materials']['PLA']['fit_clearance_mm_per_side']
        for name, kind, fit in (('press.py', 'press_fit', 'press'), ('dovetail.py', 'dovetail', 'sliding'),
                                ('hinge.py', 'print_in_place_hinge', 'print_in_place')):
            with self.subTest(kind):
                report = self.report(name)
                self.passes(report)
                row = joint_rows(report)[kind]
                self.assertEqual(row['expected'], fits[fit])
                for gap in row['measured']:
                    self.assertAlmostEqual(gap, fits[fit], delta=0.02)

    def test_living_hinge_web_is_measured(self):
        report = self.report('living.py')
        self.passes(report)
        self.assertAlmostEqual(joint_rows(report)['living_hinge']['web'], 0.6, delta=0.02)
        off = self.report('living.py', overrides={'hinge_x': 10.0})
        self.assertEqual(check(off, 'Joints')['status'], 'FAIL')
        self.assertIn('web 3.00 mm', check(off, 'Joints')['detail'])

    def test_screw_insert_joint_uses_the_fastener_rules(self):
        report = self.report('screws.py', project=STACK)
        self.passes(report)
        row = joint_rows(report)['screw_insert']
        self.assertEqual(row['fit'], 'sliding')
        kinds = {c['kind'] for c in report['connections']}
        self.assertTrue({'press', 'fastener', 'joint'} <= kinds)
        long = self.report('screws.py', project=STACK, overrides={'screw_length': 12.0})
        self.assertEqual(check(long, 'Joints')['status'], 'FAIL')

    def test_a_clearance_that_is_not_the_profiles_fails(self):
        """Negative control: the joint asks for 0.05 mm; the PLA sliding fit is 0.25."""
        with tempfile.TemporaryDirectory() as tmp:
            source = (FIXTURE / 'assembly.py').read_text().replace(
                'asm.join("snap_fit", "cap", "base")', 'asm.join("snap_fit", "cap", "base", clearance=tight)')
            source = source.replace('PARAMS = {', 'PARAMS = {\n    "tight": (0.05, 0.0, 1.0),').replace(
                'def assemble(asm, cap_thickness)', 'def assemble(asm, cap_thickness, tight)')
            path = Path(tmp) / 'tight.py'
            path.write_text(source)
            report = evaluate(path, FIXTURE)
        self.assertFalse(report['pass'])
        detail = check(report, 'Joints')['detail']
        self.assertIn('PLA sliding fit is 0.25 mm per side', detail)

    def test_petg_project_uses_petg_clearance(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'project'
            shutil.copytree(FIXTURE, project)
            (project / 'printer.json').write_text(json.dumps({'printer': PROFILE['id'], 'material': 'PETG'}))
            patched = json.loads(json.dumps(PROFILE))
            patched['materials']['PETG']['fit_clearance_mm_per_side']['sliding'] = 0.3
            with mock.patch.dict(PROFILE, patched):
                report = evaluate(project / 'assembly.py', project)
        self.passes(report)
        row = joint_rows(report)['snap_fit']
        self.assertEqual((row['material'], row['expected']), ('PETG', 0.3))
        self.assertAlmostEqual(min(row['measured']), 0.3, delta=0.02)

    def test_joint_claims_need_a_physical_test_until_a_print_is_recorded(self):
        report = self.report('assembly.py')
        claim = next(c for c in report['claims'] if c['claim'].startswith('Joint '))
        self.assertEqual((claim['tier'], claim['status']), ('needs physical test', 'NOT TESTED'))
        events = Path(self.calibration.name) / 'events'
        events.mkdir(parents=True, exist_ok=True)
        (events / 'one.json').write_text(json.dumps({'joint_type': 'snap_fit', 'material': 'PLA', 'result': 'perfect'}))
        try:
            again = evaluate(FIXTURE / 'assembly.py', FIXTURE)
        finally:
            shutil.rmtree(events)
        claim = next(c for c in again['claims'] if c['claim'].startswith('Joint '))
        self.assertEqual(claim['tier'], 'print tested')

    def test_manifest_carries_the_joint_and_its_fit(self):
        with tempfile.TemporaryDirectory() as out:
            report = self.report('assembly.py', out=out)
            self.passes(report)
            manifest = json.loads((Path(out) / 'assembly.json').read_text())
        joint = next(j for j in manifest['joints'] if j['role'] == 'snap_fit')
        self.assertEqual((joint['parent'], joint['child'], joint['type']), ('base', 'cap', 'prismatic'))
        self.assertEqual(joint['axis'], [0.0, 0.0, -1.0])           # the cap goes down onto the base
        self.assertEqual(joint['fit']['tier'], 'needs physical test')
        self.assertEqual(joint['fit']['class'], 'sliding')
        cap = next(e for e in manifest['explode'] if e['instance'] == 'cap')
        self.assertGreater(cap['offset'][2], 0)                     # explodes upward, off the base

    def test_hinge_manifest_is_revolute_and_stays_seated(self):
        with tempfile.TemporaryDirectory() as out:
            report = self.report('hinge.py', out=out)
            manifest = json.loads((Path(out) / 'assembly.json').read_text())
        joint = next(j for j in manifest['joints'] if j['role'] == 'print_in_place_hinge')
        self.assertEqual(joint['type'], 'revolute')
        self.assertEqual(joint['range'], [-90.0, 90.0])
        right = next(e for e in manifest['explode'] if e['instance'] == 'right')
        self.assertEqual(right['distance'], 0)

    def test_hinge_swing_is_swept_and_wide_leaves_fail_it(self):
        """Negative control: 30 mm wide leaves meet each other long before the declared ±90 deg."""
        row = joint_rows(self.report('hinge.py'))['print_in_place_hinge']
        self.assertEqual(row['swing'], [-90.0, 90.0])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'wide.py'
            path.write_text((FIXTURE / 'hinge.py').read_text().replace('length=leaf_length)', 'length=leaf_length, width=leaf_length)'))
            report = evaluate(path, FIXTURE)
        self.assertEqual(check(report, 'Joints')['status'], 'FAIL')
        self.assertIn('the leaves collide turning past', check(report, 'Joints')['detail'])

    def test_parts_that_do_not_touch_cannot_snap(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = (FIXTURE / 'assembly.py').read_text().replace('top + cap_thickness', 'top + cap_thickness * 2')
            path = Path(tmp) / 'apart.py'
            path.write_text(source)
            report = evaluate(path, FIXTURE)
        self.assertEqual(check(report, 'Assembly file')['status'], 'FAIL')
        self.assertIn('do not touch face to face', check(report, 'Assembly file')['detail'])


if __name__ == '__main__':
    unittest.main()
