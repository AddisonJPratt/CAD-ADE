#!/usr/bin/env python
"""Eval runner aggregation on fabricated reports. No CAD, no subprocesses; runs in under a second.

    .venv/bin/python tests/test_evals.py
"""
import ast
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_evals import (ERROR, FAIL, GATE_NAMES, NO_DESIGN, PASS, discover, evaluate, no_design_row,
                             run_all, summarize, timestamped_dir, to_markdown, write_reports)

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail}")


def gates(**overrides):
    """All-PASS gate list; overrides keyed like gate_3 = "FAIL" or Sweep = "NOT RUN"."""
    keys = {"gate_1": "1 Execute", "gate_2": "2 Geometry", "gate_3": "3 Printability",
            "gate_4": "4 Renders", "Sweep": "Sweep", "gate_5": "5 Exports"}
    status = {keys[k]: v for k, v in overrides.items()}
    return [{"name": n, "status": status.get(n, "PASS"), "detail": "d"} for n in GATE_NAMES]


def good_report():
    return {"pass": True, "gates": gates(),
            "geometry": {"dimensions": [{"pass": True}] * 6 + [{"pass": True}]},
            "sweep": {"passed": 31, "total": 31}}


def failing_report():
    return {"pass": False,
            "gates": gates(gate_3="FAIL", Sweep="SKIPPED", gate_5="SKIPPED"),
            "geometry": {"dimensions": [{"pass": True}, {"pass": False}]}}


def test_gate_list_matches_harness():
    # Parsed, not imported: importing the pipeline would pull in the CAD stack.
    tree = ast.parse((ROOT / "harness" / "pipeline.py").read_text())
    names = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                 and getattr(node.targets[0], "id", "") == "GATE_NAMES")
    check("gate list matches harness.pipeline", names == GATE_NAMES, str(names))


def test_pass():
    row = evaluate("a", good_report(), 0, 229.0)
    check("pass: status", row["status"] == PASS)
    check("pass: metrics", row["runs"] is True and row["printable"] is True
          and row["dimensional"] == {"passed": 7, "total": 7}
          and row["parametric"] == {"passed": 31, "total": 31, "share": 1.0} and row["seconds"] == 229.0)
    check("pass: per-gate status kept", [g["status"] for g in row["gates"]] == ["PASS"] * 6)


def test_fail():
    row = evaluate("a", failing_report(), 1, 12.0)
    check("fail: status and reason", row["status"] == FAIL and "3 Printability" in row["reason"])
    check("fail: metrics", row["runs"] is True and row["printable"] is False
          and row["dimensional"] == {"passed": 1, "total": 2} and row["parametric"] is None)
    early = {"pass": False, "gates": gates(gate_1="FAIL", gate_2="SKIPPED", gate_3="SKIPPED",
                                           gate_4="SKIPPED", Sweep="SKIPPED", gate_5="SKIPPED")}
    row = evaluate("a", early, 1, 3.0)
    check("fail: skipped gate is unknown, not No", row["runs"] is False and row["printable"] is None)


def test_malformed():
    cases = {"none": None, "not a dict": [1, 2], "no pass key": {"gates": gates()},
             "pass not boolean": {"pass": "yes", "gates": gates()},
             "no gates": {"pass": True}, "gates not list": {"pass": True, "gates": "PASS"},
             "gate not dict": {"pass": True, "gates": ["PASS"]},
             "gate without status": {"pass": True, "gates": [{"name": "1 Execute"}]},
             "gates missing": {"pass": True, "gates": gates()[:2]}}
    for label, report in cases.items():
        row = evaluate("a", report, 0, 1.0)
        check(f"malformed: {label} is ERROR even on exit 0", row["status"] == ERROR and row["reason"])
    odd = good_report()
    odd["geometry"], odd["sweep"] = "junk", {"passed": "many", "total": 0}
    row = evaluate("a", odd, 0, 1.0)
    check("malformed: junk metrics don't crash", row["dimensional"] is None and row["parametric"] is None)


