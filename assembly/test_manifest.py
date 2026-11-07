"""The assembly manifest: the one derived file Studio and the instructions generator read.

    XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m unittest assembly.test_manifest -v

Regenerate the committed fixture (only after reviewing why it changed):

    XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m assembly.manifest --refresh-fixture
"""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

from assembly.gate import evaluate, run_gate
from assembly.manifest import (FIXTURE, GAP_MIN, GAP_RATIO, MANIFEST, ManifestError, explode, gap,
                               quaternion_matrix, validate)

ROOT = Path(__file__).resolve().parent.parent
STACK = ROOT / 'tests' / 'fixtures' / 'assembly_stack'


def node(ident, parent=None, direction=(0, 0, 1), extent=10.0, role=None):
    return {'id': ident, 'parent': parent, 'direction': list(direction), 'extent': extent, 'role': role}


class ExplodeRule(unittest.TestCase):
    """Pure geometry of the rule: no CAD, so each clause is checked on its own."""

    def by_id(self, rows):
        return {r['instance']: r for r in rows}

    def test_gap_is_a_quarter_of_the_extent_with_a_floor(self):
        self.assertAlmostEqual(gap(40.0), 40.0 * GAP_RATIO)
        self.assertAlmostEqual(gap(2.0), GAP_MIN)

    def test_a_root_does_not_move(self):
        row = self.by_id(explode([node('base')]))['base']
        self.assertEqual(row['distance'], 0)
        self.assertEqual(row['offset'], [0, 0, 0])

    def test_a_child_backs_out_along_its_direction_by_its_extent_plus_gap(self):
        rows = self.by_id(explode([node('clip'), node('screw', 'clip', (1, 0, 0), 15.0)]))
        self.assertEqual(rows['screw']['direction'], [1, 0, 0])
        self.assertAlmostEqual(rows['screw']['distance'], 15.0 + gap(15.0))
        self.assertEqual(rows['screw']['offset'], [round(15.0 + gap(15.0), 4), 0, 0])

    def test_a_clamped_part_clears_what_pops_out_of_its_parent_the_same_way(self):
        rows = self.by_id(explode([node('base'), node('insert', 'base', extent=4.0),
                                   node('lid', 'base', extent=3.0, role='clamp')]))
        insert, lid = rows['insert']['distance'], rows['lid']['distance']
        self.assertAlmostEqual(lid, 3.0 + gap(3.0) + insert)
        self.assertGreater(lid, insert)

    def test_offsets_accumulate_down_the_tree(self):
        rows = self.by_id(explode([node('base'), node('lid', 'base', extent=3.0, role='clamp'),
                                   node('screw', 'lid', extent=9.0)]))
        self.assertAlmostEqual(rows['screw']['offset'][2],
                               round(rows['lid']['distance'] + rows['screw']['distance'], 4), places=3)

    def test_a_cycle_is_refused(self):
        with self.assertRaises(ManifestError):
            explode([node('a', 'b'), node('b', 'a')])


class HolderManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp())
        cls.report = evaluate(ROOT / 'assembly' / 'holder_clip.py', ROOT, out=cls.out)
        cls.manifest = json.loads((cls.out / MANIFEST).read_text())

    def test_the_gate_writes_a_valid_manifest_next_to_its_report(self):
        self.assertEqual(self.report['manifest'], MANIFEST)
        self.assertTrue(validate(self.manifest))
        self.assertEqual(self.manifest['schema_version'], 1)
        self.assertTrue(self.manifest['pass'])

    def test_it_matches_the_committed_fixture(self):
        self.assertEqual(self.manifest, json.loads(FIXTURE.read_text()),
                         'holder manifest changed; review it, then refresh the fixture')

    def test_screws_hang_off_the_clip_by_fastener_joints(self):
        parents = {i['id']: i['parent'] for i in self.manifest['instances']}
        self.assertEqual(parents, {'clip': None, 'screw_1': 'clip', 'screw_2': 'clip'})
        joints = {j['child']: j for j in self.manifest['joints']}
        self.assertEqual(set(joints), {'screw_1', 'screw_2'})
        for joint in joints.values():
            self.assertEqual((joint['type'], joint['role'], joint['range']), ('prismatic', 'fastener', None))
            self.assertAlmostEqual(joint['axis'][0], -1, places=6)

    def test_screws_back_out_away_from_the_wall(self):
        rows = {r['instance']: r for r in self.manifest['explode']}
        self.assertEqual(rows['clip']['distance'], 0)
        for ident in ('screw_1', 'screw_2'):
            self.assertAlmostEqual(rows[ident]['direction'][0], 1, places=6)
            self.assertGreater(rows[ident]['distance'], 15.0)   # longer than head + shank

    def test_each_mesh_lands_where_the_gate_placed_it(self):
        """Mesh (local frame) x transform reproduces the screw the gate checked: head at x=-22.45."""
        screw = next(i for i in self.manifest['instances'] if i['id'] == 'screw_1')
        mesh = trimesh.load(self.out / screw['mesh'], force='mesh')
        t = screw['transform']
        matrix = np.eye(4)
        matrix[:3, :3] = quaternion_matrix(t['quaternion'])
        matrix[:3, 3] = t['position']
        lo, hi = mesh.copy().apply_transform(matrix).bounds
        self.assertAlmostEqual(lo[0], -22.45 - 12.0, places=2)
        self.assertAlmostEqual(hi[0], -22.45 + 3.0, places=2)
        self.assertAlmostEqual((lo[2] + hi[2]) / 2, 8.0, places=2)
        for i in self.manifest['instances']:
            self.assertTrue((self.out / i['mesh']).is_file(), i['mesh'])

    def test_steps_name_the_joints_they_complete_with_a_callout_and_tool(self):
        last = self.manifest['steps'][-1]
        self.assertEqual(sorted(last['joints']), ['screw_1_fastener', 'screw_2_fastener'])
        self.assertEqual(last['tool'], 'hex key')
        self.assertIn('2 ×', last['callout'])


class StackManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp())
        evaluate(STACK / 'assembly.py', STACK, out=cls.out)
        cls.manifest = json.loads((cls.out / MANIFEST).read_text())

    def test_the_lid_is_clamped_to_the_base_through_the_insert(self):
        self.assertTrue(validate(self.manifest))
        parents = {i['id']: i['parent'] for i in self.manifest['instances']}
        self.assertEqual(parents, {'base': None, 'lid': 'base', 'insert': 'base', 'screw': 'lid'})
        clamp = next(j for j in self.manifest['joints'] if j['child'] == 'lid')
        self.assertEqual((clamp['type'], clamp['role'], clamp['parent']), ('fixed', 'clamp', 'base'))

    def test_exploded_order_is_base_insert_lid_screw_going_up(self):
        z = {r['instance']: r['offset'][2] for r in self.manifest['explode']}
        self.assertEqual(z['base'], 0)
        self.assertLess(z['base'], z['insert'])
        self.assertLess(z['insert'], z['lid'])
        self.assertLess(z['lid'], z['screw'])

    def test_press_step_uses_a_soldering_iron(self):
        press = next(s for s in self.manifest['steps'] if 'insert' in s['part_ids'])
        self.assertEqual((press['tool'], press['joints']), ('soldering iron', ['insert_press']))

    def test_a_failing_assembly_still_gets_a_manifest_marked_failing(self):
        with tempfile.TemporaryDirectory() as out:
            report = evaluate(STACK / 'assembly.py', STACK, {'lid_gap': -1.0}, out=Path(out))
            manifest = json.loads((Path(out) / MANIFEST).read_text())
            self.assertFalse(report['pass'])
            self.assertFalse(manifest['pass'])
            self.assertTrue(validate(manifest))

    def test_an_assembly_that_does_not_build_writes_no_manifest(self):
        folder = Path(tempfile.mkdtemp())
        (folder / 'assembly.py').write_text('PARAMS = {}\n\ndef assemble(asm):\n    raise RuntimeError("boom")\n')
        with tempfile.TemporaryDirectory() as out:
            report = run_gate(folder / 'assembly.py', folder, Path(out))
            self.assertNotIn('manifest', report)
            self.assertFalse((Path(out) / MANIFEST).exists())

    def test_run_gate_writes_the_manifest_and_meshes(self):
        with tempfile.TemporaryDirectory() as out:
            report = run_gate(STACK / 'assembly.py', STACK, Path(out))
            self.assertEqual(report['manifest'], MANIFEST)
            self.assertTrue(validate(json.loads((Path(out) / MANIFEST).read_text())))
            self.assertEqual(sorted(p.name for p in (Path(out) / 'meshes').iterdir()),
                             ['base.stl', 'insert.stl', 'lid.stl', 'screw.stl'])


