#!/usr/bin/env python
"""Library tests, harness negative controls, eval-brief schema. No pytest in the venv.

    .venv/bin/python tests/run_tests.py
"""
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import trimesh
from build123d import Align, Box, Pos

from harness.brief import load_brief
from harness.printability import check_stl, min_feature, overhang_metrics
from library import counterbored_hole, heatset_boss, snap_cantilever, standard_parts

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail}")


def raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ValueError:
        return True
    return False


def test_database():
    db = standard_parts()
    check("db 608 bearing", (db["bearings"]["608"]["bore"], db["bearings"]["608"]["od"],
                             db["bearings"]["608"]["width"]) == (8, 22, 7))
    check("db NEMA17 / gridfinity", db["motor_mounts"]["NEMA17"]["hole_spacing"] == 31
          and db["grids"]["gridfinity"]["pitch"] == 42)
    check("db 2020 slot", db["extrusions"]["2020"]["slot_width"] == 6)
    check("db sizes", set(db["screws"]) == {"M2.5", "M3", "M4", "M5"} and set(db["heatset_inserts"]) == {"M2.5", "M3", "M4"})


def test_counterbored_hole():
    for screw, spec in standard_parts()["screws"].items():
        thickness = spec["counterbore_depth"] + spec["head_height"]
        plate = Box(40, 40, thickness, align=(Align.CENTER, Align.CENTER, Align.MAX))
        cut = plate - counterbored_hole(screw, depth=thickness)
        removed = math.pi / 4 * (spec["counterbore_dia"] ** 2 * spec["counterbore_depth"]
                                 + spec["clearance"] ** 2 * (thickness - spec["counterbore_depth"]))
        delta = plate.volume - cut.volume - removed
        check(f"counterbored_hole {screw}", cut.is_valid and abs(delta) < 0.01, f"volume delta {delta:.4f}")
        teardrop = plate - counterbored_hole(screw, depth=thickness, teardrop=True)
        check(f"counterbored_hole {screw} teardrop", teardrop.is_valid and teardrop.volume < cut.volume)
    check("counterbored_hole too thin raises", raises(counterbored_hole, "M4", depth=3.0))
    check("counterbored_hole unknown screw raises", raises(counterbored_hole, "M7"))


def test_heatset_boss():
    for screw, spec in standard_parts()["heatset_inserts"].items():
        boss = heatset_boss(screw)
        depth = spec["insert_length"] + spec["hole_extra_depth"]
        height = depth + spec["floor"]
        expect = math.pi / 4 * (spec["boss_od"] ** 2 * height - spec["hole_dia"] ** 2 * depth)
        check(f"heatset_boss {screw}", boss.is_valid and abs(boss.volume - expect) < 0.01,
              f"volume delta {boss.volume - expect:.4f}")
        check(f"heatset_boss {screw} wall > insert", spec["boss_od"] > spec["insert_od"] > spec["hole_dia"])
    check("heatset_boss short raises", raises(heatset_boss, "M3", height=5.0))
    check("heatset_boss M5 not in DB raises", raises(heatset_boss, "M5"))


def test_snap_cantilever():
    for args in [(8, 3, 1, 0.3), (20, 8, 2, 1.0), (40, 20, 4, 4.0)]:
        snap = snap_cantilever(*args)
        box = snap.bounding_box()
        length, width, thickness, deflection = args
        check(f"snap_cantilever {args}", snap.is_valid and abs(box.size.Z - width) < 1e-6
              and box.max.X > length, f"volume {snap.volume:.1f}")
    plain = 20 * 2 * 8
    filleted = snap_cantilever(20, 8, 2, 1.0)
    check("snap_cantilever flexes in layer plane", abs(filleted.bounding_box().size.Z - 8) < 1e-6
          and filleted.volume > plain)
    check("snap_cantilever overstrain raises", raises(snap_cantilever, 8, 5, 4, 4))
    check("snap_cantilever out of range raises", raises(snap_cantilever, 5, 5, 2, 1))


def test_metrics():
    """Known meshes against hand-computed answers."""
    box = trimesh.creation.box((10, 10, 10))
    m = overhang_metrics(box)
    check("flat base: no overhang", m["overhang_brief_pct"] == 0 and m["support_risk_pct"] == 0
          and abs(m["bed_contact_mm2"] - 100) < 1e-6)
    for wall in (1.0, 2.0, 5.0):
        plate = trimesh.creation.box((wall, 40, 40))
        reading = min_feature(plate)
        check(f"min_feature on {wall} mm wall", abs(reading["mm"] - wall) <= reading["resolution_mm"],
              f"read {reading['mm']:.1f}")
    corner = trimesh.creation.box((30, 30, 30))
    check("min_feature: a plain block is not thin", min_feature(corner)["mm"] > 10)


