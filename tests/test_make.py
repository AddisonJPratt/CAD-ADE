"""Make mode (engine/make.py, #14): the first-proof app's behaviour on engine projects.

    .venv/bin/python -m unittest tests.test_make -v

Each proof/tests/test_proof.py case has its equivalent here; verdicts are written by hand except
in the last test, which makes a real holder through the HTTP API and runs every gate on it.
"""
import ast
import base64
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import make  # noqa: E402
from engine.api import make_server  # noqa: E402
from engine.projects import ProjectError  # noqa: E402
from engine.versions import STATE, head, list_versions  # noqa: E402

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 64).decode()
PHYSICAL = {"claim": "Physical fit and performance", "tier": "needs physical test", "status": "NOT TESTED",
            "detail": "No physical print result recorded."}

ROUND = {"object": "Pump <script>", "shape": "round", "diameter": "42", "length": "200",
         "mount": "screws", "material": "PETG"}


def params(design):
    tree = ast.parse(Path(design).read_text())
    return ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign)
                                 and any(getattr(t, "id", "") == "PARAMS" for t in n.targets)))


def pass_verdict(project, gates=None, stls=1):
    """A stored verdict for the current version, as a finished run would leave it."""
    stem = make.record(project)["template"]
    gates = gates or {name: "PASS" for name in make.GATES}
    artifacts = [f"{stem}/{stem}{'' if i == 0 else i}.stl" for i in range(stls)] + [f"{stem}/renders/iso.png"]
    verdict = {"pass": True, "designs": [{"design": f"{stem}.py", "pass": True, "claims": [PHYSICAL],
                                          "gates": [{"name": n, "status": s, "detail": ""} for n, s in gates.items()],
                                          "artifacts": artifacts}]}
    folder = Path(project) / STATE / "verdicts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{head(project)}.json").write_text(json.dumps(verdict))
    return head(project)


class MakeCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"MAGIC_PROJECTS_HOME": str(root / "home"),
                                           "MAGIC_PRINT_LOG": str(root / "PRINT_LOG.md")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def made(self, form=ROUND):
        folder, ask = make.create(form)
        make.size(folder, ask)
        return folder

    def profile(self):
        return json.loads((make.calibration_dir() / "profile.json").read_text())["adjustments_mm"]