class Validator(unittest.TestCase):
    """Every refusal the schema and the cross-reference checks make, one broken copy each."""

    @classmethod
    def setUpClass(cls):
        cls.good = json.loads(FIXTURE.read_text())

    def broken(self, change):
        data = copy.deepcopy(self.good)
        change(data)
        with self.assertRaises(ManifestError):
            validate(data)

    def instance(self, data, ident):
        return next(i for i in data['instances'] if i['id'] == ident)

    def test_fixture_is_valid(self):
        self.assertTrue(validate(self.good))

    def test_wrong_schema_version_or_units(self):
        self.broken(lambda d: d.update(schema_version=2))
        self.broken(lambda d: d.update(units='inch'))

    def test_duplicate_ids(self):
        self.broken(lambda d: self.instance(d, 'screw_2').update(id='screw_1'))

    def test_unknown_parent_or_a_cycle(self):
        self.broken(lambda d: self.instance(d, 'screw_1').update(parent='ghost'))
        def cycle(d):
            self.instance(d, 'clip').update(parent='screw_1')
        self.broken(cycle)

    def test_joint_with_a_missing_instance_or_disagreeing_with_the_tree(self):
        self.broken(lambda d: d['joints'][0].update(child='ghost'))
        self.broken(lambda d: d['joints'][0].update(parent='screw_2'))

    def test_non_finite_transform_or_non_unit_axis(self):
        self.broken(lambda d: self.instance(d, 'clip')['transform'].update(position=[math.nan, 0, 0]))
        self.broken(lambda d: self.instance(d, 'clip')['transform'].update(quaternion=[0, 0, 0, 2]))
        self.broken(lambda d: d['joints'][0].update(axis=[2, 0, 0]))
        self.broken(lambda d: d['explode'][1].update(direction=[0, 0, 0]))

    def test_bad_range_or_rest_outside_it(self):
        self.broken(lambda d: d['joints'][0].update(range=[5, 1]))
        self.broken(lambda d: d['joints'][0].update(range=[1, 5], rest=0))

    def test_step_that_skips_or_repeats_an_instance(self):
        self.broken(lambda d: d['steps'][-1]['part_ids'].pop())
        self.broken(lambda d: d['steps'][-1]['part_ids'].append('clip'))

    def test_step_naming_an_unknown_joint(self):
        self.broken(lambda d: d['steps'][-1]['joints'].append('ghost_fastener'))

    def test_bom_quantity_mismatch_or_missing_instance(self):
        self.broken(lambda d: d['bom'][1].update(quantity=3))
        def drop(d):
            d['bom'][1]['part_ids'].pop()
            d['bom'][1]['quantity'] = 1
        self.broken(drop)

    def test_explode_must_cover_each_instance_once(self):
        self.broken(lambda d: d['explode'].pop())

    def test_mesh_path_must_stay_inside_the_output_folder(self):
        self.broken(lambda d: self.instance(d, 'clip').update(mesh='../../etc/passwd.stl'))


if __name__ == '__main__':
    unittest.main()
