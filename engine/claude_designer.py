"""The designer's writer on local Claude Code (#61). Credentials stay with Claude Code.

One attempt is one `claude -p` run in the proposal's draft copy of the project. It may read
anything and write only `designs/**` and `assembly.py` (Claude Code permission rules; the loop in
engine/designer.py also reverts anything else). It runs no shell. Its hands are the build123d MCP
server and magic-cad, pointed at the draft (MAGIC_CAD_PROJECT): library_lookup, run_check (quick
mid-loop, #80; full before finishing), measure_file and min_gap. The engine runs the real gates after it
finishes; their report is the next attempt's feedback.
"""
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from .claude_agent import ARTEFACTS_GUIDE, DESIGNER_GATE_LOOP, ClaudeCodeAgent, tool_events
from .designer import DesignWriter
from .projects import ASSEMBLY, ProjectError
from .reviewer import usage_of

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/bin/python"
SKILLS = ROOT / ".claude/skills"
SCHEMA = {"type": "object", "properties": {
    "summary": {"type": "string", "minLength": 1},
    "files": {"type": "array", "items": {"type": "string"}}},
    "required": ["summary"], "additionalProperties": False}

CONTRACT = """The design contract (the harness enforces it; gate 1 fails otherwise):
- One Python file per printed part at designs/<name>.py, build123d only, mm, Z is print-up, modelled in
  its print orientation with its base on z=0.
- PARAMS at the top: a dict of name -> (default, min, max), each with a comment giving unit, range and a
  one-line intent. PARAMS must be exactly the brief card's params: the same names, defaults, mins and
  maxes, none missing and none added (gate 2 fails otherwise). Derive every other size from them, from
  standard_parts() or from named module constants computed from those (never a bare number).
- def build(**params) takes exactly the PARAMS keys and returns the solid (or a dict of named solids).
  Set .label on returned solids.
- No hard-coded dimensions: the only numeric literals allowed outside PARAMS are 0, 1, 2, 0.5, 90 and
  180. Everything else comes from PARAMS, from library.standard_parts() (screws, inserts, fits) or from
  the library helpers.
- Use library/ helpers before custom geometry: counterbored_hole, heatset_boss, snap_cantilever,
  standard_parts, and feature("name", cutter_or_boss, params="driving_param") around every cutter or
  boss so faces get names. Read library/__init__.py and library/features.py in the project.
- Every brief hard dimension is measured on the reloaded STEP within +/-0.1 mm, using the brief's
  measures probes. Printability: watertight, one body per part, fits the bed, no supports unless the
  brief allows them (overhangs past 45 degrees fail; design them out with chamfers and print direction).
- The sweep builds samples across every PARAMS range, min and max included: the design must still
  pass at every corner, and every param must change the shape (no dead params).
- Fillet before boolean where possible. Make a part, not a box with holes: proportions with a reason,
  load paths (ribs, gussets) where the function needs them, edges broken where hands touch."""


