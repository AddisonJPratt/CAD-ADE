# 3. An independent reviewer judges every kept change, and sends a failing fix back once

Date: 2026-11-08. Status: accepted. Ticket: #28.

## Context

The harness gates prove a design executes, measures and prints. They say nothing about whether it
is a good design, and the house rule is that a gate pass is never a design verdict. The
`magic-cad-reviewer` skill already defines that verdict: five dimensions scored 0-4 (20 in all),
bands from adopt-ready to reject, named slop tells and ranked fixes. #28 puts it in the loop.

## Decision

- **When.** After a change the owner kept (an accepted proposal) passes its gates, the engine runs
  the reviewer automatically. The run's status is `reviewing` until the verdict lands. That status
  is not terminal, so the project stays busy and nothing else edits it meanwhile. Other runs and
  rollbacks are not reviewed.
- **Independence.** The reviewer is its own adapter (`engine/reviewer.py`), separate from the
  designer's `AgentAdapter`. The Claude Code reviewer is a fresh `claude -p` with
  `--no-session-persistence` and read-only tools (Read, Glob, Grep), no MCP servers, and a JSON
  schema. It sees the brief, the source, the gate report, the renders and the changed settings
  with their ranges. It never sees the designer's conversation or the owner's request.
- **Pass mark.** 13/20 or more passes (adopt-ready or direction approved). 12 or less (rework or
  reject) fails.
- **Send back once.** A failed review's top-ranked fix becomes a new designer proposal
  automatically, once per change (`origin.round` 1). The owner still keeps or discards it like
  any proposal. If that kept fix fails review again, its fixes are listed and nothing is sent.
- **Unavailable reviewer.** If the reviewer can't run, the version is labelled unreviewed. The
  run does not fail.
- **Stored with the version.** The verdict is written to `.magic/reviews/<version id>.json` beside
  the gate verdicts, and `list_versions` returns `review: {total, band, pass}`. Studio's verdict
  card says "Prints, but needs rework" while the review fails, never "Ready to print".

## Consequences

- Every kept change spends one reviewer run of the owner's Claude usage, about a minute. Usage the
  CLI reports (tokens, cost, duration) is streamed as `usage` events and totalled in the session
  meter.
- The M0 designer edits one parameter, so a fix the reviewer words as a code change goes back
  as text. The designer may answer that it is beyond M0; that answer is shown, not hidden.
- Tests use `ScriptedFakeReviewer`: it fails a change that puts a setting at the end of its range
  and names the range midpoint as its fix. That makes the loop deterministic at both seams.
