"""The designer role (#61): a brief card in, a design that passes every gate out.

The engine owns the loop and the agent owns the writing. Each attempt:

1. the writer (a `DesignWriter`) writes or rewrites design files in the proposal's draft copy of
   the project, given the brief card, the printer and clearance table, and the last gate report;
2. any change outside `designs/*.py` and `assembly.py` (the brief, the library, the printer
   settings) is reverted and reported back as refused: the designer never edits those;
3. the engine runs the quick gates (#80: build, geometry, printability; seconds) and, once they
   pass, the full project run with renders, Eyes and the sweep. Gate events stream live; a gate report closes
   each run. A failing report is the next attempt's feedback.

A full pass ends the loop with the changed files as a proposal (before may be empty). Running out
of attempts or wall time ends it with an error naming the last gate report, never a silent partial.
Interrupting rolls the current attempt back in the draft; resuming redoes it. The project folder
itself is never written: only accepting the proposal does that (engine/api.py).

The writer seam is a scripted fake in tests (`ScriptedFakeDesigner`) and Claude Code for real
(`engine.claude_designer.ClaudeCodeDesigner`). The unit of work is a set of files, not one, so the
two-part case (#82, M2) needs no new seam.
"""
import json
import queue
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path

from harness.brief import BriefError, load_brief
from harness.pipeline import run as run_design

from .agents import AgentAdapter
from .projects import ASSEMBLY, OUTPUTS, ProjectError, designs_of, run_project

DEFAULT_ATTEMPTS = 6
DEFAULT_SECONDS = 45 * 60
MAX_ATTEMPTS = 20
SKIPPED_DIRS = {OUTPUTS, "__pycache__", ".git", ".magic"}


class DesignWriter(ABC):
    """The agent half of the designer: writes design files into session['workspace']."""

    @abstractmethod
    def write(self, session, attempt, feedback):
        """Write or rewrite design files for this attempt; yield progress events while doing it.
        feedback is the previous attempt's gate report as text, or None on the first attempt."""

    def interrupt(self, session):
        """Stop a write in progress. session['interrupted'] is already set."""


class ScriptedFakeDesigner(DesignWriter):
    """A predictable writer for tests, not a language model: step N is written on the Nth call
    (an interrupted attempt is redone by the next call, so it takes the next step).

    A step is {relative path: source} or a callable(session). Every feedback string it was given
    is kept in self.feedback, so a test can see what the loop told it.
    """

    def __init__(self, steps):
        self.steps, self.feedback = list(steps), []

    def write(self, session, attempt, feedback):
        self.feedback.append(feedback)
        if len(self.feedback) > len(self.steps):
            raise ProjectError(f"scripted designer has no step for call {len(self.feedback)}")
        step = self.steps[len(self.feedback) - 1]
        if callable(step):
            step(session)
        else:
            for relative, source in step.items():
                target = Path(session["workspace"]) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
        yield {"type": "plan", "message": f"Scripted designer wrote attempt {attempt}"}


def allowed(relative):
    """The files a designer may write: top-level designs/*.py and the assembly file."""
    parts = Path(relative).parts
    return relative == ASSEMBLY or (len(parts) == 2 and parts[0] == "designs" and parts[1].endswith(".py"))


def files_of(folder):
    """Every source file in a project folder, relative path -> bytes (outputs and caches skipped)."""
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*")
            if p.is_file() and not SKIPPED_DIRS & set(p.relative_to(folder).parts)}


def restore(folder, saved, now, which):
    """Put the files `which` selects back as they were in `saved`."""
    folder = Path(folder)
    for relative in set(saved) | set(now):
        if not which(relative) or saved.get(relative) == now.get(relative):
            continue
        target = folder / relative
        if relative in saved:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(saved[relative])
        else:
            target.unlink(missing_ok=True)


def changed(saved, now):
    return sorted(r for r in set(saved) | set(now) if saved.get(r) != now.get(r))