def test_signals_must_agree():
    check("exit 0 but report fails is ERROR", evaluate("a", failing_report(), 0, 1.0)["status"] == ERROR)
    check("exit 1 but report passes is ERROR", evaluate("a", good_report(), 1, 1.0)["status"] == ERROR)
    check("exit 2 is ERROR", evaluate("a", failing_report(), 2, 1.0)["status"] == ERROR)
    lying = good_report()
    lying["gates"] = gates(gate_2="FAIL")
    check("report pass with a failed gate is ERROR", evaluate("a", lying, 0, 1.0)["status"] == ERROR)
    check("timeout note wins over a stale report",
          evaluate("a", good_report(), -9, 1.0, note="timeout after 5 s")["status"] == ERROR)


def test_not_run_gates():
    quick = {"pass": True, "gates": gates(Sweep="NOT RUN", gate_5="NOT RUN"),
             "geometry": {"dimensions": [{"pass": True}]}}
    check("quick: unrun sweep may pass", evaluate("a", quick, 0, 1.0, quick=True)["status"] == PASS)
    check("full: unrun sweep can't pass", evaluate("a", quick, 0, 1.0, quick=False)["status"] == ERROR)
    quick["gates"] = gates(gate_3="NOT RUN", Sweep="NOT RUN", gate_5="NOT RUN")
    check("quick: another unrun gate can't pass", evaluate("a", quick, 0, 1.0, quick=True)["status"] == ERROR)
    skipped = {"pass": True, "gates": gates(Sweep="SKIPPED", gate_5="NOT RUN")}
    check("quick: SKIPPED is not NOT RUN", evaluate("a", skipped, 0, 1.0, quick=True)["status"] == ERROR)


def rows_of(*statuses):
    rows = []
    for i, status in enumerate(statuses):
        if status == NO_DESIGN:
            rows.append(no_design_row(f"b{i}"))
        elif status == PASS:
            rows.append(evaluate(f"b{i}", good_report(), 0, 1.0))
        elif status == FAIL:
            rows.append(evaluate(f"b{i}", failing_report(), 1, 1.0))
        else:
            rows.append(evaluate(f"b{i}", None, 0, 1.0))
    return rows


def test_summary():
    s = summarize(rows_of(PASS, *[NO_DESIGN] * 4))
    check("one pass + 4 no-design: 1/1 and 1/5", s["pass_rate"]["value"] == 1.0
          and s["pass_rate"]["text"] == "1/1 (100%)" and s["coverage"]["text"] == "1/5 (20%)", str(s["pass_rate"]))
    check("NO_DESIGN doesn't fail the run", s["exit_code"] == 0 and s["no_design"] == 4)
    s = summarize(rows_of(PASS, FAIL, NO_DESIGN, NO_DESIGN, NO_DESIGN))
    check("pass + fail + 3 no-design: 1/2 and 2/5", s["pass_rate"]["text"] == "1/2 (50%)"
          and s["coverage"]["text"] == "2/5 (40%)")
    check("a failed design fails the run", s["exit_code"] == 1)
    check("an errored design fails the run", summarize(rows_of(PASS, ERROR))["exit_code"] == 1)
    s = summarize(rows_of(NO_DESIGN, NO_DESIGN))
    check("no designs: pass rate is n/a, not 100 %", s["pass_rate"]["value"] is None
          and "n/a" in s["pass_rate"]["text"] and s["exit_code"] == 0)
    s = summarize([])
    check("no briefs: both n/a", s["pass_rate"]["value"] is None and s["coverage"]["value"] is None)
    check("mode recorded", summarize([], quick=True)["mode"] == "quick")