class MakeTests(MakeCase):
    def test_generated_design_uses_requested_value_and_matching_brief(self):
        folder = self.made()
        self.assertEqual(folder.name, "Pump script holder")
        self.assertEqual(params(folder / "designs" / "holder_clip.py")["barrel_dia"][0], 42)
        brief = yaml.safe_load((folder / "briefs" / "holder_clip.yaml").read_text())
        self.assertEqual(brief["params"]["barrel_dia"]["value"], 42)
        self.assertEqual(brief["hard_dimensions"]["mount_holes"], 2)
        self.assertEqual(make.record(folder)["readings"]["length"], 200)
        self.assertEqual(make.record(folder)["object"], "Pump <script>")
        self.assertNotIn("<script>", (folder / "designs" / "holder_clip.py").read_text())
        self.assertEqual(json.loads((folder / "printer.json").read_text())["material"], "PETG")
        versions = list_versions(folder)
        self.assertEqual([v["message"] for v in versions], ["Sized for Pump <script>: 42 mm diameter",
                                                            "Created from holder_clip"])

    def test_rectangular_object_sizes_the_cradle(self):
        folder = self.made({"object": "Router", "shape": "rectangular", "width": "100", "depth": "30",
                            "height": "90", "material": "PLA"})
        values = params(folder / "designs" / "holder_cradle.py")
        self.assertEqual((values["obj_w"][0], values["obj_d"][0], values["obj_h"][0]), (100, 30, 90))
        self.assertIn("mm, object width", (folder / "designs" / "holder_cradle.py").read_text())  # comments kept

    def test_finite_range_validation(self):
        for value in ("nan", "inf", "-1", "51", ""):
            with self.subTest(value=value), self.assertRaises(ProjectError):
                make.validate({**ROUND, "diameter": value})
        for bad in ({"shape": "hex"}, {"object": " "}, {"object": "x" * 101}, {"material": "ABS"},
                    {"mount": "adhesive"}, {"length": "0"}):
            with self.subTest(bad=bad), self.assertRaises(ProjectError):
                make.validate({**ROUND, **bad})
        self.assertFalse((Path(os.environ["MAGIC_PROJECTS_HOME"])).exists())

    def test_only_complete_success_exports_and_feedback_once(self):
        folder = self.made()
        version = pass_verdict(folder)
        proof = make.proof(folder, version)
        self.assertTrue(proof["proven"])
        self.assertEqual(proof["stl"], "holder_clip/holder_clip.stl")
        self.assertEqual(proof["render"], "holder_clip/renders/iso.png")
        recorded = make.record_print(folder, version, "too_tight")
        self.assertEqual(recorded["outcome"]["result"], "too_tight")
        self.assertAlmostEqual(self.profile()["holder_clip"], .2)
        self.assertTrue(recorded["can_remake"])
        self.assertAlmostEqual(recorded["next_clearance_mm"], .45)
        with self.assertRaises(ProjectError):
            make.record_print(folder, version, "too_tight")
        self.assertEqual(len((make.calibration_dir() / "outcomes.jsonl").read_text().splitlines()), 1)
        self.assertIn("too tight", make.print_log().read_text().lower())

    def test_stale_and_out_of_bounds_outcomes_are_recorded_without_adjustment(self):
        first, second = self.made(), self.made()
        self.assertEqual(second.name, "Pump script holder 2")
        first_version, second_version = pass_verdict(first), pass_verdict(second)
        make.record_print(first, first_version, "too_tight")
        stale = make.record_print(second, second_version, "too_tight")["outcome"]
        self.assertEqual(stale["adjustment_mm"], 0)
        self.assertTrue(stale["review_needed"])
        self.assertIn("changed since this print", stale["adjustment_reason"])
        self.assertAlmostEqual(self.profile()["holder_clip"], .2)
        self.assertEqual(len((make.calibration_dir() / "outcomes.jsonl").read_text().splitlines()), 2)
        # Out of bounds: the clearance range tops out at 0.7 mm.
        current = self.made()  # made at 0.45 mm
        make.record_print(current, pass_verdict(current), "too_tight")
        make.size(current)
        self.assertAlmostEqual(self.profile()["holder_clip"], .4)  # 0.25 + 0.4 = 0.65
        capped = make.record_print(current, pass_verdict(current), "too_tight")["outcome"]
        self.assertEqual(capped["adjustment_mm"], 0)
        self.assertIn("tested clearance range", capped["adjustment_reason"])
        with self.assertRaisesRegex(ProjectError, "already uses"):
            make.size(current)

    def test_reconciles_durable_event_after_interrupted_materialization(self):
        folder = self.made()
        version = pass_verdict(folder)
        make.record_print(folder, version, "too_tight")
        (make.calibration_dir() / "profile.json").unlink()
        (make.calibration_dir() / "outcomes.jsonl").unlink()
        make.reconcile()
        make.reconcile()
        self.assertAlmostEqual(self.profile()["holder_clip"], .2)
        self.assertEqual(len((make.calibration_dir() / "outcomes.jsonl").read_text().splitlines()), 1)
        self.assertEqual(make.print_log().read_text().count("magic-make:" + make.event_key(folder, version)), 1)

    def test_not_run_never_releases_export(self):
        folder = self.made()
        version = pass_verdict(folder, gates={n: "NOT RUN" if n == "Sweep" else "PASS" for n in make.GATES})
        proof = make.proof(folder, version)
        self.assertFalse(proof["proven"])
        self.assertIsNone(proof["stl"])
        self.assertIn("Sweep", proof["failure"])
        with self.assertRaises(ProjectError):
            make.record_print(folder, version, "perfect")
        two = self.made()
        self.assertFalse(make.proof(two, pass_verdict(two, stls=2))["proven"])

    def test_unchecked_version_is_not_proven(self):
        folder = self.made()
        proof = make.proof(folder, head(folder))
        self.assertFalse(proof["checked"])
        self.assertFalse(proof["proven"])
        with self.assertRaises(ProjectError):
            make.record_print(folder, head(folder), "perfect")

    def test_remake_applies_calibrated_clearance_as_a_new_version(self):
        folder = self.made()
        make.record_print(folder, pass_verdict(folder), "too_tight")
        make.size(folder)
        self.assertAlmostEqual(params(folder / "designs" / "holder_clip.py")["clearance"][0], .45)
        versions = list_versions(folder)
        self.assertEqual(versions[0]["message"], "Adjusted fit gap: 0.45 mm per side")
        self.assertAlmostEqual(make.record(folder)["clearance_used_mm"], .45)
        self.assertAlmostEqual(make.record(folder, versions[1]["id"])["clearance_used_mm"], .25)
        new = self.made()  # a new make of the same template starts from the calibrated clearance
        self.assertAlmostEqual(make.record(new)["clearance_used_mm"], .45)
        self.assertTrue(make.form_spec()["shapes"]["round"]["calibrated"])

    def test_shelf_lists_projects_with_history_and_outcomes(self):
        folder = self.made()
        version = pass_verdict(folder)
        make.record_print(folder, version, "perfect")
        shelf = make.shelf()
        self.assertEqual(len(shelf["projects"]), 1)
        item = shelf["projects"][0]
        self.assertEqual(item["path"], str(folder))
        self.assertEqual(item["make"]["object"], "Pump <script>")
        self.assertEqual(len(item["versions"]), 2)
        self.assertEqual(item["versions"][0]["outcome"]["result"], "perfect")
        self.assertIsNone(item["versions"][1]["outcome"])


