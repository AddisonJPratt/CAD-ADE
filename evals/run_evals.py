#!/usr/bin/env python
"""Run the harness on every eval brief that has a design, then report the EVALS.md metrics.

  .venv/bin/python evals/run_evals.py [--quick] [--out DIR] [--timeout S]
  .venv/bin/python magic.py evals [--quick] [--out DIR] [--timeout S]

Default: full `magic.py run` per design, sweep and exports included.
--quick: `magic.py check --no-sweep`. Fast feedback only; it says nothing about parametric
behaviour, so a quick PASS does not verify a design.
Results go to evals/results/<timestamp>/ unless --out names another folder.
Exit code: 0 if every present design passes, 1 if any fails. NO_DESIGN never fails the run.
"""
import argparse
import json
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "bin" / "python"   # not resolved: the venv is found through this symlink
BRIEFS_DIR = ROOT / "evals" / "briefs"
DESIGNS_DIR = ROOT / "designs"
RESULTS_DIR = ROOT / "evals" / "results"
DEFAULT_TIMEOUT = 1800      # s per design; a full run is about 4 min on 4 cores

PASS, FAIL, ERROR, NO_DESIGN = "PASS", "FAIL", "ERROR", "NO_DESIGN"
# Same list as harness.pipeline.GATE_NAMES; tests/test_evals.py fails if they drift apart.
GATE_NAMES = ["1 Execute", "2 Geometry", "3 Printability", "4 Renders", "Sweep", "5 Exports"]
QUICK_NOT_RUN = {"Sweep", "5 Exports"}   # the only gates a quick run may leave unrun


def discover(briefs_dir=BRIEFS_DIR, designs_dir=DESIGNS_DIR):
    """One entry per brief, sorted. glob lists symlinks, so wall_bracket.yaml is included."""
    entries = []
    for brief in sorted(Path(briefs_dir).glob("*.yaml")):
        design = Path(designs_dir) / f"{brief.stem}.py"
        entries.append({"name": brief.stem, "brief": brief, "design": design,
                        "design_present": design.is_file(), "brief_is_symlink": brief.is_symlink(),
                        "brief_readable": brief.is_file()})
    return entries


def run_harness(args, timeout):
    """Run a harness command in its own process group, so a timeout also kills its workers.

    subprocess.run(timeout=) kills only the child, then blocks on pipes the workers still hold.
    stdin is closed so nothing downstream can read a parent's stream (the MCP server's protocol).
    """
    started = time.monotonic()
    result = {"returncode": None, "stdout": "", "stderr": "", "timed_out": False, "error": None}
    try:
        proc = subprocess.Popen([str(a) for a in args], cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                errors="replace", start_new_session=True)
    except OSError as err:
        result["error"] = f"could not start harness: {err}"
    else:
        try:
            result["stdout"], result["stderr"] = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            result["stdout"], result["stderr"] = proc.communicate()
            result["timed_out"] = True
        except BaseException:   # Ctrl-C: don't leave workers behind in their own group
            os.killpg(proc.pid, signal.SIGKILL)
            raise
        result["returncode"] = proc.returncode
    result["seconds"] = round(time.monotonic() - started, 1)
    return result


def read_report(path):
    """Return the parsed report, or None if it is missing or not JSON."""
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def report_problem(report):
    """Why a report can't be trusted, or None. Keeps the aggregation from crashing on junk."""
    if not isinstance(report, dict):
        return "report is not a JSON object"
    if not isinstance(report.get("pass"), bool):
        return "report has no boolean 'pass'"
    gates = report.get("gates")
    if not isinstance(gates, list) or not all(isinstance(g, dict) and isinstance(g.get("name"), str)
                                              and isinstance(g.get("status"), str) for g in gates):
        return "report 'gates' is not a list of {name, status}"
    missing = [name for name in GATE_NAMES if name not in {g["name"] for g in gates}]
    if missing:
        return f"report is missing gates {missing}"
    return None


def gate_status(gates, name):
    return next((g["status"] for g in gates if g["name"] == name), None)


def count_dimensions(report):
    geometry = report.get("geometry")
    rows = geometry.get("dimensions") if isinstance(geometry, dict) else None
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return None
    return {"passed": sum(1 for r in rows if r.get("pass") is True), "total": len(rows)}


def count_sweep(report):
    sweep = report.get("sweep")
    if not isinstance(sweep, dict) or not isinstance(sweep.get("passed"), int) \
            or not isinstance(sweep.get("total"), int) or sweep["total"] <= 0:
        return None
    return {"passed": sweep["passed"], "total": sweep["total"],
            "share": sweep["passed"] / sweep["total"]}


