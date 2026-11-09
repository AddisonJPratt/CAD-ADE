"""Opt-in real designer eval (#61): a brief card in, a passing design out. Never in the test suite.

    .venv/bin/python evals/run_designer.py [--brief briefs/wall_bracket.yaml] [--attempts 6]
                                           [--seconds 2700] [--samples N] [--project DIR] [--no-accept]

Creates a project holding only the brief card, asks the real Claude Code designer for a design
through the engine API (the same proposal seam Studio uses), streams every event, then accepts the
proposal: the gates run again on the saved version and the independent reviewer (#28) scores it.
Writes evals/results/designer-<timestamp>-<brief>/ with events.jsonl, the design file, the review
and result.json (attempts, wall time, usage, gate report, review). Uses the existing CLI login and
spends model usage. Exit 0 only if the design passed every gate.
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.api import Engine, Handler  # noqa: E402
from engine.claude_designer import ClaudeCodeDesigner  # noqa: E402
from engine.designer import DesignLoop  # noqa: E402
from engine.reviewer import ClaudeCodeReviewer  # noqa: E402
from engine.versions import create_project_from_brief, list_versions  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brief", type=Path, default=ROOT / "briefs/wall_bracket.yaml")
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--seconds", type=float, default=2700)
    parser.add_argument("--samples", type=int, help="sweep sample cap; default the harness's")
    parser.add_argument("--project", type=Path, help="where to create the project; default a temp folder")
    parser.add_argument("--no-accept", action="store_true", help="stop at the proposal; no version, no review")
    parser.add_argument("--out", type=Path, help="results folder; default evals/results/designer-<ts>-<brief>")
    args = parser.parse_args(argv)
    stem = args.brief.stem
    out = args.out or ROOT / "evals/results" / f"designer-{datetime.now():%Y%m%d-%H%M%S}-{stem}"
    out.mkdir(parents=True, exist_ok=True)
    scratch = tempfile.TemporaryDirectory(prefix="magic-designer-eval-")
    project = (args.project or Path(scratch.name) / stem).resolve()
    create_project_from_brief(project, args.brief)

    handler = Handler.__new__(Handler)
    handler.engine = Engine(designer=DesignLoop(ClaudeCodeDesigner()), reviewer=ClaudeCodeReviewer())
    began = time.monotonic()
    log = (out / "events.jsonl").open("w")

    def record(source, event):
        line = json.dumps({"source": source, **event})
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    request = {"brief": stem, "attempts": args.attempts, "seconds": args.seconds}
    if args.samples:
        request["samples"] = args.samples
    _, pending = handler.post_proposal({"project": str(project), "design": request})
    proposal = handler.engine.proposals[pending["id"]]
    session = proposal["session"]
    sent = 0
    while True:
        with session.changed:
            session.changed.wait(timeout=2)
            fresh, state = session.events[sent:], session.state
            sent = len(session.events)
        for event in fresh:
            record("designer", event)
        if state in ("ready", "error"):
            break
    events = list(session.events)
    reports = [e for e in events if e["type"] == "gate_report"]
    usage = [e for e in events if e["type"] == "usage"]
    result = {"brief": stem, "project": str(project), "state": session.state, "error": session.error,
              "attempts": proposal["attempt"], "budget": proposal["budget"],
              "designer_seconds": round(time.monotonic() - began, 1),
              "gate_runs": {"quick": sum(r["mode"] == "quick" for r in reports),
                            "full": sum(r["mode"] == "full" for r in reports)},
              "refused_edits": sum(e["type"] == "refused_edit" for e in events),
              "designer_usage": {"runs": len(usage), "cost_usd": round(sum(u.get("cost_usd") or 0 for u in usage), 4),
                                 "tokens": sum(u.get("tokens") or 0 for u in usage)},
              "last_gate_report": reports[-1] if reports else None, "pass": False}
    design = Path(proposal["workspace"]) / proposal["file"]
    if design.is_file():
        shutil.copyfile(design, out / design.name)
    if session.state == "ready" and not args.no_accept:
        _, accepted = handler.accept_proposal(pending["id"], {"wait": True, **({"samples": args.samples} if args.samples else {})})
        run = handler.engine.get(accepted["run"]["id"])
        with run.changed:
            run.changed.wait_for(lambda: run.status in ("done", "error"))
        for event in run.events:
            record("accepted-run", {k: v for k, v in event.items() if k != "traceback"})
        version = list_versions(project)[0]
        result.update({"pass": bool(run.verdict and run.verdict["pass"]), "version": version["number"],
                       "review": run.review, "seconds": round(time.monotonic() - began, 1)})
        renders = project / "outputs" / stem / "renders"
        if renders.is_dir():
            shutil.copytree(renders, out / "renders", dirs_exist_ok=True)
    elif session.state == "ready":
        result["pass"] = bool(proposal["report"] and proposal["report"]["pass"])
    (out / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("brief", "state", "pass", "attempts", "designer_seconds", "gate_runs")}
                     | {"review": (result.get("review") or {}).get("total"), "out": str(out)}), flush=True)
    log.close()
    handler.engine.close()
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
