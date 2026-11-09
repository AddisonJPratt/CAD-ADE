#!/usr/bin/env python
"""Quick gate subset (`magic.py ... --quick`, ticket #41): build, geometry, printability only.

Runs every starter design in designs/ both quick and full (`magic.py run`, sweep included), so it
is slow: about 5 min on 10 cores. Checks that quick stays under QUICK_BUDGET_S, that quick and
full agree on the geometry and printability verdicts, and that a quick pass is never a saved
version or a proven verdict.

    .venv/bin/python tests/test_quick.py [--record docs/quick-gate-timings.md] [--only wall_bracket]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.make import judge
from harness.pipeline import run

PYTHON = ROOT / ".venv" / "bin" / "python"
FIXTURES = ROOT / "tests" / "fixtures"
QUICK_BUDGET_S = 20            # the ticket's "under about 20 s", wall clock including Python start-up
VERDICT_GATES = ("1 Execute", "2 Geometry", "3 Printability")
QUICK_STATUSES = {"4 Renders": "NOT RUN", "Sweep": "NOT RUN", "5 Exports": "NOT RUN"}

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail}")


def harness(args, out):
    """Run magic.py in a subprocess; (exit code, report, wall seconds)."""
    started = time.monotonic()
    proc = subprocess.run([str(PYTHON), str(ROOT / "magic.py"), *map(str, args), "--out", str(out)],
                          cwd=ROOT, capture_output=True, text=True)
    seconds = time.monotonic() - started
    report_file = Path(out) / "report.json"
    report = json.loads(report_file.read_text()) if report_file.exists() else None
    if report is None:
        print(proc.stdout, proc.stderr)
    return proc.returncode, report, seconds


def statuses(report):
    return {g["name"]: g["status"] for g in report["gates"]}


def verdicts(report):
    """What the two runs must agree on: the build, geometry and printability gates."""
    by_name = {g["name"]: g for g in report["gates"]}
    timed = re.compile(r"built in [\d.]+ s")   # build time is a measurement, not a verdict
    return {name: (by_name[name]["status"], timed.sub("built in _ s", by_name[name]["detail"]))
            for name in VERDICT_GATES if by_name[name]["status"] != "SKIPPED"}


def test_contract(tmp):
    """One design, in process and via the CLI: what a quick report is and is not."""
    out = tmp / "contract"
    code, report = run(ROOT / "designs" / "wall_bracket.py", out=out, exports=False, quick=True,
                       command="quick")
    gates = statuses(report)
    check("quick: build, geometry, printability ran and passed",
          all(gates[g] == "PASS" for g in VERDICT_GATES) and code == 0, str(gates))
    check("quick: renders, sweep and exports are NOT RUN",
          all(gates[g] == s for g, s in QUICK_STATUSES.items()), str(gates))
    check("quick: report says quick", report.get("quick") is True)
    check("quick: verification is draft, never passed", report["verification"] == "draft", report["verification"])
    check("quick: no production files or renders written",
          not list(out.glob("*.stl")) and not list(out.glob("*.step")) and not (out / "renders").exists(),
          str(sorted(p.name for p in out.iterdir())))
    check("quick: report.json and report.md written", (out / "report.json").exists() and (out / "report.md").exists())
    gate_details = {g["name"]: g["detail"] for g in report["gates"]}
    check("quick: NOT RUN details say why", all("quick" in gate_details[g] for g in QUICK_STATUSES))

    verdict = {"pass": report["pass"], "designs": [{"pass": report["pass"], "gates": report["gates"],
                                                    "artifacts": ["wall_bracket/bracket.stl"]}]}
    proven, stl, _, failure = judge(verdict)
    check("quick: a quick report is never a proven verdict", proven is False and stl is None, failure)

    try:
        run(ROOT / "designs" / "wall_bracket.py", out=tmp / "refused", exports=True, quick=True)
        refused = False
    except ValueError:
        refused = True
    check("quick: refused together with exports", refused)

    code, report, _ = harness(["run", ROOT / "designs" / "wall_bracket.py", "--quick"], tmp / "cli-run")
    check("cli: run --quick keeps no exports", code == 0 and report["quick"] is True
          and statuses(report)["5 Exports"] == "NOT RUN" and not list((tmp / "cli-run").glob("*.stl")))
    code, _, _ = harness(["sweep", ROOT / "designs" / "wall_bracket.py", "--quick"], tmp / "cli-sweep")
    check("cli: sweep --quick is refused", code == 2, f"exit {code}")


def test_defaults():
    """The default quick folder never overwrites a full run's report."""
    proc = subprocess.run([str(PYTHON), str(ROOT / "magic.py"), "check", str(FIXTURES / "crash.py"), "--quick"],
                          cwd=ROOT, capture_output=True, text=True)
    out = ROOT / "runs" / "crash-quick"
    check("cli: default quick folder is runs/<stem>-quick", proc.returncode == 1 and (out / "report.json").exists())
    for leftover in sorted(out.rglob("*"), reverse=True):
        leftover.rmdir() if leftover.is_dir() else leftover.unlink()
    out.rmdir()


