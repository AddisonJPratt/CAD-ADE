"""Patterns and ingrained surface textures (#52).

    .venv/bin/python -m unittest tests.test_textures
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import trimesh
from build123d import Align, Box, Cylinder, Edge, Pos, export_stl

from harness.printability import overhang_metrics
from library import textures as tx
from library.engineering import FEATURES, FeatureError, min_wall, propose, rules

UP = (Align.CENTER, Align.CENTER, Align.MIN)


def wall():
    """A 50 x 8 x 30 upright plate; its front (-Y) face is vertical."""
    return Box(50, 8, 30, align=UP)


def knob():
    return Cylinder(12, 16, align=UP)


class Rules(unittest.TestCase):
    def test_bounds_come_from_the_nozzle(self):
        r = tx.texture_rules()
        nozzle = rules()["nozzle"]
        self.assertAlmostEqual(r["min_feature"], nozzle)
        self.assertAlmostEqual(r["min_pitch"], 2 * nozzle)
        self.assertAlmostEqual(r["brep_min_pitch"], 2 * min_wall())
        self.assertAlmostEqual(r["min_depth"], nozzle * tx.standard_parts()["texture_rules"]["min_depth_nozzles"])
        self.assertLess(r["flank_rate"], 1.0)   # flanks steeper than 45 deg from the surface never

    def test_registered_with_engineering_features(self):
        for name in ("knurl", "diamond_knurl", "ribbing", "hex_texture", "emboss_text", "emboss_outline", "pattern"):
            self.assertIn(name, FEATURES)


class Patterns(unittest.TestCase):
    def test_linear_is_centred_and_spaced(self):
        pts = tx.linear_pattern(4, 5.0)
        self.assertEqual(len(pts), 4)
        self.assertAlmostEqual(sum(u for u, _ in pts), 0.0)
        self.assertAlmostEqual(pts[1][0] - pts[0][0], 5.0)

    def test_linear_at_an_angle(self):
        pts = tx.linear_pattern(2, 10.0, angle=90)
        self.assertAlmostEqual(abs(pts[1][1] - pts[0][1]), 10.0)
        self.assertAlmostEqual(pts[1][0] - pts[0][0], 0.0)

    def test_grid(self):
        pts = tx.grid_pattern(3, 2, 4.0, 6.0)
        self.assertEqual(len(pts), 6)
        us, vs = sorted({round(u, 6) for u, _ in pts}), sorted({round(v, 6) for _, v in pts})
        self.assertEqual(us, [-4.0, 0.0, 4.0])
        self.assertEqual(vs, [-3.0, 3.0])

    def test_circular_full_circle_does_not_double_the_seam(self):
        pts = tx.circular_pattern(6, 10.0)
        self.assertEqual(len(pts), 6)
        for u, v in pts:
            self.assertAlmostEqual(math.hypot(u, v), 10.0)
        arc = tx.circular_pattern(3, 10.0, sweep=90)   # partial arc includes both ends
        self.assertAlmostEqual(math.degrees(math.atan2(arc[-1][1], arc[-1][0])), 90.0)

    def test_path_pattern_spaces_along_the_edge(self):
        locs = tx.path_pattern(Edge.make_line((0, 0, 0), (30, 0, 0)), 4)
        xs = [loc.position.X for loc in locs]
        self.assertEqual(len(xs), 4)
        self.assertAlmostEqual(xs[1] - xs[0], 10.0)

    def test_bad_counts_and_spacing_refused(self):
        with self.assertRaises(FeatureError):
            tx.linear_pattern(0, 5.0)
        with self.assertRaises(FeatureError):
            tx.linear_pattern(3, 0.0)
        with self.assertRaises(FeatureError):
            tx.grid_pattern(2, 2, 5.0, -1.0)
        with self.assertRaises(FeatureError):
            tx.circular_pattern(4, 0.0)

    def test_pattern_places_bosses_on_a_top_face(self):
        plate = Box(40, 30, 4, align=UP)
        stud = Cylinder(2, 3, align=UP)
        p = tx.pattern(plate, (0, 0, 4), stud, tx.grid_pattern(3, 2, 10.0, 10.0))
        self.assertAlmostEqual(p.volume_delta_mm3, 6 * stud.volume, delta=1.0)
        self.assertLessEqual(p.adds_overhang_mm2, rules()["overhang_tolerance_mm2"])
        self.assertEqual(p.derived["instances"]["value"], 6)

    def test_pattern_cut_makes_pockets(self):
        plate = Box(40, 30, 4, align=UP)
        hole = Cylinder(1.5, 2, align=(Align.CENTER, Align.CENTER, Align.MAX))
        p = tx.pattern(plate, (0, 0, 4), hole, tx.linear_pattern(3, 8.0), cut=True)
        self.assertLess(p.volume_delta_mm3, -3 * hole.volume * 0.9)

    def test_overlapping_instances_refused(self):
        plate = Box(40, 30, 4, align=UP)
        stud = Cylinder(2, 3, align=UP)
        with self.assertRaisesRegex(FeatureError, "web"):
            tx.pattern(plate, (0, 0, 4), stud, tx.linear_pattern(3, 4.2))

    def test_instances_off_the_face_refused(self):
        plate = Box(20, 20, 4, align=UP)
        stud = Cylinder(2, 3, align=UP)
        with self.assertRaisesRegex(FeatureError, "off the face"):
            tx.pattern(plate, (0, 0, 4), stud, tx.linear_pattern(3, 12.0))


class BrepTextures(unittest.TestCase):
    def test_straight_knurl_on_a_wall_adds_no_downward_area(self):
        part = wall()
        p = propose("knurl", part, face=(0, -4, 15), pitch=3.0, depth=0.8)
        self.assertEqual(p.derived["mode"]["value"], "brep")
        self.assertLess(p.volume_delta_mm3, 0)
        with tempfile.TemporaryDirectory() as tmp:
            before, after = Path(tmp) / "a.stl", Path(tmp) / "b.stl"
            export_stl(part, str(before))
            export_stl(p.shape, str(after))
            down = lambda f: overhang_metrics(trimesh.load(str(f)))["overhang_brief_pct"]
            self.assertAlmostEqual(down(after), down(before), delta=0.5)

    def test_diamond_knurl_on_a_vertical_face_is_brep_and_self_supporting(self):
        p = propose("diamond_knurl", wall(), face=(0, -4, 15), pitch=4.0, depth=0.8)
        self.assertEqual(p.derived["mode"]["value"], "brep")
        self.assertLess(p.volume_delta_mm3, 0)
        self.assertLessEqual(p.adds_overhang_mm2, rules()["overhang_tolerance_mm2"])
        self.assertIsNone(p.mesh_texture)

    def test_knurl_on_a_cylinder_wraps_a_whole_number_of_grooves(self):
        p = tx.knurl(knob(), (12, 0, 8), pitch=4.0, depth=0.8)
        grooves = p.derived["grooves_per_hand"]["value"]
        self.assertAlmostEqual(p.derived["pitch_wrapped"]["value"] * grooves, 2 * math.pi * 12, places=6)
        self.assertLessEqual(p.adds_overhang_mm2, rules()["overhang_tolerance_mm2"])

    def test_diamond_knurl_on_a_cylinder(self):
        p = tx.diamond_knurl(knob(), (12, 0, 8), pitch=4.0, depth=0.8)
        self.assertEqual(p.derived["mode"]["value"], "brep")
        grooves = p.derived["grooves_per_hand"]["value"]
        circumference = 2 * math.pi * 12
        self.assertAlmostEqual(p.derived["pitch_wrapped"]["value"] * grooves,
                               circumference * math.cos(math.radians(30)), places=6)
        self.assertLess(p.volume_delta_mm3, 0)
        self.assertLessEqual(p.adds_overhang_mm2, rules()["overhang_tolerance_mm2"])

    def test_straight_ribbing_on_a_wall(self):
        p = tx.ribbing(wall(), (0, -4, 15), pitch=4.0, depth=0.6)
        self.assertEqual(p.feature, "ribbing")
        self.assertGreater(p.derived["groove_floor"]["value"], 0)
        self.assertLess(p.volume_delta_mm3, 0)
        self.assertLessEqual(p.adds_overhang_mm2, rules()["overhang_tolerance_mm2"])

    def test_horizontal_ribs_on_a_wall_keep_self_supporting_roofs(self):
        # flanks rise at the self-supporting slope across the groove, so a sideways groove's
        # roof stands self_supporting_deg from vertical: no support needed
        p = tx.ribbing(wall(), (0, -4, 15), pitch=4.0, depth=0.6, angle=90)
        self.assertLessEqual(p.adds_overhang_mm2, rules()["overhang_tolerance_mm2"])

    def test_steep_flank_would_need_support(self):
        # the same horizontal groove, cut square, has a flat ceiling: the shared print check refuses it
        from build123d import Box as B
        with self.assertRaisesRegex(FeatureError, "overhang"):
            tx.pattern(wall(), (0, -4, 15), Pos(0, 0, -0.5) * B(4, 1, 1), tx.linear_pattern(3, 8.0), cut=True)

    def test_hex_texture_on_a_wall_slants_its_roofs(self):
        p = tx.hex_texture(wall(), (0, -4, 15), cell=6.0, depth=0.8)
        self.assertLess(p.volume_delta_mm3, 0)
        self.assertLessEqual(p.adds_overhang_mm2, rules()["overhang_tolerance_mm2"])
        self.assertGreater(p.derived["cells"]["value"], 4)

    def test_engraved_text_on_top_face(self):
        plate = Box(60, 20, 4, align=UP)
        p = tx.emboss_text(plate, (0, 0, 4), "MAGIC", size=8.0, depth=0.6, raised=False)
        self.assertLess(p.volume_delta_mm3, 0)
        raised = tx.emboss_text(plate, (0, 0, 4), "MAGIC", size=8.0, depth=0.6)
        self.assertGreater(raised.volume_delta_mm3, 0)

    def test_text_on_a_wall_is_printable(self):
        for raised in (False, True):
            p = tx.emboss_text(wall(), (0, -4, 15), "AEB", size=14.0, depth=0.8, raised=raised)
            self.assertLessEqual(p.adds_overhang_mm2, rules()["overhang_tolerance_mm2"])
            self.assertGreater(p.derived["slant"]["value"], 1.0)

    def test_outline_logo(self):
        from build123d import Circle, Rectangle
        plate = Box(40, 40, 4, align=UP)
        logo = Circle(8) - Rectangle(4, 20)
        p = tx.emboss_outline(plate, (0, 0, 4), logo, depth=0.8)
        self.assertGreater(p.volume_delta_mm3, 0)

    def test_text_too_small_for_the_nozzle_refused(self):
        plate = Box(60, 20, 4, align=UP)
        with self.assertRaisesRegex(FeatureError, "nozzle"):
            tx.emboss_text(plate, (0, 0, 4), "MAGIC", size=1.5, depth=0.6)

    def test_downward_face_refused(self):
        with self.assertRaisesRegex(FeatureError, "downward"):
            tx.knurl(wall(), (0, 0, 0), pitch=4.0, depth=0.8)

    def test_json_ready(self):
        p = tx.ribbing(wall(), (0, -4, 15), pitch=4.0, depth=0.6)
        self.assertEqual(json.loads(json.dumps(p.to_dict()))["feature"], "ribbing")


class Printability(unittest.TestCase):
    """The texture gate: nothing below the nozzle's minimum feature size."""

    def test_pitch_below_two_lines_refused(self):
        with self.assertRaisesRegex(FeatureError, "nozzle"):
            tx.knurl(wall(), (0, -4, 15), pitch=0.6, depth=0.2)

    def test_depth_below_minimum_refused(self):
        with self.assertRaisesRegex(FeatureError, "depth"):
            tx.knurl(wall(), (0, -4, 15), pitch=3.0, depth=0.05)

    def test_depth_past_the_flank_refused(self):
        # a V groove deeper than its flank allows would need flanks steeper than self-supporting
        with self.assertRaisesRegex(FeatureError, "depth"):
            tx.knurl(wall(), (0, -4, 15), pitch=2.0, depth=1.5)

    def test_rib_too_wide_for_its_pitch_refused(self):
        with self.assertRaisesRegex(FeatureError, "floor"):
            tx.ribbing(wall(), (0, -4, 15), pitch=3.0, depth=0.8, rib=2.5)

    def test_rib_below_nozzle_refused(self):
        with self.assertRaisesRegex(FeatureError, "nozzle"):
            tx.ribbing(wall(), (0, -4, 15), pitch=3.0, depth=0.4, rib=0.2)

    def test_hex_web_below_nozzle_refused(self):
        with self.assertRaisesRegex(FeatureError, "web"):
            tx.hex_texture(wall(), (0, -4, 15), cell=4.0, depth=0.4, web=0.2)


