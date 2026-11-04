# Product

<!-- impeccable:product-schema 1 -->

Written from `BRIEF_UI.md`, `CLAUDE.md` and the repository in a non-interactive session.
No init interview ran, so nothing here has been confirmed in conversation. Facts marked
(inferred) are readings of those files; correct them freely.

## Platform

web

## Stack

Pinned by the brief: Python stdlib `http.server` plus plain HTML, CSS and JS. No
frameworks, no CDN, no webfonts, no new dependencies.

## Users

One person: the owner of a one-person engineering studio who directs agents that write
parametric CAD. They read the studio's state between agent runs, usually at a desk, often
late (inferred from the brief's "drafting table at night"). They are fluent in
millimetres, tolerances, and print constraints, and need no explanation of those terms.

## Product Purpose

Magic CAD turns a written brief into a parametric build123d design, and a harness
(`magic.py`) verifies it from files reloaded off disk. The studio UI is the place to read
what the harness found: which designs exist, which gates passed, how measured geometry
compares with the brief, and how much of the eval set has a design at all.

Success: the owner can answer "what can I trust right now, and what has not been checked?"
in seconds, without opening a JSON file.

## Positioning

A workbench over evidence the harness already produced. The UI never computes a verdict
and never pretends to one: it reports gate results, names the file each came from, and
leaves a gap visible when something has not run.

## Operating Context

- Runs locally from the project root: `.venv/bin/python ui/server.py`, port 8765.
- Data comes from `designs/`, `briefs/`, `evals/briefs/`, `runs/*/report.json`,
  `evals/results/*/eval_report.json`, and `library/standard_parts.json`.
- Agents write those files; the UI only reads them.
- Renders are QA images from the reloaded STL: flat z-buffer, white background.

## Capabilities and Constraints

Now, read-only: the Studio home view (the part in 3D with a build replay), and Mission
Control's views of overview, design report, brief card, evals, and library.

Not yet wired (a later phase): rebuilding from changed parameters and running a check from
the UI. The brief's sliders are a labelled draft affordance and the Run check button stays
disabled until that wiring exists.

Project rules that bind this surface:

- Never send a print job. Printer actions always need the user's confirmation.
- A gate pass is not a design verdict. Harness results must not read as design approval.
- Pass rate and coverage are separate figures and must never merge into one number.
- Printer values and clearances in `CLAUDE.md` are placeholders, not calibrated.

Terms: gate, sweep, dead param, brief, hard dimension, probe, NO_DESIGN, check mode (no
exports kept), run mode (exports kept), quick eval (sweep not run).

## Brand Commitments

Name: Magic CAD. The briefs bind both visual languages; `DESIGN.md` records them.

## Evidence on Hand

- `runs/`: real reports, renders and exports, which another session is adding to.
- `evals/results/`: eval reports. Read the newest for current pass rate and coverage.
- `prints/` is empty. No part has been logged as printed, so no physical result may be
  implied anywhere.

## Product Principles

1. Show the source. A figure without its file and timestamp is a claim, not evidence.
2. Absence is data. NO_DESIGN, NOT RUN and "—" are shown at full legibility.
3. Quiet when fine, loud when not. Attention is spent on what needs action.
4. No fake interactivity. A control that does nothing yet says so beside it.

## Accessibility & Inclusion

WCAG 2.1 AA, set by the brief: semantic landmarks, visible focus, passing contrast,
keyboard-reachable navigation, usable at 390 px wide. State is never carried by color
alone.