def compare(name, design, brief, tmp, full_too=True):
    extra = ["--brief", brief] if brief else []
    q_code, quick, q_seconds = harness(["check", design, "--quick", *extra], tmp / f"{name}-quick")
    if not full_too:
        return name, q_code, quick, q_seconds, None, None, None
    f_code, full, f_seconds = harness(["run", design, *extra], tmp / f"{name}-full")
    return name, q_code, quick, q_seconds, f_code, full, f_seconds


def test_agreement(tmp, only=None, record=None):
    """Every starter design plus failing fixtures: quick and full agree, quick is fast."""
    cases = [(p.stem, p, None) for p in sorted((ROOT / "designs").glob("*.py")) if not p.name.startswith("_")]
    starters = {name for name, _, _ in cases}
    cases += [("fixture_wrong_dim", FIXTURES / "wrong_dim.py", FIXTURES / "wrong_dim.yaml"),
              ("fixture_oversize", FIXTURES / "oversize.py", None),
              ("fixture_two_bodies", FIXTURES / "two_bodies.py", None),
              ("fixture_crash", FIXTURES / "crash.py", None)]
    if only:
        cases = [c for c in cases if c[0] in only]
    # Quick runs alone first, so their timings aren't inflated by full runs sharing the cores.
    with ThreadPoolExecutor(max_workers=1) as pool:   # one at a time: a fair timing
        quick_runs = list(pool.map(lambda c: compare(*c, tmp, full_too=False), cases))
    with ThreadPoolExecutor(max_workers=4) as pool:
        full_runs = list(pool.map(lambda c: compare(*c, tmp), cases))
    rows = []
    for (name, q_code, quick, q_seconds, *_), (_, _, quick_again, _, f_code, full, f_seconds) in zip(quick_runs, full_runs):
        if quick is None or full is None:
            check(f"{name}: both runs wrote a report", False)
            continue
        same = verdicts(quick) == verdicts(full) == verdicts(quick_again)
        check(f"{name}: quick and full agree on build/geometry/printability", same,
              "" if same else f"quick {verdicts(quick)} full {verdicts(full)}")
        if full["pass"]:
            check(f"{name}: full passes, so quick passes", q_code == 0 and quick["pass"] is True)
        quick_fail = any(s == "FAIL" for s, _ in verdicts(quick).values())
        check(f"{name}: a quick FAIL is a full FAIL", not quick_fail or f_code != 0)
        if name in starters:
            check(f"{name}: quick under {QUICK_BUDGET_S} s", q_seconds < QUICK_BUDGET_S, f"{q_seconds:.1f} s")
        rows.append((name, q_seconds, f_seconds, quick["verification"], full["verification"],
                     statuses(quick)["3 Printability"]))
    if record:
        lines = ["# Quick gate timings", "",
                 f"Recorded by `tests/test_quick.py --record` on {time.strftime('%Y-%m-%d')}, "
                 f"{subprocess.run(['sysctl', '-n', 'hw.ncpu'], capture_output=True, text=True).stdout.strip() or '?'} cores. "
                 "Wall clock per `magic.py` call, Python start-up included. Quick runs went one at a time; "
                 "full runs (`magic.py run`, sweep included) four at a time, so full times are inflated by sharing cores. "
                 f"Load average at the end: {os.getloadavg()[0]:.0f}.",
                 "", f"Budget: quick under {QUICK_BUDGET_S} s on every starter design.", "",
                 "| Design | Quick (s) | Full (s) | Quick verification | Full verification | Printability |",
                 "|---|---:|---:|---|---|---|"]
        lines += [f"| {n} | {q:.1f} | {f:.1f} | {qv} | {fv} | {p} |" for n, q, f, qv, fv, p in rows]
        Path(record).write_text("\n".join(lines) + "\n")
        print(f"recorded {record}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", help="write the timing table here (markdown)")
    parser.add_argument("--only", nargs="*", help="limit the agreement test to these case names")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="magic_quick_") as tmp:
        tmp = Path(tmp)
        print("--- contract")
        test_contract(tmp)
        print("--- defaults")
        test_defaults()
        print("--- agreement")
        test_agreement(tmp, args.only, args.record)
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)