def blocked_gates(gates, quick):
    """Gates that stop a design passing. In a full run every gate must be a real PASS."""
    allowed = QUICK_NOT_RUN if quick else set()
    return [g["name"] for g in gates
            if g["status"] != "PASS" and not (g["status"] == "NOT RUN" and g["name"] in allowed)]


def no_design_row(name, brief=None):
    return {"name": name, "brief": brief, "status": NO_DESIGN, "reason": "no design file",
            "gates": [], "runs": None, "dimensional": None, "printable": None, "parametric": None,
            "seconds": None, "report_path": None}


def evaluate(name, report, exit_code, seconds, quick=False, note=None, brief=None, report_path=None):
    """Turn one harness outcome into a table row. Pure, so it is testable without CAD.

    PASS requires exit 0, a well-formed report saying pass, and every gate satisfied. Any
    disagreement between those signals is ERROR, never a pass.
    """
    row = no_design_row(name, brief)
    row.update(seconds=seconds, report_path=report_path, reason=None)
    problem = note or report_problem(report)
    if problem:
        row.update(status=ERROR, reason=f"{problem} (exit {exit_code})")
        return row
    gates = report["gates"]
    row["gates"] = [{"name": g["name"], "status": g["status"], "detail": g.get("detail", "")} for g in gates]
    execute, printable = gate_status(gates, "1 Execute"), gate_status(gates, "3 Printability")
    row.update(runs=execute == "PASS" if execute != "SKIPPED" else None,
               printable=printable == "PASS" if printable in ("PASS", "FAIL") else None,
               dimensional=count_dimensions(report),
               parametric=count_sweep(report))
    blocked = blocked_gates(gates, quick)
    if exit_code == 0 and report["pass"] and not blocked:
        row["status"] = PASS
    elif exit_code == 1 and not report["pass"]:
        failed = [g["name"] for g in gates if g["status"] == "FAIL"]
        row.update(status=FAIL, reason=f"failed gates: {', '.join(failed) or ', '.join(blocked)}")
    else:
        row.update(status=ERROR, reason=f"harness signals disagree: exit {exit_code}, "
                                        f"report pass={report['pass']}, unsatisfied gates {blocked}")
    return row


def share_text(part, whole):
    return f"{part}/{whole} ({part / whole:.0%})" if whole else f"{part}/{whole} (n/a)"


def summarize(rows, quick=False):
    """Pass rate and coverage are separate numbers with separate denominators, on purpose."""
    missing = [r["name"] for r in rows if r["status"] == NO_DESIGN]
    present = len(rows) - len(missing)
    passed = sum(1 for r in rows if r["status"] == PASS)
    failed = sum(1 for r in rows if r["status"] == FAIL)
    errored = sum(1 for r in rows if r["status"] == ERROR)
    return {"mode": "quick" if quick else "full",
            "pass_rate": {"passed": passed, "designs_present": present,
                          "value": passed / present if present else None,
                          "text": share_text(passed, present)},
            "coverage": {"designs_present": present, "total_briefs": len(rows),
                         "value": present / len(rows) if rows else None,
                         "text": share_text(present, len(rows))},
            "passed": passed, "failed": failed, "errored": errored,
            "no_design": len(missing), "no_design_briefs": missing,
            "exit_code": 1 if failed or errored else 0}


def fmt_seconds(seconds):
    if seconds is None:
        return "-"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} min {rest} s" if minutes else f"{rest} s"


def fmt_flag(value):
    return "-" if value is None else ("Yes" if value else "No")


def fmt_count(value):
    return "-" if value is None else f"{value['passed']}/{value['total']}"


def fmt_parametric(row, quick):
    value = row["parametric"]
    if value:
        return f"{value['passed']}/{value['total']} ({value['share']:.0%})"
    return "not run (quick)" if quick and row["status"] != NO_DESIGN else "-"


def summary_lines(summary):
    lines = [f"Pass rate (over designs present): {summary['pass_rate']['text']}",
             f"Coverage (designs present / total briefs): {summary['coverage']['text']}"]
    if summary["no_design"]:
        lines.append(f"NO_DESIGN: {summary['no_design']} of {summary['coverage']['total_briefs']} briefs "
                     f"have no design ({', '.join(summary['no_design_briefs'])}). "
                     "Coverage gap, not a design failure.")
    if summary["errored"]:
        lines.append(f"ERROR: {summary['errored']} design(s) gave no trustworthy result; counted as not passing.")
    if summary["mode"] == "quick":
        lines.append("QUICK MODE: sweep not run. Parametric behaviour is unverified; "
                     "a PASS here does not verify a design.")
    return lines


