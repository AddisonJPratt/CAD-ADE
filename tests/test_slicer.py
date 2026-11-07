"""ElegooSlicer check: a passing part is sliced with the Centauri Carbon 2 profile.

    .venv/bin/python -m unittest tests.test_slicer

Tests that need the real slicer skip with a clear message where ElegooSlicer is not
installed. The guards that no code path sends a print job always run.
"""
import json
import re
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
import tempfile

from engine import slicer
from engine.api import make_server
from engine.projects import run_project
from harness.evidence import apply_slice

ROOT = Path(__file__).resolve().parent.parent
SLICER = slicer.find_slicer()
NEEDS_SLICER = unittest.skipUnless(SLICER, slicer.MISSING)

CUBE = '''from build123d import Box, Align
PARAMS = {"side": (20.0, 15.0, 25.0)}  # mm, a plain block that needs no supports
def build(side):
    part = Box(side, side, side / 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part.label = "block"
    return part
'''


def claims(*tiers):
    return [{"claim": "3 Printability", "tier": "computed", "status": "PASS", "detail": "ok"},
            {"claim": "Printability metrics: block", "tier": "computed", "status": "PASS", "detail": "ok"},
            {"claim": "2 Geometry", "tier": "computed", "status": "PASS", "detail": "ok"},
            {"claim": "Physical fit and performance", "tier": "needs physical test",
             "status": "NOT TESTED", "detail": "none"}]


def sliced(**overrides):
    result = {"ran": True, "ok": True, "slicer": "ElegooSlicer 1.5.2.2", "printer": "Elegoo Centauri Carbon 2 0.4 nozzle",
              "process": "0.20mm Standard @Elegoo CC2 0.4 nozzle", "material": "PLA",
              "filament": "Elegoo PLA @ECC2", "print_seconds": 565, "filament_m": 0.99, "filament_g": 2.95,
              "supports_allowed": False, "support_used": False, "support_filament_mm": 0.0, "layers": 50,
              "outside": False, "three_mf": "block/block.3mf", "problems": []}
    result.update(overrides)
    return result


class ClaimUpgradeTest(unittest.TestCase):
    """Matching claims move to slicer-checked only when the slice backs them."""

    def test_clean_slice_upgrades_printability_claims(self):
        upgraded = apply_slice(claims(), sliced())
        tiers = {c["claim"]: c["tier"] for c in upgraded}
        self.assertEqual(tiers["3 Printability"], "slicer-checked")
        self.assertEqual(tiers["Printability metrics: block"], "slicer-checked")
        self.assertEqual(tiers["2 Geometry"], "computed")
        self.assertEqual(tiers["Physical fit and performance"], "needs physical test")
        summary = next(c for c in upgraded if c["claim"] == "Slice")
        self.assertEqual((summary["tier"], summary["status"]), ("slicer-checked", "PASS"))
        for words in ("9m 25s", "0.99 m", "2.95 g", "no supports", "Centauri Carbon 2", "PLA"):
            self.assertIn(words, summary["detail"])

    def test_failed_slice_upgrades_nothing(self):
        upgraded = apply_slice(claims(), sliced(ok=False, support_used=True,
                                                problems=["supports were generated but the brief does not allow them"]))
        self.assertFalse(any(c["tier"] == "slicer-checked" and c["claim"] != "Slice" for c in upgraded))
        summary = next(c for c in upgraded if c["claim"] == "Slice")
        self.assertEqual(summary["status"], "FAIL")
        self.assertIn("brief does not allow", summary["detail"])

    def test_missing_slicer_is_said_plainly(self):
        upgraded = apply_slice(claims(), None)
        summary = next(c for c in upgraded if c["claim"] == "Slice")
        self.assertEqual(summary["status"], "NOT RUN")
        self.assertIn("ElegooSlicer is not installed", summary["detail"])
        self.assertFalse(any(c["tier"] == "slicer-checked" for c in upgraded))

    def test_slicer_setup_problem_is_not_run_not_fail(self):
        upgraded = apply_slice(claims(), sliced(ran=False, ok=False,
                                                problems=["ElegooSlicer presets could not be loaded: x"]))
        summary = next(c for c in upgraded if c["claim"] == "Slice")
        self.assertEqual((summary["tier"], summary["status"]), ("computed", "NOT RUN"))
        self.assertIn("presets could not be loaded", summary["detail"])