def magic(*args):
    return subprocess.run([sys.executable, str(ROOT / "magic.py"), *args], cwd=ROOT,
                          capture_output=True, text=True).returncode


def expect_harness(name, fixture, code, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        got = magic("check", f"tests/fixtures/{fixture}.py", "--out", tmp, *extra)
        report = (Path(tmp) / "report.md").read_text() if (Path(tmp) / "report.md").exists() else ""
        needle = name.split("|")[1] if "|" in name else ""
        check(f"harness: {name.split('|')[0]}", got == code and needle in report, f"exit {got}")


def test_harness():
    expect_harness("sweep fails a defaults-only design|only works at the default", "only_default", 1)
    expect_harness("sweep flags a dead param|Dead params: extra", "dead_param", 1)
    expect_harness("lint fails a hard-coded dimension|literal 37.5", "hardcoded", 1)
    expect_harness("execute captures a traceback|kernel exploded", "crash", 1)
    expect_harness("execute times out a hang|timeout after", "hang", 1, "--timeout", "40")
    expect_harness("geometry fails two disjoint solids|2 solids, expected 1", "two_bodies", 1)
    expect_harness("geometry fails part overlap|overlap", "overlap_parts", 1)
    expect_harness("printability catches a flat ceiling|support_risk_pct", "ceiling", 1)
    expect_harness("printability fails bed overflow|exceeds bed", "oversize", 1)
    expect_harness("dimension off by 0.5 mm fails|width: measured", "wrong_dim", 1,
                   "--brief", "tests/fixtures/wrong_dim.yaml")
    expect_harness("two-part design with a gap passes|Overlap a / b", "good_two_parts", 0)
    code = subprocess.run([sys.executable, str(ROOT / "magic.py"), "sweep", "tests/fixtures/only_default.py",
                           "--samples", "2", "--out", tempfile.gettempdir() + "/magic_cap"],
                          cwd=ROOT, capture_output=True, text=True).returncode
    check("too few --samples is refused", code == 2, f"exit {code}")
    expect_harness("--no-sweep is opt-in and says so|--no-sweep: parametric behaviour not verified",
                   "only_default", 0, "--no-sweep")
    with tempfile.TemporaryDirectory() as tmp:
        code = magic("check", "tests/fixtures/only_default.py", "--no-sweep", "--out", tmp)
        import json
        report = json.loads((Path(tmp) / "report.json").read_text())
        check("unswept check is labelled draft", code == 0 and report["verification"] == "draft"
              and "(draft)" in (Path(tmp) / "report.md").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        other = Path(tmp) / "my-model.3mf"
        other.write_bytes(b"user data")
        code = magic("run", "tests/fixtures/hardcoded.py", "--out", tmp)
        check("failed run preserves unrelated 3MF files", code == 1 and other.read_bytes() == b"user data")
    with tempfile.TemporaryDirectory() as tmp:
        code = magic("run", "tests/fixtures/only_default.py", "--no-sweep", "--out", tmp)
        check("run --no-sweep is refused, no unswept exports", code == 2 and not list(Path(tmp).iterdir()), f"exit {code}")


def test_briefs():
    for path in sorted((ROOT / "evals" / "briefs").glob("*.yaml")) + [ROOT / "briefs" / "wall_bracket.yaml"]:
        brief = load_brief(path)
        check(f"brief schema: {path.name}", brief["name"] and brief["params"])


def test_studio_fixtures():
    """The Studio test meshes are still the committed runs: each part's size matches its report's bbox,
    and the parts' volumes add up to the report's volume. Rerun ui/tests/make_fixtures.py if this fails."""
    import json
    fixtures = ROOT / "ui" / "tests" / "fixtures" / "models"
    for folder in sorted(p for p in fixtures.iterdir() if p.is_dir()):
        report = json.loads((ROOT / "runs" / folder.name / "report.json").read_text())["geometry"]
        meshes = {stl.stem: trimesh.load_mesh(stl) for stl in sorted(folder.glob("*.stl"))}
        sizes_ok = set(meshes) == set(report["bbox"]) and all(
            max(abs(a - b) for a, b in zip(mesh.extents, report["bbox"][name])) <= 0.05 for name, mesh in meshes.items())
        volume = sum(mesh.volume for mesh in meshes.values())
        check(f"studio fixture matches its run: {folder.name}",
              sizes_ok and abs(volume - report["volume"]) <= 0.01 * report["volume"], f"volume {volume:.0f} vs {report['volume']:.0f}")


if __name__ == "__main__":
    for test in (test_database, test_counterbored_hole, test_heatset_boss, test_snap_cantilever,
                 test_metrics, test_briefs, test_studio_fixtures, test_harness):
        print(f"--- {test.__name__}")
        test()
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)