class PrintResultTests(MakeCase):
    """#15: rate each fit in a few taps, optional caliper readings and photo, claims upgraded."""

    def test_proof_offers_each_fit_and_the_named_features_to_measure(self):
        folder = self.made()
        proof = make.proof(folder, pass_verdict(folder))
        self.assertEqual([(f["id"], f["primary"]) for f in proof["fits"]], [("grip", True), ("screws", False)])
        features = {f["id"]: f for f in proof["features"]}
        self.assertAlmostEqual(features["bore"]["modelled_mm"], 42.5)  # 42 + 2 x 0.25 per side
        self.assertAlmostEqual(features["screw_hole"]["modelled_mm"], 3.4)  # M3 clearance, standard_parts
        cradle = self.made({"object": "Router", "shape": "rectangular", "width": "100", "depth": "30",
                            "height": "90", "material": "PLA"})
        proof = make.proof(cradle, pass_verdict(cradle))
        self.assertEqual([f["id"] for f in proof["fits"]], ["seat", "screws"])
        widths = {f["id"]: f["modelled_mm"] for f in proof["features"]}
        self.assertAlmostEqual(widths["inner_width"], 100.5)
        self.assertAlmostEqual(widths["inner_depth"], 30.25)

    def test_each_fit_measurements_and_photo_land_in_the_outcomes_log(self):
        folder = self.made()
        version = pass_verdict(folder)
        recorded = make.record_print(folder, version, fits={"grip": "perfect", "screws": "too_loose"},
                                     measurements={"bore": "42.31", "screw_hole": ""}, photo=PNG)
        outcome = recorded["outcome"]
        self.assertEqual(outcome["result"], "perfect")  # the primary fit drives the clearance, as before
        self.assertEqual(outcome["adjustment_mm"], 0)
        self.assertEqual([(f["id"], f["result"]) for f in outcome["fits"]], [("grip", "perfect"), ("screws", "too_loose")])
        self.assertEqual(outcome["measurements"], [{"id": "bore", "label": "Clip bore", "modelled_mm": 42.5,
                                                    "measured_mm": 42.31, "difference_mm": -0.19}])
        self.assertTrue((make.calibration_dir() / outcome["photo"]).is_file())
        line = json.loads((make.calibration_dir() / "outcomes.jsonl").read_text().splitlines()[0])
        self.assertEqual((line["project"], line["project_name"], line["version"], line["version_number"]),
                         (str(folder), folder.name, version, 2))
        self.assertEqual(line["fits"], outcome["fits"])
        log = make.print_log().read_text()
        self.assertIn("Modelled vs measured: Clip bore 42.5 mm modelled, 42.31 mm measured (-0.19 mm)", log)
        self.assertIn("Clip around the object: Perfect; Screws in the mounting holes: Too loose", log)
        self.assertIn(f"Photo: {outcome['photo']}", log)
        self.assertEqual(self.profile().get("holder_clip", 0), 0)

    def test_only_the_primary_fit_is_required_and_measurements_never_calibrate(self):
        folder = self.made()
        outcome = make.record_print(folder, pass_verdict(folder), fits={"grip": "too_tight"},
                                    measurements={"bore": 41.9})["outcome"]
        self.assertEqual([f["id"] for f in outcome["fits"]], ["grip"])
        self.assertIsNone(outcome["photo"])
        self.assertAlmostEqual(self.profile()["holder_clip"], .2)  # the existing 0.2 mm nudge, nothing more

    def test_matching_claims_become_physically_tested(self):
        folder = self.made()
        version = pass_verdict(folder)
        before = make.proof(folder, version)["claims"]
        self.assertEqual([c["tier"] for c in before], ["needs physical test"])
        make.record_print(folder, version, fits={"grip": "too_tight"}, measurements={"bore": 42.31})
        claims = {c["claim"]: c for c in make.proof(folder, version)["claims"]}
        grip = claims["Physical fit: Clip around the object"]
        self.assertEqual((grip["tier"], grip["status"]), ("physically tested", "FAIL"))
        self.assertIn("Too tight", grip["detail"])
        screws = claims["Physical fit: Screws in the mounting holes"]
        self.assertEqual((screws["tier"], screws["status"]), ("needs physical test", "NOT TESTED"))
        bore = claims["Measured: Clip bore"]
        self.assertEqual((bore["tier"], bore["status"]), ("physically tested", "RECORDED"))
        self.assertNotIn("Physical fit and performance", claims)
        # Studio reads claims from the version list: the same upgrade shows there.
        studio = list_versions(folder)[0]["verdict"]["designs"][0]["claims"]
        self.assertIn("physically tested", [c["tier"] for c in studio])
        perfect = self.made()
        v = pass_verdict(perfect)
        make.record_print(perfect, v, fits={"grip": "perfect", "screws": "perfect"})
        tiers = {c["claim"]: (c["tier"], c["status"]) for c in make.proof(perfect, v)["claims"]}
        self.assertEqual(tiers["Physical fit: Screws in the mounting holes"], ("physically tested", "PASS"))

    def test_old_single_result_events_still_read_as_the_primary_fit(self):
        folder = self.made()
        version = pass_verdict(folder)
        make.record_print(folder, version, "perfect")
        path = make.calibration_dir() / "events" / f"{make.event_key(folder, version)}.json"
        event = json.loads(path.read_text())
        for key in ("fits", "measurements", "photo", "project_name"):
            event.pop(key)
        path.write_text(json.dumps(event))
        claims = {c["claim"]: c for c in make.proof(folder, version)["claims"]}
        self.assertEqual(claims["Physical fit: Clip around the object"]["status"], "PASS")
        make.reconcile()

    def test_bad_print_results_are_refused_and_nothing_is_recorded(self):
        folder = self.made()
        version = pass_verdict(folder)
        bad = [dict(fits={"screws": "perfect"}),                         # the primary fit is required
               dict(fits={"grip": "perfect", "hinge": "perfect"}),     # not a fit of this holder
               dict(fits={"grip": "wobbly"}),
               dict(result="perfect", fits={"grip": "too_tight"}),     # two answers for one fit
               dict(fits={"grip": "perfect"}, measurements={"wall": 2}),
               dict(fits={"grip": "perfect"}, measurements={"bore": "nan"}),
               dict(fits={"grip": "perfect"}, measurements={"bore": 0}),
               dict(fits={"grip": "perfect"}, measurements={"bore": 5000}),
               dict(fits={"grip": "perfect"}, photo="data:text/html;base64,PGh0bWw+"),
               dict(fits={"grip": "perfect"}, photo="data:image/png;base64,PGh0bWw+"),  # not really a PNG
               dict(fits={"grip": "perfect"}, photo="data:image/png;base64," + base64.b64encode(
                   b"\x89PNG\r\n\x1a\n" + b"\0" * (7 * 1024 * 1024)).decode())]
        for kwargs in bad:
            with self.subTest(kwargs=str(kwargs)[:80]), self.assertRaises(ProjectError):
                make.record_print(folder, version, **kwargs)
        self.assertIsNone(make.outcome(folder, version))
        self.assertFalse((make.calibration_dir() / "photos").exists())


