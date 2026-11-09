"""Patterns and ingrained surface textures (#52): library, mesh textures, the texture gate.

    .venv/bin/python -m unittest tests.test_surface
"""
import copy
import math
import tempfile
import unittest
from pathlib import Path

import trimesh
from build123d import Align, Box, Cylinder, Pos, Rot, export_stl

from library import features as registry
from library import standard_parts
from library import surface
from library.engineering import FeatureError

ROOT = Path(__file__).resolve().parents[1]


def knob(radius=15.0, height=12.0):
    return Cylinder(radius, height, align=(Align.CENTER, Align.CENTER, Align.MIN))


def wall():
    """A 60 x 40 mm wall standing on the bed, 6 mm thick: its +Y face is vertical."""
    return Box(60, 6, 40, align=(Align.CENTER, Align.CENTER, Align.MIN))


class BoundsTest(unittest.TestCase):
    def test_bounds_come_from_the_print_rules_not_literals(self):
        rules = standard_parts()["print_rules"]
        b = surface.bounds()
        self.assertAlmostEqual(b["min_feature"], rules["nozzle"] * rules["texture_min_lines"])
        self.assertAlmostEqual(b["min_depth"], rules["layer_height"] * rules["texture_min_layers"])
        self.assertEqual(b["brep_max_cells"], rules["texture_brep_max_cells"])
        saved = dict(rules)
        try:
            rules["nozzle"] = 0.6          # a bigger nozzle raises every minimum
            self.assertAlmostEqual(surface.bounds()["min_feature"], 0.6 * rules["texture_min_lines"])
            self.assertGreater(surface.texture_ranges("knurl")["pitch"][1], 2 * 0.6 * 2 - 1e-9)
        finally:
            rules.clear()
            rules.update(saved)

    def test_texture_ranges_are_printable_at_every_corner(self):
        """A sweep over the ranges an agent writes into PARAMS never samples an unprintable texture."""
        for kind in ("knurl", "diamond", "ribbing", "hex"):
            ranges = surface.texture_ranges(kind)
            for pitch in ranges["pitch"][1:]:
                for depth in ranges["depth"][1:]:
                    self.assertEqual(surface.texture_problems(surface.texture_spec(kind, pitch, depth)), [],
                                     f"{kind} pitch {pitch} depth {depth}")
            for name in ("pitch", "depth"):
                default, low, high = ranges[name]
                self.assertTrue(low <= default <= high, f"{kind} {name} {ranges[name]}")


class PatternTest(unittest.TestCase):
    def test_linear_grid_circular_and_path_placements(self):
        line = surface.linear_pattern(4, 10.0, direction=(1, 0, 0))
        self.assertEqual([round(loc.position.X, 6) for loc in line], [-15.0, -5.0, 5.0, 15.0])
        grid = surface.grid_pattern(3, 2, 8.0, 12.0)
        self.assertEqual(len(grid), 6)
        self.assertEqual(sorted({round(loc.position.Y, 6) for loc in grid}), [-6.0, 6.0])
        ring = surface.circular_pattern(6, 20.0)
        self.assertEqual(len(ring), 6)
        self.assertTrue(all(abs(loc.position.length - 20.0) < 1e-6 for loc in ring))
        half = surface.circular_pattern(3, 20.0, sweep_deg=90)
        angles = [round(math.degrees(math.atan2(l.position.Y, l.position.X)), 6) for l in half]
        self.assertEqual(angles, [0.0, 45.0, 90.0])
        from build123d import Line
        path = surface.path_pattern(Line((0, 0, 0), (30, 0, 0)), 4)
        self.assertEqual([round(loc.position.X, 6) for loc in path], [0.0, 10.0, 20.0, 30.0])

    def test_pattern_cuts_or_adds_every_copy(self):
        plate = Box(60, 40, 4, align=(Align.CENTER, Align.CENTER, Align.MIN))
        hole = Cylinder(2.0, 10.0)
        vents = surface.pattern(plate, hole, surface.grid_pattern(4, 3, 10.0, 10.0), cut=True)
        self.assertAlmostEqual(-vents.volume_delta_mm3, 12 * math.pi * 4 * 4, delta=1.0)
        self.assertEqual(vents.derived["copies"]["value"], 12)
        pegs = surface.pattern(plate, Pos(0, 0, 4) * Cylinder(2.0, 3.0, align=(Align.CENTER, Align.CENTER, Align.MIN)),
                               surface.linear_pattern(3, 10.0))
        self.assertGreater(pegs.volume_delta_mm3, 0)

    def test_pattern_gap_below_the_minimum_feature_is_refused(self):
        plate = Box(60, 40, 4, align=(Align.CENTER, Align.CENTER, Align.MIN))
        hole = Cylinder(2.0, 10.0)
        web = surface.bounds()["min_feature"] / 2
        with self.assertRaisesRegex(FeatureError, "web"):
            surface.pattern(plate, hole, surface.linear_pattern(3, 4.0 + web), cut=True)
        with self.assertRaisesRegex(FeatureError, "count"):
            surface.linear_pattern(0, 5.0)

    def test_pattern_sweep_over_count_and_spacing(self):
        """Every count/spacing pair across the range gives one valid solid with the right copy count."""
        plate = Box(80, 30, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))
        hole = Cylinder(1.5, 10.0)
        for count in (1, 3, 6):
            for spacing in (4.0, 7.0, 10.0):
                result = surface.pattern(plate, hole, surface.linear_pattern(count, spacing), cut=True)
                self.assertTrue(result.shape.is_valid)
                self.assertAlmostEqual(-result.volume_delta_mm3, count * math.pi * 1.5 ** 2 * 3, delta=0.5)


