# 4. The engine owns the designer's loop; the agent only writes design files

Date: 2026-11-08. Status: accepted. Ticket: #61.

## Context

M0 (#8) proved one bounded parameter edit through the agent adapter. The designer role has to
write a whole design from a brief card and keep going until every gate passes, sweep included. An
agent left to run the harness on its own decides for itself when it is done, what "pass" means and
how long to spend, and nothing stops it editing the brief or the library to make a gate go green.
The issue asks for gate runs streamed to the app, a user interrupt that leaves the project
untouched, a bounded budget that ends in a clear failure, and a proposal the owner accepts.

## Decision

- **Split.** The loop lives in the engine (`engine/designer.py`, `DesignLoop`, an `AgentAdapter`).
  Each attempt calls a `DesignWriter` to write files in the proposal's draft copy of the project,
  then the engine runs the gates itself. The writer is Claude Code for real
  (`engine/claude_designer.py`, one fresh `claude -p` per attempt) and `ScriptedFakeDesigner` in tests.
- **What the designer may write.** Top-level `designs/*.py` and `assembly.py`, nothing else. Claude
  Code's permission rules scope `Edit` to those paths, and the engine diffs the draft after every
  attempt: any other change is reverted, streamed as `refused_edit` and fed back. The brief card,
  library, printer settings and harness never change.
- **Gates.** Quick first (#80: build, geometry, printability; seconds), then the full project run
  with renders, Eyes (#79) and the sweep once quick passes. Every gate event streams on the proposal's
  event stream, framed by `attempt_started`, `gate_run_started` and a `gate_report`. A failing report,
  as text with the traceback tail, failing sweep samples and the render paths, is the next
  attempt's input. Designer gate runs hold the engine's one execution lock, like every other run.
- **Budget.** Attempts (default 6, at most 20) and wall time (default 45 min). Running out ends the
  proposal in `error` with a message naming the last failing gates. No partial design is proposed.
- **Result.** A full pass makes a proposal like any other: the changed files with before (often
  nothing) and after, previews, and the gate report. Accepting writes them, saves one version and
  re-runs the gates, which starts the reviewer (ADR 0003).
- **Interrupt.** Stops the Claude process, rolls the current attempt back in the draft and leaves
  the project folder and versions untouched. Resume redoes that attempt.

## Consequences

- The verdict that ends the loop is the harness's, not the agent's claim, and the full run is what
  accepting repeats, so a proposal that reached "ready" passes again on the saved version unless
  the environment changed.
- Every attempt starts a fresh Claude context with the brief, the printer and clearance table, the
  previous source (in the draft) and the last gate report. Nothing carries over except files.
- Within an attempt Claude has no shell. It checks its own draft through magic-cad, which the
  designer starts with `MAGIC_CAD_PROJECT` set to the draft, so `run_check` (quick mid-loop, full
  before finishing), `measure_file` and `min_gap` resolve paths there and refuse anything outside,
  the repo included. Their checks write under the draft's `outputs/`, which is never proposed.
- The unit of work is a set of files, so the planner's multi-part briefs (#82) need no new seam.
- A project can hold only a brief card (`create_project_from_brief`); `require_versioned` and
  `project_printer` accept it, and `run_project` still refuses it until a design exists.