def gate_summary(report):
    """A gate run's report, per design, as the event stream and the proposal carry it."""
    entries = report["designs"] + ([report["assembly"]] if report.get("assembly") else [])
    return {"pass": report["pass"], "designs": [
        {"design": e.get("design") or e.get("assembly"), "pass": e["pass"],
         "gates": [{"name": g["name"], "status": g["status"], "detail": g["detail"]} for g in e["gates"]]}
        for e in entries]}


def feedback_of(attempt, mode, report, workspace):
    """The previous gate run as text for the next attempt: failing gates, the traceback tail,
    failing sweep samples and where the renders are, so the writer can look at its own part."""
    lines = [f"Attempt {attempt} {mode} gate run: {'PASS' if report['pass'] else 'FAIL'}"]
    for entry in report["designs"]:
        lines.append(f"{entry['design']}: {'PASS' if entry['pass'] else 'FAIL'}")
        for gate in entry["gates"]:
            lines.append(f"  {gate['status']:8} {gate['name']}: {gate['detail']}")
        detail = entry.get("details") or {}
        if detail.get("traceback"):
            lines.append("  traceback (tail):")
            lines += ["    " + line for line in detail["traceback"].strip().splitlines()[-12:]]
        failing = [r for r in (detail.get("sweep") or {}).get("rows", []) if not r.get("pass")]
        for row in failing[:5]:
            lines.append(f"  sweep sample {row['label']} failed: {'; '.join(map(str, row.get('problems', [])))[:300]}")
        if (detail.get("sweep") or {}).get("dead_params"):
            lines.append(f"  dead params (no effect between min and max): {detail['sweep']['dead_params']}")
        out = Path(workspace) / OUTPUTS / Path(entry["design"]).stem
        images = sorted((out / "renders").glob("*.png")) + sorted((out / "eyes").glob("*.png"))  # Eyes (#79)
        if images:
            lines.append("  images to look at: " + ", ".join(str(p) for p in images[:12]))
        if (out / "eyes" / "eyes.json").is_file():
            lines.append(f"  per-part metrics (bbox, overhang shares, min wall): {out / 'eyes' / 'eyes.json'}")
    if report.get("assembly"):
        for gate in report["assembly"]["gates"]:
            lines.append(f"{ASSEMBLY}: {gate['status']} {gate['name']}: {gate['detail']}")
    return "\n".join(lines)


def last_failures(summary):
    """One line naming the failing gates of a gate summary."""
    failed = [f"{d['design']} {g['name']}: {g['detail']}" for d in summary["designs"]
              for g in d["gates"] if g["status"] == "FAIL"]
    return "; ".join(failed)[:1500] or "no gate passed or failed"


