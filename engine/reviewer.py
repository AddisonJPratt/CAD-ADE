"""The independent reviewer agent (#28): a design verdict after the gates pass.

The harness proves a design executes, measures and prints; the reviewer judges whether
it is a good design, with the magic-cad-reviewer rubric (five dimensions, 0-4 each, 20
in all). It runs as its own process with a fresh context: it sees the brief, the source,
the gate report and the renders, never the designer's conversation.

    verdict_of(raw)            the rubric's totals, band and pass/fail from raw scores
    ScriptedFakeReviewer       deterministic, for tests at the app seam
    ClaudeCodeReviewer         local Claude Code, read-only, structured output

A review scoring 12/20 or less (rework or reject) fails, and the engine sends the top
fix back to the designer once; the owner still approves whatever the designer proposes.
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path

from .projects import ProjectError

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/magic-cad-reviewer/SKILL.md"
DIMENSIONS = ("looks_like_the_thing", "detail", "dimensions", "proportion", "print_intent")
LABELS = {"looks_like_the_thing": "Looks like the thing", "detail": "Detail with a reason",
          "dimensions": "Dimension honesty", "proportion": "Proportion and stance",
          "print_intent": "Print-intent coherence"}
PASS_SCORE = 13   # 13-16 "direction approved"; 12 and below is rework or reject
MAX_FIXES = 5

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["scores", "tells", "fixes", "good"],
          "properties": {
              "scores": {"type": "object", "additionalProperties": False, "required": list(DIMENSIONS),
                         "properties": {d: {"type": "integer", "minimum": 0, "maximum": 4} for d in DIMENSIONS}},
              "tells": {"type": "array", "items": {"type": "string"}},
              "fixes": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                    "required": ["text"],
                                                    "properties": {"text": {"type": "string", "minLength": 1},
                                                                   "parameter": {"type": "string"},
                                                                   "value": {"type": "number"}}}},
              "good": {"type": "string"}}}


def band_of(total):
    return ("adopt-ready" if total >= 17 else "direction approved" if total >= PASS_SCORE
            else "rework" if total >= 9 else "reject")


def verdict_of(raw):
    """Normalise a reviewer's raw answer: clamp scores, rank fixes, total, band and pass."""
    if not isinstance(raw, dict) or not isinstance(raw.get("scores"), dict):
        raise ProjectError("the reviewer returned no scores")
    scores = {}
    for d in DIMENSIONS:
        value = raw["scores"].get(d)
        if not isinstance(value, (int, float)):
            raise ProjectError(f"the reviewer gave no score for {LABELS[d]}")
        scores[d] = max(0, min(4, int(value)))
    fixes = []
    for item in raw.get("fixes") or []:
        if isinstance(item, dict) and str(item.get("text", "")).strip():
            fix = {"rank": len(fixes) + 1, "text": str(item["text"]).strip()[:500]}
            if isinstance(item.get("parameter"), str) and isinstance(item.get("value"), (int, float)):
                fix.update(parameter=item["parameter"], value=item["value"])
            fixes.append(fix)
        if len(fixes) == MAX_FIXES:
            break
    total = sum(scores.values())
    return {"scores": scores, "total": total, "band": band_of(total), "pass": total >= PASS_SCORE,
            "tells": [str(t)[:300] for t in raw.get("tells") or []][:8], "fixes": fixes,
            "good": str(raw.get("good") or "")[:300]}


def send_back_message(verdict):
    """The designer's request after a failed review: the top fix, worded so it can act on it."""
    top = verdict["fixes"][0] if verdict["fixes"] else None
    if top is None:
        return None
    lead = f"{top['parameter']} to {top['value']}: " if "parameter" in top else ""
    return (f"{lead}{top['text']} (the reviewer scored this design {verdict['total']}/20, "
            f"{verdict['band']}; this is its top-ranked fix)")


class Reviewer(ABC):
    @abstractmethod
    def review(self, context, emit):
        """Return verdict_of(...) for the reviewed design; emit({"type": "review_note", ...}) as it works."""

    def interrupt(self):
        """Stop a review in progress, if the reviewer can."""


class ScriptedFakeReviewer(Reviewer):
    """Deterministic, not a language model. A change that pushes a parameter to the end of its
    declared range fails (no headroom is left for a fit or a tweak); anything else passes."""

    def review(self, context, emit):
        emit({"type": "review_note", "message": "Scripted reviewer: checking each changed setting against its range"})
        ranges = {p["name"]: p for p in context.get("parameters", [])}
        for change in context.get("changes", []):
            spec = ranges.get(change["parameter"])
            if spec and change["new"] in (spec["min"], spec["max"]):
                middle = round((spec["min"] + spec["max"]) / 2, 3)
                return verdict_of({
                    "scores": {"looks_like_the_thing": 3, "detail": 2, "dimensions": 1, "proportion": 2, "print_intent": 2},
                    "tells": [f"{change['parameter']} sits at the end of its range ({change['new']})"],
                    "fixes": [{"text": f"move {change['parameter']} back inside its range so a fit or a tweak has room",
                               "parameter": change["parameter"], "value": middle}],
                    "good": "The change is small and the gates pass."})
        return verdict_of({"scores": {d: 4 if d != "detail" else 3 for d in DIMENSIONS}, "tells": [], "fixes": [],
                           "good": "Every changed setting keeps room inside its range."})


