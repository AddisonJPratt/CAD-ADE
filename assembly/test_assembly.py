"""The assembly gate: positive examples pass, and each negative control fails for its reason.

    XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m unittest assembly.test_assembly -v
"""
import copy
import tempfile
import unittest
from pathlib import Path

from assembly.demo import get_demo
from assembly.gate import evaluate, run_gate, validate_entries

ROOT = Path(__file__).resolve().parent.parent
STACK = ROOT / 'tests' / 'fixtures' / 'assembly_stack'


def check(report, name):
    return next(c for c in report['checks'] if c['name'] == name)


class HolderAssembly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate(ROOT / 'assembly' / 'holder_clip.py', ROOT)

    def test_holder_and_screws_pass_the_gate(self):
        self.assertTrue(self.report['pass'], self.report['checks'])
        self.assertEqual([c['status'] for c in self.report['checks']], ['PASS'] * 4)

    def test_screws_land_where_the_demo_shows_them(self):
        demo = {p['id']: p['position'] for p in get_demo(ROOT)['parts']}
        placed = {i['id']: i for i in self.report['instances']}
        self.assertEqual(set(placed), set(demo))
        for ident in ('screw_1', 'screw_2'):
            for got, want in zip(placed[ident]['position'], demo[ident]):
                self.assertAlmostEqual(got, want, places=3)
            self.assertAlmostEqual(placed[ident]['axis'][0], -1, places=6)

    def test_fasteners_measure_clearance_and_grip(self):
        for row in self.report['fasteners']:
            self.assertTrue(row['pass'], row)
            self.assertAlmostEqual(row['clearance_holes'][0]['dia'], 3.4, places=3)
            self.assertGreater(row['protrusion'], 0)

    def test_derived_entries_cover_each_instance_once(self):
        self.assertEqual([r['quantity'] for r in self.report['bom']], [1, 2])
        ids = [i for step in self.report['steps'] for i in step['part_ids']]
        self.assertEqual(sorted(ids), ['clip', 'screw_1', 'screw_2'])


class StackFixture(unittest.TestCase):
    def evaluate(self, **overrides):
        return evaluate(STACK / 'assembly.py', STACK, overrides)

    def test_lid_screwed_into_insert_passes(self):
        report = self.evaluate()
        self.assertTrue(report['pass'], report['checks'])
        row = report['fasteners'][0]
        self.assertEqual(row['into'], 'insert')
        self.assertAlmostEqual(row['grip'], 0.8, places=3)
        self.assertAlmostEqual(row['engagement'], 5.2, places=3)

    def test_colliding_parts_fail(self):
        report = self.evaluate(lid_gap=-1.0)
        self.assertFalse(report['pass'])
        self.assertEqual(check(report, 'Collisions')['status'], 'FAIL')
        self.assertTrue(any({r['a'], r['b']} == {'base', 'lid'} and not r['pass'] for r in report['collisions']))

    def test_too_long_screw_fails(self):
        report = self.evaluate(screw_length=10.0)
        self.assertFalse(report['pass'])
        detail = check(report, 'Fasteners')['detail']
        self.assertEqual(check(report, 'Fasteners')['status'], 'FAIL')
        self.assertIn('bottoms out', detail)

    def test_too_short_screw_fails(self):
        report = self.evaluate(screw_length=4.0)
        self.assertEqual(check(report, 'Fasteners')['status'], 'FAIL')
        self.assertIn('engages', check(report, 'Fasteners')['detail'])

    def test_wrong_clearance_hole_fails(self):
        tight = self.evaluate(lid_clearance=2.5)
        self.assertEqual(check(tight, 'Fasteners')['status'], 'FAIL')
        self.assertIn('clearance hole 2.50 mm', check(tight, 'Fasteners')['detail'])
        loose = self.evaluate(lid_clearance=4.5)
        self.assertEqual(check(loose, 'Fasteners')['status'], 'FAIL')
        self.assertIn('clearance hole 4.50 mm', check(loose, 'Fasteners')['detail'])

    def test_unknown_override_is_an_assembly_error(self):
        report = self.evaluate(no_such_param=1.0)
        self.assertFalse(report['pass'])
        self.assertEqual(check(report, 'Assembly file')['status'], 'FAIL')


class AssemblyFileContract(unittest.TestCase):
    def write(self, text):
        folder = Path(tempfile.mkdtemp())
        (folder / 'designs').symlink_to(STACK / 'designs')
        path = folder / 'assembly.py'
        path.write_text(text)
        return path, folder

    def test_hard_coded_dimensions_are_refused(self):
        path, folder = self.write('PARAMS = {}\n\ndef assemble(asm):\n    asm.screw("s", "M3", 12.0)\n')
        report = evaluate(path, folder)
        self.assertEqual(check(report, 'Assembly file')['status'], 'FAIL')
        self.assertIn('literal 12.0', check(report, 'Assembly file')['detail'])

    def test_loose_hardware_is_in_no_step(self):
        path, folder = self.write(
            'from library import standard_parts\nPARAMS = {}\n\ndef assemble(asm):\n'
            '    asm.printed("base", "base")\n    asm.insert("spare", "M3")\n')
        report = evaluate(path, folder)
        self.assertEqual(check(report, 'Derived entries')['status'], 'FAIL')
        self.assertIn('spare', check(report, 'Derived entries')['detail'])

    def test_derived_entries_must_map_to_exactly_one_instance(self):
        report = evaluate(STACK / 'assembly.py', STACK)
        ids = [i['id'] for i in report['instances']]
        self.assertTrue(validate_entries(ids, report['bom'], report['steps']))
        broken = copy.deepcopy(report)
        broken['steps'][-1]['part_ids'].append('lid')
        with self.assertRaises(ValueError):
            validate_entries(ids, broken['bom'], broken['steps'])
        broken = copy.deepcopy(report)
        broken['bom'][0]['part_ids'].append('ghost')
        with self.assertRaises(ValueError):
            validate_entries(ids, broken['bom'], broken['steps'])
        broken = copy.deepcopy(report)
        broken['bom'][0]['quantity'] += 1
        with self.assertRaises(ValueError):
            validate_entries(ids, broken['bom'], broken['steps'])


class GateSubprocess(unittest.TestCase):
    def test_run_gate_writes_report_and_survives_a_crash(self):
        with tempfile.TemporaryDirectory() as out:
            report = run_gate(STACK / 'assembly.py', STACK, Path(out))
            self.assertTrue(report['pass'], report['checks'])
            self.assertTrue((Path(out) / 'report.json').is_file())
            self.assertTrue(any(c['tier'] == 'needs physical test' for c in report['claims']))
        folder = Path(tempfile.mkdtemp())
        (folder / 'assembly.py').write_text('PARAMS = {}\n\ndef assemble(asm):\n    raise RuntimeError("boom")\n')
        with tempfile.TemporaryDirectory() as out:
            report = run_gate(folder / 'assembly.py', folder, Path(out))
            self.assertFalse(report['pass'])
            self.assertIn('boom', check(report, 'Assembly file')['detail'])


if __name__ == '__main__':
    unittest.main()
