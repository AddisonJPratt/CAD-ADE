"""Fit checks complement, but do not replace, the project's full harness runs."""
import tempfile
import unittest
from pathlib import Path

from build123d import Align, Box, Cylinder, Pos, Rot, export_step, import_step
from designs import holder_clip, holder_cradle
from library import standard_parts


def volume_intersection(a, b):
    result = a & b
    return 0 if result is None else result.volume


def roundtrip(shape):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'part.step'
        export_step(shape, str(path))
        return import_step(str(path))


def extremes(module):
    values = module.PARAMS
    return [{k: v[i] for k, v in values.items()} for i in (0, 1, 2)]


class HolderFitTests(unittest.TestCase):
    def test_clip_object_screw_heads_and_driver(self):
        screw = standard_parts()['screws']['M3']
        for p in extremes(holder_clip):
            with self.subTest(p=p):
                s = roundtrip(holder_clip.build(**p))
                inner = p['barrel_dia'] / 2 + p['clearance']
                obj = Cylinder(p['barrel_dia'] / 2, p['clip_height'],
                               align=(Align.CENTER, Align.CENTER, Align.MIN))
                self.assertLess(volume_intersection(s, obj), 1e-5)
                for z in (p['clip_height'] / 4, p['clip_height'] * 3 / 4):
                    head_front = -inner - screw['counterbore_depth'] + screw['head_height']
                    head = Pos(head_front - screw['head_height']/2, 0, z) * Rot(0, 90, 0) * Cylinder(
                        screw['head_dia']/2, screw['head_height'], align=(Align.CENTER,)*3)
                    self.assertLess(volume_intersection(s, head), 1e-5)
                    self.assertLess(volume_intersection(obj, head), 1e-5)
                    travel_end = inner + p['wall'] * 3
                    tool = Pos((head_front + travel_end)/2, 0, z) * Rot(0, 90, 0) * Cylinder(
                        screw['tap']/2, travel_end - head_front, align=(Align.CENTER,)*3)
                    self.assertLess(volume_intersection(s, tool), 1e-5)

    def test_cradle_object_and_screw_heads(self):
        screw = standard_parts()['screws']['M3']
        for p in extremes(holder_cradle):
            with self.subTest(p=p):
                s = roundtrip(holder_cradle.build(**p))
                w = p['wall']
                obj = Pos(0, 2*w, w) * Box(p['obj_w'], p['obj_h'], p['obj_d'],
                                           align=(Align.CENTER, Align.MIN, Align.MIN))
                self.assertLess(volume_intersection(s, obj), 1e-5)
                width = p['obj_w'] + 2*p['clearance'] + 2*w
                for side in (-1, 1):
                    x = side * (width/2 + screw['head_dia'])
                    y = p['obj_h'] * 0.5 * 0.75
                    head = Pos(x, y, w) * Cylinder(screw['head_dia']/2, screw['head_height'],
                                                   align=(Align.CENTER, Align.CENTER, Align.MIN))
                    self.assertLess(volume_intersection(obj, head), 1e-5)
                    self.assertLess(volume_intersection(s, head), 1e-5)


if __name__ == '__main__':
    unittest.main()
