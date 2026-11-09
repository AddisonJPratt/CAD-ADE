#!/usr/bin/env python
"""Quick mode (#80): build, geometry and printability only, for mid-session iteration.

    .venv/bin/python tests/test_quick_mode.py           every starter design, full runs included (~10 min)
    .venv/bin/python tests/test_quick_mode.py --fast    the version and MCP checks only (~30 s)

Checks that quick and full runs agree on the Geometry and Printability verdicts for every
starter design in designs/, that each quick run beats the full run (QUICK_BUDGET_S is the idle-machine target, printed), that a quick pass
keeps no files and never creates a version or a stored verdict, and that run_check(quick=True)
in the MCP server is the same quick run.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import versions
from engine.make import judge
from harness.pipeline import QUICK_NOT_RUN, run

PYTHON = ROOT / ".venv" / "bin" / "python"
QUICK_BUDGET_S = 20          # the ticket's target for one quick run
COMPARED = ("2 Geometry", "3 Printability")
FULL_ONLY = {"4 Renders", "Sweep", "5 Exports"}

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail}")


def brief_for(stem):
    """briefs/ first, then evals/briefs/, as the MCP server's run_check does."""
    for folder in (ROOT / "briefs", ROOT / "evals" / "briefs"):
        if (folder / f"{stem}.yaml").is_file():
            return folder / f"{stem}.yaml"
    return None


def gates(report):
    return {g["name"]: g for g in report["gates"]}


def test_quick_matches_full(tmp):
    """Same verdicts on the gates both runs share; the full run is `magic.py run`, sweep included."""
    timings = {}
    for design in sorted((ROOT / "designs").glob("*.py")):
        brief = brief_for(design.stem)
        start = time.monotonic()
        quick_code, quick = run(design, brief, tmp / f"{design.stem}-quick", quick=True, command="test quick")
        timings[design.stem] = round(time.monotonic() - start, 1)
        start = time.monotonic()
        full_code, full = run(design, brief, tmp / f"{design.stem}-full", command="test full")
        full_s = round(time.monotonic() - start, 1)
        q, f = gates(quick), gates(full)
        same = all(q[n]["status"] == f[n]["status"] and q[n]["detail"] == f[n]["detail"] for n in COMPARED)
        check(f"{design.stem}: quick and full agree on geometry and printability", same,
              "; ".join(f"{n} quick {q[n]['status']} / full {f[n]['status']}" for n in COMPARED))
        check(f"{design.stem}: same geometry and printability numbers",
              quick.get("geometry") == full.get("geometry") and quick.get("printability") == full.get("printability"))
        # Wall-clock budgets fail on a loaded machine, so the assertion is relative; the
        # absolute target is printed and was measured on an idle machine (see the PR for #80).
        check(f"{design.stem}: quick faster than full", timings[design.stem] < full_s,
              f"quick {timings[design.stem]} s, full {full_s} s, target < {QUICK_BUDGET_S} s"
              f"{'' if timings[design.stem] < QUICK_BUDGET_S else ' (over target: machine load?)'}")
        reached = q["3 Printability"]["status"] in ("PASS", "FAIL")
        check(f"{design.stem}: quick never runs renders, sweep or exports",
              all(q[n]["status"] == ("NOT RUN" if reached else "SKIPPED") for n in FULL_ONLY))
        check(f"{design.stem}: a quick pass is a draft, never passed",
              quick["mode"] == "quick" and quick["verification"] in ("draft", "failed") and
              (quick["verification"] == "draft") == quick["pass"])
        check(f"{design.stem}: a passing full run is not a draft",
              not full["pass"] or (full["verification"] == "passed" and full["mode"] == "full"))
        if full["pass"]:
            check(f"{design.stem}: quick passes wherever full passes", quick["pass"] and quick_code == 0)
        check(f"{design.stem}: quick keeps no production files",
              not any(any((tmp / f"{design.stem}-quick").glob(p)) for p in ("*.stl", "*.step", "*.faces.json", "renders")))
    print("quick run times (s):", json.dumps(timings))


def test_quick_creates_no_version(tmp):
    project = versions.create_project(tmp / "clip", "cable_clip")
    before = versions.list_versions(project)
    design = project / "designs" / "cable_clip.py"

    code, report = run(design, None, tmp / "quick-api", quick=True)
    cli = subprocess.run([PYTHON, ROOT / "magic.py", "run", design, "--quick", "--out", tmp / "quick-cli"],
                         capture_output=True, text=True, cwd=ROOT)
    after = versions.list_versions(project)
    check("quick passes the cable clip, in-process and from the CLI", code == 0 and report["pass"]
          and cli.returncode == 0, cli.stdout[-300:])
    check("the CLI says a quick pass is a draft", "QUICK PASS (draft" in cli.stdout)
    check("a quick pass creates no version", [v["id"] for v in after] == [v["id"] for v in before]
          and len(after) == 1)
    check("a quick pass stores no verdict", after[0]["verdict"] is None
          and not (project / versions.STATE / "verdicts").exists())
    check("the project has nothing unsaved after a quick pass", not versions.unsaved(project))
    check("quick run on `run` keeps no exports", not list((tmp / "quick-cli").glob("*.stl"))
          and json.loads((tmp / "quick-cli" / "report.json").read_text())["mode"] == "quick")

    # Even if someone stored a quick report as a verdict, it would not be proven.
    verdict = {"pass": True, "designs": [{"design": "cable_clip.py", "pass": True, "gates": report["gates"],
                                         "artifacts": ["cable_clip/cable_clip.stl"]}]}
    proven, stl, *_ = judge(verdict)
    check("a quick report can never be judged proven", proven is False and stl is None)
    check("quick marks exactly the gates it skips as NOT RUN",
          [g["name"] for g in report["gates"] if g["status"] == "NOT RUN"] == list(QUICK_NOT_RUN))


def test_cli_refuses_odd_combinations(tmp):
    for argv in (["sweep", "designs/cable_clip.py", "--quick"],
                 ["check", "designs/cable_clip.py", "--quick", "--no-sweep"]):
        done = subprocess.run([PYTHON, ROOT / "magic.py", *argv, "--out", tmp / "refused"],
                              capture_output=True, text=True, cwd=ROOT)
        check(f"refused: magic.py {' '.join(argv)}", done.returncode == 2 and "--quick" in done.stderr)


def test_mcp_quick(tmp):
    spec = importlib.util.spec_from_file_location("magic_cad_server", ROOT / "mcp" / "magic_cad_server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)
    result = srv.run_check("cable_clip", quick=True)
    statuses = {g["name"]: g["status"] for g in result["gates"]}
    check("run_check(quick=True) passes the cable clip", result["pass"] and result["error"] is None, str(result)[:300])
    check("run_check(quick=True) reports mode and its own folder", result["mode"] == "quick"
          and result["report_path"].endswith("cable_clip-quick/report.json") and "note" in result)
    check("run_check(quick=True) runs only the quick gates",
          all(statuses[n] == "PASS" for n in ("1 Execute", *COMPARED))
          and all(statuses[n] == "NOT RUN" for n in FULL_ONLY))
    print(f"run_check(quick=True) took {result['seconds']} s (target < {QUICK_BUDGET_S} s)")


if __name__ == "__main__":
    fast = "--fast" in sys.argv
    with tempfile.TemporaryDirectory(prefix="magic_quick_") as tmp:
        tmp = Path(tmp)
        test_quick_creates_no_version(tmp)
        test_cli_refuses_odd_combinations(tmp)
        test_mcp_quick(tmp)
        if not fast:
            test_quick_matches_full(tmp)
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)