class NoPrintJobTest(unittest.TestCase):
    """No code path sends a job to a printer."""

    def test_slicer_command_only_slices_and_exports(self):
        argv = slicer.command(Path("/bin/elegoo"), [Path("/tmp/a.stl")], Path("/tmp/m.json"),
                              Path("/tmp/p.json"), Path("/tmp/f.json"), Path("/tmp/out"), "a.3mf")
        flags = {a for a in argv if a.startswith("--")}
        self.assertLessEqual(flags, slicer.ALLOWED_FLAGS)
        with self.assertRaises(ValueError):
            slicer.command(Path("/bin/elegoo"), [Path("--send")], Path("m"), Path("p"), Path("f"),
                           Path("/tmp/out"), "a.3mf")
        self.assertFalse(slicer.ALLOWED_FLAGS & {"--send", "--upload", "--print", "--pipe"})

    def test_flattened_machine_profile_has_no_print_host(self):
        machine = {"type": "machine", "name": "m", "host_type": "elegoolink",
                   "print_host": "192.168.1.20", "printhost_apikey": "k", "print_host_webui": "x"}
        cleaned = slicer.without_print_host(machine)
        for key in ("print_host", "printhost_apikey", "print_host_webui"):
            self.assertEqual(cleaned.get(key, ""), "")

    def test_no_source_reaches_a_printer(self):
        # Printer-network vocabulary that a send-to-printer path would need. The slicer
        # module names print_host only to blank it, so it is checked separately above.
        banned = re.compile(r"(?i)(send_?print|print_?job|start_?print|moonraker|octoprint|"
                            r"elegoolink|sdcp|/printer/print|upload_?gcode|--send\b|--upload\b)")
        roots = [ROOT / "engine", ROOT / "harness", ROOT / "library", ROOT / "mcp", ROOT / "ui",
                 ROOT / "magic.py"]
        sources = [p for r in roots for p in ([r] if r.is_file() else r.rglob("*.py"))]
        self.assertTrue(sources)
        offenders = [f"{p.relative_to(ROOT)}: {m.group(0)}" for p in sources
                     for m in [banned.search(p.read_text())] if m]
        self.assertEqual(offenders, [])


class MissingSlicerTest(unittest.TestCase):
    def test_find_slicer_honours_an_unusable_override(self):
        import os
        old = os.environ.get(slicer.ENV)
        os.environ[slicer.ENV] = "/nonexistent/ElegooSlicer"
        try:
            self.assertIsNone(slicer.find_slicer())
        finally:
            if old is None:
                os.environ.pop(slicer.ENV)
            else:
                os.environ[slicer.ENV] = old
        self.assertIn("ElegooSlicer is not installed", slicer.MISSING)


class ProjectFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "designs").mkdir()
        (self.project / "designs" / "block.py").write_text(CUBE)

    def tearDown(self):
        self.tmp.cleanup()