class MeshTextures(unittest.TestCase):
    """Fine textures go to the export mesh instead of B-rep."""

    def setUp(self):
        tx.reset_mesh_textures()

    def test_fine_knurl_is_deferred_to_the_mesh(self):
        part = knob()
        p = tx.knurl(part, (12, 0, 8), pitch=1.2, depth=0.3)
        self.assertEqual(p.derived["mode"]["value"], "mesh")
        self.assertIs(p.shape, part)
        self.assertEqual(p.volume_delta_mm3, 0)
        self.assertTrue(any("fuzzy skin" in n for n in p.notes))
        self.assertEqual(len(tx.declared_mesh_textures()), 1)
        self.assertEqual(json.loads(json.dumps(p.to_dict()))["mesh_texture"]["kind"], "knurl")

    def test_applying_a_mesh_texture_keeps_the_stl_watertight(self):
        part = knob()
        p = tx.knurl(part, (12, 0, 8), pitch=1.2, depth=0.3)
        with tempfile.TemporaryDirectory() as tmp:
            stl = Path(tmp) / "knob.stl"
            export_stl(part, str(stl), tolerance=0.01, angular_tolerance=0.1)
            before = trimesh.load(str(stl)).volume
            delta = tx.apply_mesh_textures(stl, [p.mesh_texture])
            mesh = trimesh.load(str(stl))
        self.assertTrue(mesh.is_watertight)
        self.assertEqual(mesh.body_count, 1)
        self.assertLess(delta, 0)
        self.assertAlmostEqual(mesh.volume, before + delta, delta=abs(delta) * 0.05 + 1.0)
        # displaced flanks stay self-supporting: no new support risk on the side wall
        self.assertLess(overhang_metrics(mesh)["support_risk_pct"], 1.0)

    def test_mesh_texture_on_a_wall(self):
        part = wall()
        p = tx.hex_texture(part, (0, -4, 15), cell=1.5, depth=0.3, web=0.4)
        self.assertEqual(p.derived["mode"]["value"], "mesh")
        with tempfile.TemporaryDirectory() as tmp:
            stl = Path(tmp) / "wall.stl"
            export_stl(part, str(stl), tolerance=0.01, angular_tolerance=0.1)
            delta = tx.apply_mesh_textures(stl, [p.mesh_texture])
            mesh = trimesh.load(str(stl))
        self.assertTrue(mesh.is_watertight)
        self.assertLess(delta, 0)
        self.assertLess(overhang_metrics(mesh)["support_risk_pct"], 15.0)


if __name__ == "__main__":
    unittest.main()
