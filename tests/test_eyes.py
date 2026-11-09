"""Eyes (#79): the harness writes instruments the agent can read back after every build.

Real `magic.py check --no-sweep` runs on small fixtures, about 20 s.

    .venv/bin/python -m unittest tests.test_eyes
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.eyes import overhang_classes, OVERHANG_CLASSES

PYTHON = ROOT / ".venv" / "bin" / "python"
METRIC_KEYS = {"bbox", "volume_mm3", "overhang_brief_pct", "support_risk_pct", "min_wall_mm",
               "min_wall_where", "unsupported_area_mm2", "bed_contact_mm2"}


def check(design, out):
    proc = subprocess.run([str(PYTHON), str(ROOT / "magic.py"), "check", str(design), "--no-sweep", "--out", str(out)],
                          cwd=ROOT, capture_output=True, text=True, timeout=300)
    return proc.returncode, json.loads((Path(out) / "report.json").read_text())


class OverhangClassesTest(unittest.TestCase):
    def test_mushroom_ceiling_is_support_risk_and_base_is_bed(self):
        stem = trimesh.creation.box((10, 10, 40))
        stem.apply_translation((0, 0, 20))
        cap = trimesh.creation.box((40, 40, 10))
        cap.apply_translation((0, 0, 45))
        mesh = trimesh.util.concatenate([stem, cap])
        classes = overhang_classes(mesh)
        areas = {name: float(mesh.area_faces[classes == i].sum()) for i, (name, _) in enumerate(OVERHANG_CLASSES)}
        self.assertAlmostEqual(areas["bed"], 100.0, places=3)
        self.assertAlmostEqual(areas["needs support (0-45 deg)"], 1600.0, places=3)
        self.assertGreater(areas["up or vertical"], 0)
        self.assertEqual(len(classes), len(mesh.faces))


class ArtefactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.code, cls.report = check(ROOT / "tests/fixtures/named_features.py", Path(cls.tmp.name) / "named")
        cls.fail_code, cls.fail_report = check(ROOT / "tests/fixtures/ceiling.py", Path(cls.tmp.name) / "ceiling")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_report_lists_every_artefact_and_files_exist(self):
        self.assertEqual(self.code, 0, self.report["gates"])
        art = self.report["artefacts"]
        self.assertEqual(set(art["views"]), {"iso", "top", "front", "side"})
        files = [*art["views"].values(), art["overhang_heatmap"], art["design_section"],
                 *(s["path"] for s in art["sections"]), *art["face_maps"].values()]
        for path in files:
            self.assertTrue(Path(path).is_file() and Path(path).stat().st_size > 0, path)
        self.assertTrue(Path(art["manifest"]).is_file())
        self.assertEqual(json.loads(Path(art["manifest"]).read_text())["views"], art["views"])

    def test_sections_cover_thinnest_wall_and_each_named_feature(self):
        names = [s["name"] for s in self.report["artefacts"]["sections"]]
        self.assertEqual(names[0], "thinnest wall")
        self.assertIn("lid pocket", names)
        self.assertIn("mount hole", names)
        for section in self.report["artefacts"]["sections"]:
            self.assertIn(section["axis"], "XYZ")

    def test_face_map_and_metrics(self):
        art = self.report["artefacts"]
        faces = json.loads(Path(art["face_maps"]["plate"]).read_text())
        self.assertEqual(set(faces["features"]), {"lid pocket", "mount hole"})
        metrics = art["metrics"]["plate"]
        self.assertTrue(METRIC_KEYS <= set(metrics), set(metrics))
        self.assertEqual([round(s, 3) for s in metrics["bbox"]["size"]], [36.0, 36.0, 12.0])
        self.assertGreater(metrics["volume_mm3"], 0)
        self.assertGreater(metrics["min_wall_mm"], 0)

    def test_gates_are_unchanged_and_nothing_printable_is_kept(self):
        statuses = {g["name"]: g["status"] for g in self.report["gates"]}
        self.assertEqual(statuses["5 Exports"], "NOT RUN")
        out = Path(self.tmp.name) / "named"
        self.assertEqual(list(out.rglob("*.stl")) + list(out.rglob("*.step")), [])

    def test_failing_design_still_gets_artefacts_and_still_fails(self):
        self.assertEqual(self.fail_code, 1)
        printability = next(g for g in self.fail_report["gates"] if g["name"] == "3 Printability")
        self.assertEqual(printability["status"], "FAIL")
        art = self.fail_report["artefacts"]
        self.assertTrue(Path(art["overhang_heatmap"]).is_file())
        self.assertGreater(art["metrics"]["part"]["unsupported_area_mm2"], 1000)
        out = Path(self.tmp.name) / "ceiling"
        self.assertEqual(list(out.rglob("*.stl")) + list(out.rglob("*.step")), [])


if __name__ == "__main__":
    unittest.main()