class PrintResultApiTests(unittest.TestCase):
    """#15 at the HTTP seam: rate fits, measure, attach a photo, read the upgraded claims."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"MAGIC_PROJECTS_HOME": str(root / "home"),
                                           "MAGIC_PRINT_LOG": str(root / "PRINT_LOG.md")})
        self.env.start()
        self.server = make_server(port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.env.stop()
        self.temp.cleanup()

    call = lambda self, path, body=None: MakeApiTests.call(self, path, body)  # noqa: E731

    def test_record_fits_measurements_and_photo(self):
        folder, ask = make.create(ROUND)
        make.size(folder, ask)
        version = pass_verdict(folder)
        query = urllib.parse.urlencode({"project": str(folder), "version": version})
        status, proof = self.call(f"/make/proof?{query}")
        self.assertEqual([f["label"] for f in proof["fits"]], ["Clip around the object", "Screws in the mounting holes"])
        status, error = self.call("/make/print", {"project": str(folder), "version": version, "fits": {"grip": "meh"}})
        self.assertEqual(status, 400)
        self.assertEqual(error["error"], "Choose a fit result for each fit you rate.")
        status, recorded = self.call("/make/print", {"project": str(folder), "version": version,
                                                     "fits": {"grip": "perfect", "screws": "perfect"},
                                                     "measurements": {"bore": 42.4}, "photo": PNG})
        self.assertEqual(status, 200, recorded)
        tested = [c["claim"] for c in recorded["claims"] if c["tier"] == "physically tested"]
        self.assertEqual(tested, ["Physical fit: Clip around the object", "Physical fit: Screws in the mounting holes",
                                  "Measured: Clip bore"])
        with urllib.request.urlopen(f"{self.base}/make/photo?{query}") as response:
            self.assertEqual(response.headers["Content-Type"], "image/png")
            self.assertTrue(response.read().startswith(b"\x89PNG"))
        status, again = self.call("/make/print", {"project": str(folder), "version": version, "result": "perfect"})
        self.assertEqual(status, 409)
        status, versions = self.call(f"/projects/versions?{urllib.parse.urlencode({'project': str(folder)})}")
        tiers = [c["tier"] for c in versions["versions"][0]["verdict"]["designs"][0]["claims"]]
        self.assertNotIn("needs physical test", tiers)


class MakeApiTests(unittest.TestCase):
    """A real holder through the HTTP seam: Ask, Make (every gate), Prove, Shelf."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"MAGIC_PROJECTS_HOME": str(root / "home"),
                                           "MAGIC_PRINT_LOG": str(root / "PRINT_LOG.md")})
        self.env.start()
        self.server = make_server(port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.env.stop()
        self.temp.cleanup()

    def call(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_ask_make_prove_shelf(self):
        status, spec = self.call("/make/form")
        self.assertEqual(status, 200)
        self.assertEqual([f["name"] for f in spec["shapes"]["round"]["fields"]], ["diameter", "length"])
        status, error = self.call("/make", {**ROUND, "diameter": "70"})
        self.assertEqual(status, 400)
        self.assertEqual(error["error"], "Diameter must be between 30 and 50 mm.")
        status, made = self.call("/make", {**ROUND, "object": "Bike pump", "wait": True, "samples": 12})
        self.assertEqual(status, 200, made)
        self.assertEqual(made["run"]["status"], "done")
        project, version = made["project"], made["version"]["id"]
        status, proof = self.call(f"/make/proof?project={urllib.parse.quote(project)}&version={version}")
        self.assertEqual(status, 200)
        self.assertTrue(proof["proven"], proof["failure"])
        self.assertEqual([g["status"] for g in proof["gates"]], ["PASS"] * 6)
        query = urllib.parse.urlencode({"project": project, "version": version, "path": proof["stl"]})
        with urllib.request.urlopen(f"{self.base}/projects/version-artifacts?{query}") as response:
            self.assertGreater(len(response.read()), 1000)
        status, recorded = self.call("/make/print", {"project": project, "version": version, "result": "too_tight"})
        self.assertEqual(status, 200)
        status, again = self.call("/make/print", {"project": project, "version": version, "result": "perfect"})
        self.assertEqual(status, 409)
        status, remade = self.call("/make", {"project": project})
        self.assertEqual(status, 202)
        self.assertEqual(remade["version"]["number"], 3)
        status, shelf = self.call("/make/shelf")
        self.assertEqual([v["number"] for v in shelf["projects"][0]["versions"]], [3, 2, 1])
        self.assertEqual(shelf["projects"][0]["versions"][1]["outcome"]["result"], "too_tight")


if __name__ == "__main__":
    unittest.main()