class DesignLoop(AgentAdapter):
    """The designer as an engine agent: same proposal lifecycle and event stream as M0 (#8).

    start()'s message is the request {"brief": <stem>, "attempts"?, "seconds"?, "samples"?,
    "timeout"?}: the brief card at briefs/<stem>.yaml, the iteration budget, the sweep sample cap
    and the per-build timeout.
    """
    name = "designer"

    def __init__(self, writer):
        self.writer = writer

    def start(self, project, brief, selection, message):
        from .printers import project_printer
        if not isinstance(message, dict) or not isinstance(message.get("brief"), str) or not message["brief"]:
            raise ProjectError("name the brief card to design from")
        project = Path(project)
        stem = message["brief"]
        card = project / "briefs" / f"{stem}.yaml"
        if Path(stem).name != stem or not card.is_file():
            raise ProjectError(f"no brief card briefs/{stem}.yaml in the project")
        try:
            load_brief(card)
        except (BriefError, OSError) as err:
            raise ProjectError(f"brief card invalid, fix it before designing: {err}") from err
        attempts = message.get("attempts", DEFAULT_ATTEMPTS)
        seconds = message.get("seconds", DEFAULT_SECONDS)
        if not isinstance(attempts, int) or isinstance(attempts, bool) or not 1 <= attempts <= MAX_ATTEMPTS:
            raise ProjectError(f"attempts must be a whole number from 1 to {MAX_ATTEMPTS}")
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
            raise ProjectError("seconds must be a positive number")
        samples = message.get("samples")
        if samples is not None and (not isinstance(samples, int) or samples <= 0):
            raise ProjectError("samples must be a positive whole number")
        printer = project_printer(project)
        material = printer["profile"]["materials"][printer["material"]]
        file = f"designs/{stem}.py"
        original = files_of(project)
        context = {"brief_name": stem, "brief": card.read_text(), "design_file": file,
                   "existing_source": original.get(file, b"").decode() or None,
                   "printer": {"name": printer["profile"].get("name", printer["profile"]["id"]),
                               "build_volume_mm": printer["profile"]["build_volume_mm"],
                               "nozzle_mm": printer["profile"].get("nozzle_mm"),
                               "material": printer["material"]},
                   "clearances_mm_per_side": material["fit_clearance_mm_per_side"]}
        return {"kind": "design", "file": file, "source": "", "changes": [], "files": None, "report": None,
                "selection": selection, "workspace": str(project), "context": context, "brief_name": stem,
                "budget": {"attempts": attempts, "seconds": float(seconds)}, "samples": samples,
                "timeout": int(message.get("timeout", 180)), "original": original,
                "attempt": 0, "elapsed": 0.0, "feedback": None, "interrupted": False,
                "process": None, "process_lock": threading.Lock(), "execution": None}

    # -- the loop ---------------------------------------------------------------------------

    def stream_events(self, session):
        workspace = Path(session["workspace"])
        budget = session["budget"]
        while session["report"] is None:
            if session["interrupted"]:
                return
            if session["attempt"] >= budget["attempts"] or session["elapsed"] >= budget["seconds"]:
                raise ProjectError(self.exhausted(session))
            session["attempt"] += 1
            attempt = session["attempt"]
            began = time.monotonic()
            before = files_of(workspace)
            yield {"type": "attempt_started", "attempt": attempt, "of": budget["attempts"]}
            try:
                outcome = yield from self.attempt(session, attempt, before)
            finally:
                session["elapsed"] += time.monotonic() - began
            if outcome == "interrupted":
                restore(workspace, before, files_of(workspace), lambda r: True)
                session["attempt"] -= 1
                return
        yield from self.finish(session)

    def attempt(self, session, attempt, before):
        workspace = Path(session["workspace"])
        for event in self.writer.write(session, attempt, session["feedback"]):
            if session["interrupted"]:
                return "interrupted"
            yield event
        if session["interrupted"]:
            return "interrupted"
        now = files_of(workspace)
        refused = [r for r in changed(before, now) if not allowed(r)]
        if refused:
            restore(workspace, before, now, lambda r: not allowed(r))
            yield {"type": "refused_edit", "attempt": attempt, "files": refused}
            session["feedback"] = (f"Attempt {attempt} was refused: it changed {', '.join(refused)}. The designer "
                                   f"writes only designs/*.py and {ASSEMBLY}; the brief, library, printer settings "
                                   "and harness are fixed. Those edits were reverted. Design to the brief as it is.")
            return "refused"
        if not (workspace / session["file"]).is_file():
            yield {"type": "gate_report", "attempt": attempt, "mode": "quick", "pass": False, "designs": []}
            session["feedback"] = f"Attempt {attempt} wrote no {session['file']}; write the design there."
            return "failed"
        for mode in ("quick", "full"):
            report = yield from self.gates(session, attempt, mode)
            if report is None:
                return "interrupted"
            if not report["pass"]:
                session["feedback"] = feedback_of(attempt, mode, report, workspace)
                return "failed"
        session["report"] = gate_summary(report)
        return "passed"

    def finish(self, session):
        workspace = Path(session["workspace"])
        now = files_of(workspace)
        original = session["original"]
        files = [r for r in changed(original, now) if allowed(r)]
        session["files"] = {r: {"before": original[r].decode() if r in original else None,
                                "after": now[r].decode() if r in now else None} for r in files}
        session["source"] = session["files"].get(session["file"], {}).get("after") or ""
        yield {"type": "edit", "files": files, "changes": []}
        yield {"type": "plan", "message": f"Every gate passed on attempt {session['attempt']}, sweep included; "
                                          "the design is held for you to accept."}

    def exhausted(self, session):
        budget, report = session["budget"], session.get("last_report")
        count = session["attempt"]
        spent = f"{count} attempt{'' if count == 1 else 's'} and {session['elapsed']:.0f} s of a " \
                f"{budget['attempts']}-attempt, {budget['seconds']:g} s budget"
        last = last_failures(report) if report else (session["feedback"] or "no gate run")
        return f"The designer could not reach a passing design in {spent}. Last gate report: {last}"

    # -- gate runs --------------------------------------------------------------------------

    def gates(self, session, attempt, mode):
        """Run the gates in the draft on a worker thread, yielding their events as they happen.
        Returns the report, or None if interrupted (the orphaned run finishes on its own, holding
        the execution lock, and its result is ignored)."""
        workspace = Path(session["workspace"])
        events, result = queue.Queue(), {}
        lock = session.get("execution")

        def work():
            if lock is not None:
                while not lock.acquire(timeout=0.2):
                    if session["interrupted"]:
                        result["interrupted"] = True
                        events.put(None)
                        return
            try:
                result["report"] = (self.quick(workspace, session, events.put) if mode == "quick"
                                    else self.full(workspace, session, events.put))
            except Exception as err:  # a crashed gate run is a failed attempt, not a dead session
                result["error"] = f"{type(err).__name__}: {err}"
            finally:
                if lock is not None:
                    lock.release()
                events.put(None)

        yield {"type": "gate_run_started", "attempt": attempt, "mode": mode}
        threading.Thread(target=work, name="designer-gates", daemon=True).start()
        while True:
            try:
                event = events.get(timeout=0.2)
            except queue.Empty:
                if session["interrupted"]:
                    return None
                continue
            if event is None:
                break
            if session["interrupted"]:
                return None
            yield {k: v for k, v in event.items() if k != "id"}
        if session["interrupted"] or result.get("interrupted"):
            return None
        if "error" in result:
            report = {"pass": False, "designs": [{"design": session["file"].split("/")[-1], "pass": False,
                                                  "gates": [{"name": "Gate run", "status": "FAIL",
                                                             "detail": result["error"]}]}]}
        else:
            report = result["report"]
        summary = gate_summary(report)
        session["last_report"] = summary
        yield {"type": "gate_report", "attempt": attempt, "mode": mode, **summary}
        return report

    @staticmethod
    def details(workspace, design):
        path = Path(workspace) / OUTPUTS / Path(design).stem / "report.json"
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return {}

    def quick(self, workspace, session, emit):
        """The quick gate subset (#80) on every design: build, geometry, printability. A draft only."""
        from .printers import project_printer
        printer = project_printer(workspace)
        designs = []
        for design in designs_of(workspace):
            out = workspace / OUTPUTS / design.stem
            _, report = run_design(design, out=out, exports=False, quick=True, timeout=session["timeout"],
                                   command="designer quick check", on_event=emit, printer=printer)
            designs.append({"design": design.name, "pass": report["pass"], "gates": report["gates"],
                            "details": report})
        return {"pass": all(d["pass"] for d in designs), "designs": designs}

    def full(self, workspace, session, emit):
        """The full project run, sweep included: what accepting will run again."""
        _, verdict = run_project(workspace, emit, session["samples"], session["timeout"])
        for entry in verdict["designs"]:
            entry["details"] = self.details(workspace, entry["design"])
        return verdict

    # -- control ----------------------------------------------------------------------------

    def interrupt(self, session):
        with session["process_lock"]:
            session["interrupted"] = True
        self.writer.interrupt(session)

    def resume(self, session):
        with session["process_lock"]:
            session["interrupted"] = False