@NEEDS_SLICER
class SliceProjectTest(ProjectFixture):
    def test_passing_part_is_sliced_and_claims_upgrade(self):
        code, verdict = run_project(self.project, samples=3, slice=True)
        self.assertEqual(code, 0, json.dumps(verdict, indent=2)[:2000])
        design = verdict["designs"][0]
        result = design["slice"]
        self.assertTrue(result["ok"], result)
        self.assertGreater(result["print_seconds"], 0)
        self.assertGreater(result["filament_m"], 0)
        self.assertGreater(result["filament_g"], 0)
        self.assertFalse(result["support_used"])
        self.assertEqual(result["support_filament_mm"], 0)
        self.assertEqual(result["printer"], "Elegoo Centauri Carbon 2 0.4 nozzle")
        three_mf = self.project / "outputs" / result["three_mf"]
        with zipfile.ZipFile(three_mf) as archive:
            self.assertIn("Metadata/plate_1.gcode", archive.namelist())
        self.assertIn(result["three_mf"], design["artifacts"])
        tiers = {c["claim"]: c["tier"] for c in design["claims"]}
        self.assertEqual(tiers["3 Printability"], "slicer-checked")
        self.assertEqual(tiers["Slice"], "slicer-checked")
        report = json.loads((self.project / "outputs/block/report.json").read_text())
        self.assertEqual(report["claims"], design["claims"])

    def test_part_that_needs_forbidden_supports_fails(self):
        import trimesh
        from engine.slicer import slice_design
        out = self.project / "out"
        out.mkdir()
        post = trimesh.creation.box((10, 10, 30)).apply_translation((0, 0, 15))
        arms = trimesh.creation.box((60, 10, 5)).apply_translation((0, 0, 32.5))  # hang in the air
        trimesh.util.concatenate([post, arms]).export(out / "tee.stl")
        result = slice_design([out / "tee.stl"], out, "tee", "PLA", allow_supports=False)
        self.assertTrue(result["ran"])
        self.assertFalse(result["ok"])
        self.assertTrue(result["support_used"])
        self.assertIn("brief does not allow", " ".join(result["problems"]))
        allowed = slice_design([out / "tee.stl"], out, "tee", "PLA", allow_supports=True)
        self.assertTrue(allowed["ok"], allowed["problems"])
        self.assertGreater(allowed["support_filament_mm"], 0)

    def test_an_unsliced_rerun_leaves_no_stale_3mf(self):
        run_project(self.project, samples=3, slice=True)
        self.assertTrue((self.project / "outputs/block/block.3mf").exists())
        _, verdict = run_project(self.project, samples=3)
        self.assertFalse((self.project / "outputs/block/block.3mf").exists())
        self.assertNotIn("block/block.3mf", verdict["designs"][0]["artifacts"])

    def test_petg_uses_the_petg_filament_profile(self):
        (self.project / "printer.json").write_text(json.dumps(
            {"printer": "elegoo-centauri-carbon-2", "material": "PETG"}))
        _, verdict = run_project(self.project, samples=3, slice=True)
        self.assertEqual(verdict["designs"][0]["slice"]["filament"], "Elegoo PETG @ECC2")


class UnslicedRunTest(ProjectFixture):
    def test_runs_do_not_slice_unless_asked(self):
        _, verdict = run_project(self.project, samples=3)
        design = verdict["designs"][0]
        self.assertNotIn("slice", design)
        self.assertFalse(any(c["claim"] == "Slice" for c in design["claims"]))

    def test_slice_without_the_slicer_keeps_the_verdict_and_says_why(self):
        from unittest import mock
        with mock.patch.dict("os.environ", {slicer.ENV: "/nonexistent/ElegooSlicer"}):
            code, verdict = run_project(self.project, samples=3, slice=True)
        design = verdict["designs"][0]
        self.assertEqual(code, 0)
        summary = next(c for c in design["claims"] if c["claim"] == "Slice")
        self.assertEqual(summary["status"], "NOT RUN")
        self.assertIn("ElegooSlicer is not installed", summary["detail"])
        self.assertFalse(list((self.project / "outputs/block").glob("*.3mf")))


@NEEDS_SLICER
class SliceApiTest(ProjectFixture):
    def test_run_with_slice_serves_the_3mf(self):
        server = make_server(port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            body = json.dumps({"project": str(self.project), "wait": True, "samples": 3, "slice": True}).encode()
            request = urllib.request.Request(url + "/runs", data=body, method="POST",
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=300) as response:
                run = json.load(response)
            self.assertTrue(run["verdict"]["pass"], run)
            path = run["verdict"]["designs"][0]["slice"]["three_mf"]
            with urllib.request.urlopen(f"{url}/runs/{run['id']}/artifacts/{path}", timeout=30) as response:
                self.assertEqual(response.headers["Content-Type"], "model/3mf")
                self.assertTrue(response.read().startswith(b"PK"))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