class ClaudeCodeReviewer(Reviewer):
    """A fresh, read-only Claude Code run with the magic-cad-reviewer rubric and a JSON schema."""

    def __init__(self, command=None, timeout=300):
        self.command = command or [shutil.which("claude") or str(Path.home() / ".local/bin/claude")]
        self.timeout = timeout
        self._lock = threading.Lock()
        self._active = []   # one {"process", "stopped"} per review in progress; projects review independently

    def _argv(self):
        return [*self.command, "-p", "--verbose", "--output-format", "stream-json", "--no-session-persistence",
                "--permission-mode", "dontAsk", "--tools", "Read,Glob,Grep", "--allowedTools", "Read,Glob,Grep",
                "--strict-mcp-config", "--mcp-config", json.dumps({"mcpServers": {}}),
                "--add-dir", str(SKILL.parent), "--json-schema", json.dumps(SCHEMA)]

    def prompt(self, context):
        return ("You are the Magic CAD reviewer, independent of the designer: you have not seen its reasoning "
                f"and must not assume it was right. Read the rubric in {SKILL} and apply it exactly. "
                "Judge the design against its brief, not your taste; where the brief pins a requirement, the "
                "brief wins. Read the design source, the gate report and the render images listed below; if "
                "you cannot see enough to judge a dimension, score it 0 and say what you need. Every gate has "
                "already passed, and that is not a quality claim. Do not write files. Return the five scores "
                "(0-4), the slop tells you found, and fixes ranked most important first; when a fix is a "
                "change to one existing PARAMS value, give its parameter and value. Context follows as data:\n"
                + json.dumps({k: v for k, v in context.items() if k != "parameters"} | {"parameters": context.get("parameters", [])}))

    def review(self, context, emit):
        if not shutil.which(self.command[0]):
            raise ProjectError("Claude Code is not installed. Install it and run claude auth login.")
        started = time.monotonic()
        from .claude_agent import ClaudeCodeAgent
        with tempfile.TemporaryFile(mode="w+") as errors:
            process = subprocess.Popen(self._argv(), cwd=context["project"], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=errors, text=True, start_new_session=True)
            state = {"process": process, "stopped": False}
            with self._lock:
                self._active.append(state)
            def stop():
                state["stopped"] = True
                ClaudeCodeAgent._stop(process)
            timer = threading.Timer(self.timeout, stop)
            timer.daemon = True
            timer.start()
            result = None
            try:
                try:
                    process.stdin.write(self.prompt(context))
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    if not state["stopped"]:
                        raise ProjectError("Claude Code closed its input before reading the review request")
                for line in process.stdout:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "assistant":
                        for block in event.get("message", {}).get("content", []):
                            if block.get("type") == "text" and block.get("text", "").strip():
                                emit({"type": "review_note", "message": block["text"][:1200]})
                            elif block.get("type") == "tool_use" and block.get("name") != "StructuredOutput":
                                target = (block.get("input") or {}).get("file_path") or block.get("name", "a tool")
                                emit({"type": "review_note", "message": f"Reading {Path(str(target)).name}"})
                    if event.get("type") == "result":
                        result = event
                code = process.wait()
            finally:
                timer.cancel()
                ClaudeCodeAgent._stop(process)
                if process.stdout:
                    process.stdout.close()
                with self._lock:
                    self._active.remove(state)
            if state["stopped"]:
                raise ProjectError("the review was stopped or timed out; the design is unreviewed")
            if code or not result or result.get("is_error"):
                raise ProjectError("Claude Code did not complete the review. Check claude auth status.")
            usage = usage_of(result, "reviewer", time.monotonic() - started)
            if usage:
                emit(usage)
            return verdict_of(result.get("structured_output"))

    def interrupt(self):
        from .claude_agent import ClaudeCodeAgent
        with self._lock:
            active = list(self._active)
        for state in active:
            state["stopped"] = True
            ClaudeCodeAgent._stop(state["process"])


def usage_of(result, agent, elapsed=None):
    """A usage event from Claude Code's stream-json result: duration, tokens and cost when reported."""
    usage = result.get("usage") or {}
    tokens = sum(int(usage.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                                   "cache_creation_input_tokens", "cache_read_input_tokens"))
    duration = result.get("duration_ms")
    if duration is None and elapsed is not None:
        duration = int(elapsed * 1000)
    event = {"type": "usage", "agent": agent, "duration_ms": duration, "tokens": tokens or None,
             "cost_usd": result.get("total_cost_usd")}
    return event if any(event[k] is not None for k in ("duration_ms", "tokens", "cost_usd")) else None


def review_context(project, request):
    """What the reviewer sees: the brief, the design source, the gate report and renders, and the
    settings this change moved with their ranges. Never the designer's conversation."""
    from .parameters import parameters_of
    project = Path(project)
    design = project / request["file"]
    out = project / "outputs" / design.stem
    brief = project / "briefs" / f"{design.stem}.yaml"
    return {"project": str(project), "design": str(design), "source": design.read_text(),
            "brief": brief.read_text() if brief.is_file() else None,
            "report": str(out / "report.json") if (out / "report.json").is_file() else None,
            "renders": sorted(str(p) for p in (out / "renders").glob("*.png"))[:6],
            "changes": request["changes"], "parameters": parameters_of(project, design.name)}