def test_reports():
    with tempfile.TemporaryDirectory() as tmp:
        report = write_reports(rows_of(PASS, FAIL, NO_DESIGN), tmp, False)
        saved = json.loads((Path(tmp) / "eval_report.json").read_text())
        text = (Path(tmp) / "eval_report.md").read_text()
    check("json report has both numbers apart", saved["summary"]["pass_rate"]["designs_present"] == 2
          and saved["summary"]["coverage"]["total_briefs"] == 3)
    check("md states pass rate", "Pass rate (over designs present): 1/2 (50%)" in text)
    check("md states coverage", "Coverage (designs present / total briefs): 2/3 (67%)" in text)
    check("md makes NO_DESIGN prominent", "NO_DESIGN: 1 of 3 briefs" in text and "**NO_DESIGN**" in text)
    check("md names the failure", "failed gates: 3 Printability" in text)
    check("full md has no quick banner", "QUICK MODE" not in to_markdown(report))
    quick = write_reports(rows_of(PASS), tempfile.mkdtemp(), True)
    check("quick md warns", "QUICK MODE" in to_markdown(quick))


def test_discover_and_run_all():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        briefs, designs, real = tmp / "evals", tmp / "designs", tmp / "real"
        for folder in (briefs, designs, real):
            folder.mkdir()
        (real / "linked.yaml").write_text("name: linked\n")
        (briefs / "linked.yaml").symlink_to("../real/linked.yaml")
        (briefs / "broken.yaml").symlink_to("../real/gone.yaml")
        (briefs / "plain.yaml").write_text("name: plain\n")
        (designs / "linked.py").write_text("")
        (designs / "unrelated.py").write_text("")
        entries = discover(briefs, designs)
        by_name = {e["name"]: e for e in entries}
        check("discover: symlinked brief found", by_name["linked"]["brief_is_symlink"]
              and by_name["linked"]["design_present"] and by_name["linked"]["brief_readable"])
        check("discover: broken symlink still listed", not by_name["broken"]["brief_readable"])
        check("discover: only briefs count", set(by_name) == {"linked", "broken", "plain"})

        calls = []

        def runner(entry, out_dir, quick, timeout):
            calls.append(entry["name"])
            return good_report(), 0, 2.0, None, None

        rows = run_all(entries, tmp, runner=runner, log=lambda *_: None)
        check("run_all: only present designs run", calls == ["linked"])
        check("run_all: statuses", {r["name"]: r["status"] for r in rows}
              == {"linked": PASS, "broken": NO_DESIGN, "plain": NO_DESIGN})
        first, second = timestamped_dir(tmp / "r"), timestamped_dir(tmp / "r")
        check("results folders never collide", first != second and first.is_dir() and second.is_dir())


def test_real_corpus_survives_a_fresh_clone():
    """The shipped corpus: every brief a real file (symlinks were lost once in packaging) with a design,
    and a brief kept in both places is the same brief, so the eval copy can't drift from the project one."""
    expected = {"box_with_lid", "cable_clip", "cable_spool", "doorstop", "drawer_tray", "gear_pair",
                "phone_stand", "pipe_clamp", "planter_pot", "project_enclosure", "wall_bracket"}
    entries = {e["name"]: e for e in discover()}
    # A floor, not an exact set: finished projects join the corpus as regression evals.
    check("corpus: the 11 founding eval briefs present", expected <= set(entries), f"missing {sorted(expected - set(entries))}")
    check("corpus: every brief is a readable real file, not a symlink",
          all(e["brief_readable"] and not e["brief_is_symlink"] for e in entries.values()))
    check("corpus: every brief has its design", all(e["design_present"] for e in entries.values()))
    project_briefs = ROOT / "briefs"
    drifted = [n for n, e in entries.items() if (project_briefs / f"{n}.yaml").is_file()
               and (project_briefs / f"{n}.yaml").read_bytes() != Path(e["brief"]).read_bytes()]
    check("corpus: eval briefs match their project briefs", not drifted, f"drifted {drifted}")


if __name__ == "__main__":
    for test in (test_gate_list_matches_harness, test_pass, test_fail, test_malformed,
                 test_signals_must_agree, test_not_run_gates, test_summary, test_reports,
                 test_discover_and_run_all, test_real_corpus_survives_a_fresh_clone):
        print(f"--- {test.__name__}")
        test()
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)