class TextureTest(unittest.TestCase):
    def setUp(self):
        registry.reset_features()

    def test_knurl_on_an_upright_cylinder_is_brep_and_needs_no_support(self):
        part = knob()
        face = surface.pick_face(part, kind="cylinder")
        result = surface.knurl(part, face, pitch=2.0, depth=0.6)
        self.assertTrue(result.shape.is_valid)
        grooves = result.derived["grooves"]["value"]
        actual = 2 * math.pi * 15.0 / grooves
        # Each V-groove is half the pitch wide at the surface and `depth` deep: area w * d / 2.
        self.assertAlmostEqual(-result.volume_delta_mm3, grooves * (actual / 2) * 0.6 / 2 * 12.0,
                               delta=0.05 * grooves * (actual / 2) * 0.6 / 2 * 12.0)
        self.assertLessEqual(result.adds_overhang_mm2, standard_parts()["print_rules"]["overhang_tolerance_mm2"])
        self.assertAlmostEqual(result.shape.bounding_box().max.X, 15.0, delta=0.1)   # the lands stay on the surface
        self.assertGreater(len(result.shape.faces()), 40)
        declared = registry.declared_textures()
        self.assertEqual([t["kind"] for t in declared], ["knurl"])
        self.assertEqual(declared[0]["representation"], "brep")
        self.assertAlmostEqual(declared[0]["feature_width"], 1.0, delta=0.05)

    def test_knurl_on_a_top_face_cuts_full_v_grooves_without_overhang(self):
        part = Box(30, 20, 6, align=(Align.CENTER, Align.CENTER, Align.MIN))
        result = surface.knurl(part, surface.pick_face(part, facing="+Z"), pitch=2.0, depth=0.6)
        grooves = result.derived["grooves"]["value"]
        self.assertAlmostEqual(-result.volume_delta_mm3, grooves * 1.0 * 0.6 / 2 * 20, delta=0.5)
        self.assertLessEqual(result.adds_overhang_mm2, standard_parts()["print_rules"]["overhang_tolerance_mm2"])

    def test_textures_below_the_nozzle_minimum_are_refused(self):
        part = knob()
        face = surface.pick_face(part, kind="cylinder")
        tiny = surface.bounds()["min_feature"]          # pitch = one feature: ridges half that
        with self.assertRaisesRegex(FeatureError, "minimum feature"):
            surface.knurl(part, face, pitch=tiny, depth=0.5)
        with self.assertRaisesRegex(FeatureError, "depth"):
            surface.knurl(part, face, pitch=2.0, depth=surface.bounds()["min_depth"] / 2)
        with self.assertRaisesRegex(FeatureError, "minimum feature"):
            surface.text(part, surface.pick_face(part, facing="+Z"), "AB", size=2.0, depth=0.6)

    def test_diamond_hex_and_ribbing_on_a_vertical_face_print_without_support(self):
        for kind, kwargs in (("diamond", {"pitch": 3.0, "depth": 0.6}),
                             ("hex", {"pitch": 4.0, "depth": 0.6}),
                             ("ribbing", {"pitch": 3.0, "depth": 0.8})):
            with self.subTest(kind=kind):
                part = wall()
                result = surface.texture(part, surface.pick_face(part, facing="+Y"), kind, **kwargs)
                self.assertTrue(result.shape.is_valid)
                # Relief of at least a third of the face area x depth: real texture, not a sliver.
                self.assertGreater(abs(result.volume_delta_mm3), 60 * 40 * kwargs["depth"] / 3 * 0.5, kind)
                self.assertLessEqual(result.adds_overhang_mm2,
                                     standard_parts()["print_rules"]["overhang_tolerance_mm2"], kind)

    def test_embossed_and_engraved_text_on_a_top_face(self):
        part = Box(50, 20, 5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        top = surface.pick_face(part, facing="+Z")
        raised = surface.text(part, top, "MAGIC", size=8.0, depth=0.6)
        self.assertGreater(raised.volume_delta_mm3, 0)
        cut = surface.text(part, surface.pick_face(part, facing="+Z"), "MAGIC", size=8.0, depth=0.6, emboss=False)
        self.assertLess(cut.volume_delta_mm3, 0)
        self.assertAlmostEqual(cut.shape.bounding_box().max.Z, 5.0, places=3)

    def test_a_lying_cylinder_is_refused_and_too_many_cells_route_to_the_mesh(self):
        lying = Pos(0, 0, 10) * Rot(90, 0, 0) * Cylinder(10, 30)
        with self.assertRaisesRegex(FeatureError, "upright"):
            surface.knurl(lying, surface.pick_face(lying, kind="cylinder"), pitch=2.0, depth=0.6)
        big = Box(120, 120, 4, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with self.assertRaisesRegex(FeatureError, "mesh_texture"):
            surface.hex_texture(big, surface.pick_face(big, facing="+Z"), pitch=3.6, depth=0.5)
        auto = surface.texture(big, surface.pick_face(big, facing="+Z"), "hex", pitch=3.6, depth=0.5)
        self.assertEqual(registry.declared_textures()[-1]["representation"], "mesh")
        self.assertTrue(auto.shape.is_same(big) or abs(auto.volume_delta_mm3) < 1e-6)

    def test_pick_face_by_facing_kind_and_feature(self):
        part = Box(40, 30, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
        pocket = registry.feature("pocket", Pos(0, 0, 10) * Box(10, 10, 4))
        part = part - pocket
        self.assertAlmostEqual(surface.pick_face(part, facing="+Z").center().Z, 10.0)
        floor = surface.pick_face(part, facing="+Z", feature="pocket")
        self.assertAlmostEqual(floor.center().Z, 8.0)
        self.assertAlmostEqual(surface.pick_face(part, facing="-X").center().X, -20.0)
        with self.assertRaisesRegex(FeatureError, "facing"):
            surface.pick_face(part, facing="+Q")


class MeshTextureTest(unittest.TestCase):
    def test_a_fine_diamond_knurl_is_applied_to_the_exported_mesh_watertight(self):
        registry.reset_features()
        part = knob(12.0, 10.0)
        part.label = "knob"
        same = surface.mesh_texture(part, surface.pick_face(part, kind="cylinder"), "diamond", pitch=1.6, depth=0.5)
        self.assertIs(same, part)
        spec = registry.declared_textures()[0]
        self.assertEqual((spec["part"], spec["representation"]), ("knob", "mesh"))
        with tempfile.TemporaryDirectory() as tmp:
            stl = Path(tmp) / "knob.stl"
            export_stl(copy.deepcopy(part), str(stl), tolerance=0.01, angular_tolerance=0.1)
            before = trimesh.load_mesh(stl).volume
            applied = surface.apply_mesh_texture(stl, spec)
            mesh = trimesh.load_mesh(stl)
        self.assertTrue(mesh.is_watertight and mesh.is_winding_consistent)
        self.assertEqual(mesh.body_count, 1)
        self.assertLess(mesh.volume, before)
        self.assertAlmostEqual(applied["volume_delta_mm3"], mesh.volume - before, delta=1.0)
        self.assertAlmostEqual(applied["depth_measured"], 0.5, delta=0.05)


class TextureGateTest(unittest.TestCase):
    def test_gate_rejects_a_texture_below_the_minimum_feature(self):
        from harness.printability import check_textures
        fine = surface.texture_spec("knurl", 2.0, 0.6)
        self.assertEqual(check_textures([fine]), [])
        tiny = surface.texture_spec("knurl", 0.8, 0.6)
        problems = check_textures([tiny])
        self.assertTrue(any("minimum feature" in p for p in problems), problems)
        shallow = surface.texture_spec("ribbing", 2.0, 0.1)
        self.assertTrue(any("depth" in p for p in check_textures([shallow])))
        unapplied = dict(surface.texture_spec("diamond", 2.0, 0.6), representation="mesh", depth_measured=0.0)
        self.assertTrue(any("not applied" in p for p in check_textures([unapplied])))

    def test_harness_fails_gate_3_on_a_too_fine_mesh_texture(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run([sys.executable, "magic.py", "check", "tests/fixtures/textures/too_fine.py",
                                   "--out", tmp, "--no-sweep", "--timeout", "600"],
                                  cwd=ROOT, capture_output=True, text=True, timeout=900)
            report = (Path(tmp) / "report.md").read_text()
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("minimum feature", report)
        self.assertRegex(report, r"3 Printability.*FAIL")


if __name__ == "__main__":
    unittest.main()