def to_markdown(report):
    summary, quick = report["summary"], report["summary"]["mode"] == "quick"
    out = [f"# Eval report: {report['generated_at']}", "", "## Summary", ""]
    out += [f"- **{line}**" for line in summary_lines(summary)]
    out += ["", "## Per brief", "",
            "| Brief | Status | Runs | Dimensional | Printable | Parametric | Time |",
            "|---|---|---|---|---|---|---|"]
    for row in report["briefs"]:
        status = f"**{row['status']}**" if row["status"] != PASS else row["status"]
        out.append(f"| {row['name']} | {status} | {fmt_flag(row['runs'])} | {fmt_count(row['dimensional'])} | "
                   f"{fmt_flag(row['printable'])} | {fmt_parametric(row, quick)} | {fmt_seconds(row['seconds'])} |")
    notes = [row for row in report["briefs"] if row["status"] in (FAIL, ERROR)]
    if notes:
        out += ["", "## Not passing", ""] + [f"- {r['name']}: {r['status']}: {r['reason']}" for r in notes]
    ran = [row for row in report["briefs"] if row["gates"]]
    if ran:
        out += ["", "## Gates", "", "| Brief | Gate | Status | Detail |", "|---|---|---|---|"]
        out += [f"| {r['name']} | {g['name']} | {g['status']} | {g['detail']} |" for r in ran for g in r["gates"]]
    return "\n".join(out) + "\n"


def run_design(entry, out_dir, quick, timeout):
    """Harness run for one design. Returns (report, exit_code, seconds, note, report_path)."""
    run_dir = Path(out_dir) / "runs" / entry["name"]
    run_dir.mkdir(parents=True, exist_ok=True)
    design, brief = entry["design"], entry["brief"]
    args = [PYTHON, ROOT / "magic.py", "check" if quick else "run", design, "--brief", brief, "--out", run_dir]
    args += ["--no-sweep"] if quick else []
    outcome = run_harness(args, timeout)
    report_path = run_dir / "report.json"
    note = outcome["error"]
    if outcome["timed_out"]:
        note = f"timeout after {timeout} s"
    elif not note and not report_path.exists():
        note = f"no report.json written: {outcome['stderr'].strip()[-300:] or 'no stderr'}"
    return read_report(report_path), outcome["returncode"], outcome["seconds"], note, report_path


def relative(path):
    path = Path(path)
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def run_all(entries, out_dir, quick=False, timeout=DEFAULT_TIMEOUT, runner=run_design, log=print):
    """Evaluate every brief; `runner` is injectable so tests need no CAD."""
    rows = []
    for entry in entries:
        name, brief = entry["name"], relative(entry["brief"])
        if not entry["design_present"]:
            log(f"{NO_DESIGN:10} {name}")
            rows.append(no_design_row(name, brief))
            continue
        log(f"{'RUNNING':10} {name}")
        report, code, seconds, note, path = runner(entry, out_dir, quick, timeout)
        rows.append(evaluate(name, report, code, seconds, quick, note, brief, relative(path) if path else None))
        log(f"{rows[-1]['status']:10} {name} ({fmt_seconds(seconds)})")
    return rows


def write_reports(rows, out_dir, quick):
    """Write both reports; the JSON last and atomically, so eval_status never reads half a file."""
    report = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
              "summary": summarize(rows, quick), "briefs": rows}
    out_dir = Path(out_dir)
    (out_dir / "eval_report.md").write_text(to_markdown(report))
    temporary = out_dir / "eval_report.json.tmp"
    temporary.write_text(json.dumps(report, indent=2))
    temporary.replace(out_dir / "eval_report.json")
    return report


def timestamped_dir(results_dir=RESULTS_DIR):
    """A new folder; a suffix keeps two runs in the same second apart."""
    stamp, attempt = datetime.now().strftime("%Y%m%d-%H%M%S"), 1
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    while True:
        candidate = Path(results_dir) / (stamp if attempt == 1 else f"{stamp}-{attempt}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            attempt += 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="check semantics, sweep skipped; not a verification")
    parser.add_argument("--out", help="output folder; default evals/results/<timestamp>")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds per design")
    args = parser.parse_args(argv)
    out_dir = Path(args.out).resolve() if args.out else timestamped_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = run_all(discover(), out_dir, args.quick, args.timeout)
    report = write_reports(rows, out_dir, args.quick)
    print()
    for line in summary_lines(report["summary"]):
        print(line)
    print(f"Reports: {relative(out_dir / 'eval_report.md')}, {relative(out_dir / 'eval_report.json')}")
    return report["summary"]["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
