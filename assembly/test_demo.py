import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from assembly.demo import get_demo, validate

ROOT = Path(__file__).resolve().parent.parent


class AssemblyTests(unittest.TestCase):
    def test_instances_steps_bom_and_source_snapshot(self):
        data = get_demo(ROOT)
        self.assertTrue(validate(data))
        self.assertEqual(len(data['parts']), 3)
        self.assertEqual([x['quantity'] for x in data['bom']], [1, 2])
        self.assertEqual([x['position'] for x in data['parts'][1:]], [[-22.45, 0, 8], [-22.45, 0, 24]])
        self.assertTrue(all(x['mesh_available'] for x in data['parts']))
        self.assertTrue(data['provenance']['source_matches_snapshot'])
        self.assertTrue(data['provenance']['report_matches_snapshot'])
        self.assertFalse(data['provenance']['physical_assembly_tested'])
        self.assertFalse(data['warnings'])

    def test_duplicate_or_missing_step_is_rejected(self):
        data = get_demo(ROOT)
        broken = copy.deepcopy(data)
        broken['steps'][1]['part_ids'] = ['screw_1', 'screw_1']
        with self.assertRaises(ValueError): validate(broken)
        broken = copy.deepcopy(data)
        broken['parts'][1]['position'] = [float('nan'), 0, 0]
        with self.assertRaises(ValueError): validate(broken)
        broken = copy.deepcopy(data)
        broken['bom'][1]['quantity'] = 1
        with self.assertRaises(ValueError): validate(broken)

    def test_missing_or_changed_source_is_not_presented_as_current(self):
        hashes = json.loads((ROOT / 'assembly/demo_hashes.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in hashes:
                src, dst = ROOT / name, root / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
            (root / 'designs/holder_clip.py').write_text('changed')
            (root / 'assembly/assets/m3_socket_head.stl').unlink()
            data = get_demo(root)
            self.assertFalse(data['provenance']['source_matches_snapshot'])
            self.assertFalse(data['parts'][1]['mesh_available'])
            self.assertTrue(any('changed' in x for x in data['warnings']))
            self.assertTrue(any('missing' in x for x in data['warnings']))

    def test_reloaded_holder_clear_of_reference_fasteners(self):
        # Test the same simplified envelope in the saved STEP frame. No wall or
        # dynamic tool path is implied, and this is not a physical fit test.
        from build123d import Align, Cylinder, Pos, Rot, import_step
        clip = import_step(str(ROOT / 'runs/holder_clip/holder_clip.step'))
        for z in (8, 24):
            head = Pos(-22.45 + 1.5, 0, z) * Rot(0, 90, 0) * Cylinder(2.75, 3, align=(Align.CENTER,)*3)
            shaft = Pos(-22.45 - 6, 0, z) * Rot(0, 90, 0) * Cylinder(1.5, 12, align=(Align.CENTER,)*3)
            intersection = clip & (head + shaft)
            self.assertLess(0 if intersection is None else intersection.volume, 1e-5)


if __name__ == '__main__': unittest.main()