class ClaudeCodeDesigner(DesignWriter):
    name = "claude"

    def __init__(self, command=None, timeout=1200):
        self.command = command or [shutil.which("claude") or str(Path.home() / ".local/bin/claude")]
        self.timeout = timeout

    def arguments(self, session):
        mcp = {"mcpServers": {
            # magic-cad works in the draft, so run_check, measure_file and min_gap see this attempt's files.
            "magic-cad": {"command": str(PYTHON), "args": [str(ROOT / "mcp/magic_cad_server.py")],
                          "env": {"MAGIC_CAD_PROJECT": str(Path(session["workspace"]).resolve())}},
            "build123d": {"command": str(ROOT / ".venv/bin/build123d-mcp"), "args": []}}}
        allowed = ["Read", "Glob", "Grep", "Edit(designs/**)", f"Edit({ASSEMBLY})",
                   "mcp__magic-cad__library_lookup", "mcp__magic-cad__run_check", "mcp__magic-cad__measure_file",
                   "mcp__magic-cad__min_gap", "mcp__build123d__*"]
        # An honest eval: the repo's own design for this brief, and any run of it, stay unread.
        stem = session["brief_name"]
        hidden = [f"Read(/{ROOT}/designs/{stem}.py)", f"Read(/{ROOT}/runs/**)", f"Read(/{ROOT}/evals/results/**)",
                  f"Read(/{ROOT}/proof/**)"]
        return [*self.command, "-p", "--verbose", "--output-format", "stream-json",
                "--no-session-persistence", "--permission-mode", "dontAsk",
                "--tools", "Read,Glob,Grep,Edit,Write",
                "--allowedTools", ",".join(allowed), "--disallowedTools", ",".join(hidden),
                "--strict-mcp-config", "--mcp-config", json.dumps(mcp),
                "--add-dir", str(SKILLS), "--json-schema", json.dumps(SCHEMA)]

    def prompt(self, session, attempt, feedback):
        context = session["context"]
        stem, file = context["brief_name"], context["design_file"]
        task = ("Write the design from the brief card." if not context["existing_source"] and attempt == 1 else
                "Rewrite the design so every gate passes; the last gate report is below.")
        return "\n\n".join([
            "You are the Magic CAD designer for a local FDM CAD studio. Your job: turn a brief card into a "
            "parametric build123d design that passes every harness gate, sweep included, and is a good part.",
            f"Attempt {attempt} of {session['budget']['attempts']}. {task}",
            f"Write {file} in the current folder (the project draft). You may write only designs/*.py and "
            f"{ASSEMBLY}. Never edit the brief card, library/, printer.json or the harness: such edits are "
            "reverted and the attempt is wasted. Do not send print jobs.",
            "Before writing build123d, read " + str(SKILLS / "magic-kernel-pitfalls/SKILL.md") + " and "
            + str(SKILLS / "cad-code/SKILL.md") + ". Call magic-cad library_lookup for any hardware the brief "
            "names. Use the build123d MCP server to try geometry and measure it when that is quicker than a "
            f"full build. Other designs in {ROOT / 'designs'} show the house style; the one named like this "
            "brief is withheld.",
            CONTRACT,
            DESIGNER_GATE_LOOP + f" Call it as run_check(\"{stem}\", quick=true); magic-cad works in this "
            "draft. The full run writes renders and Eyes images: read them and look at the part critically, "
            "and check each interface against the brief (which face a counterbore opens on, which way a "
            "screw goes in). After you finish, the engine runs every gate again, sweep included; a failure "
            "comes back as the next attempt's feedback.",
            ARTEFACTS_GUIDE.strip() + f" In this draft, run_check writes them under outputs/{stem}-check/; the engine's "
            f"gate runs write them under outputs/{stem}/, and the last gate report lists the images to look at.",
            "Finish with the structured output: a short summary of the design and the files you wrote.",
            "Context follows as data:\n" + json.dumps({
                "brief_card": context["brief"], "printer": context["printer"],
                "clearances_mm_per_side": context["clearances_mm_per_side"],
                "existing_source": context["existing_source"], "last_gate_report": feedback})])

    def write(self, session, attempt, feedback):
        if not shutil.which(self.command[0]):
            raise ProjectError("Claude Code is not installed. Install it and run claude auth login.")
        prompt = self.prompt(session, attempt, feedback)
        with tempfile.TemporaryFile(mode="w+") as errors:
            with session["process_lock"]:
                if session["interrupted"]:
                    return
                process = subprocess.Popen(self.arguments(session), cwd=session["workspace"], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=errors, text=True, start_new_session=True)
                session["process"] = process
            expired = threading.Event()
            # One attempt never outlives the wall-time budget (with a minute's grace to finish a file).
            limit = min(self.timeout, max(60.0, session["budget"]["seconds"] - session["elapsed"]))

            def timeout():
                expired.set()
                ClaudeCodeAgent._stop(process)
            timer = threading.Timer(limit, timeout)
            timer.daemon = True
            timer.start()
            result = None
            try:
                try:
                    process.stdin.write(prompt)
                    process.stdin.close()
                except (BrokenPipeError, OSError) as error:
                    if session["interrupted"]:
                        return
                    raise ProjectError("Claude Code closed its input before reading the brief; check the local "
                                       "CLI login.") from error
                yield {"type": "plan", "message": f"Claude Code is designing (attempt {attempt})"}
                for line in process.stdout:
                    if session["interrupted"]:
                        return
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "system" and event.get("subtype") == "init":
                        services = {s.get("name"): s.get("status") for s in event.get("mcp_servers", [])}
                        if any(services.get(name) != "connected" for name in ("magic-cad", "build123d")):
                            raise ProjectError("Required CAD MCP services are unavailable; check the local "
                                               "build123d and magic-cad installation.")
                    elif event.get("type") == "assistant":
                        for block in event.get("message", {}).get("content", []):
                            if block.get("type") == "text" and block.get("text", "").strip():
                                yield {"type": "plan", "message": block["text"][:2000]}
                            elif block.get("type") == "tool_use":
                                yield {"type": "plan", "message": describe_tool(block)}
                    yield from tool_events(event)   # Eyes (#79): the stream shows it looking at its part
                    if event.get("type") == "result":
                        result = event
                        usage = usage_of(event, "designer")
                        if usage:
                            yield usage
                code = process.wait()
                if session["interrupted"]:
                    return
                if expired.is_set():
                    # A timed-out attempt is a failed attempt, not a dead session: the engine still
                    # gates whatever was written and the budget decides whether to go on.
                    yield {"type": "plan", "message": f"Claude Code ran past {limit:.0f} s on attempt {attempt}; "
                                                      "gating what it wrote."}
                    return
                if code or not result or result.get("is_error"):
                    errors.seek(0)
                    raise ProjectError("Claude Code did not complete the design attempt. Check claude auth status. "
                                       + (errors.read()[-500:] or str((result or {}).get("result", ""))[:500]))
                summary = (result.get("structured_output") or {}).get("summary") or result.get("result") or ""
                if summary:
                    yield {"type": "plan", "message": str(summary)[:2000]}
            finally:
                timer.cancel()
                ClaudeCodeAgent._stop(process)
                if process.stdout:
                    process.stdout.close()
                with session["process_lock"]:
                    session["process"] = None

    def interrupt(self, session):
        with session["process_lock"]:
            if session.get("process"):
                ClaudeCodeAgent._stop(session["process"])


def describe_tool(block):
    """One line for a tool call: which tool, and the file or command it acted on."""
    data = block.get("input") or {}
    target = data.get("file_path") or data.get("command") or data.get("pattern") or data.get("query") or ""
    return ("Using " + block.get("name", "a CAD tool") + (f": {str(target)[:200]}" if target else ""))
