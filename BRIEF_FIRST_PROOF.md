# Build brief — The First Proof: "make a holder for this"

Read `docs/PRODUCT_VISION_UX_SPEC.md` first — it governs. Then CLAUDE.md and
README.md. Work only in this folder. Python is `.venv/bin/python`. The harness makes
no LLM calls; this app calls the harness, never the other way round.

## What this is

The plainest working version of the product's whole loop, per the spec's build
sequence. Not beautiful yet — complete. A user gives three caliper readings for an
everyday object, gets ONE gated holder design on a plain page with one download
button, prints it, and answers Perfect / Too tight / Too loose. That answer adjusts
the clearance for next time and is logged. The studio UI in `ui/` is mission control;
this is the customer-shaped loop, in function language, no parameter names.

## Deliverable 1 — two parametric holder templates

Both in `designs/`, both following the design contract, both must pass a full
`magic.py run` (gates + sweep) at their defaults before anything else proceeds:

1. `holder_clip.py` — a wall clip for a cylindrical object (the spec's bike-pump
   example). Key param: `barrel_dia`. Screw-mounted back plate, compliant clip arms
   whose opening derives from barrel_dia + the current fit clearance (see profile
   store below). Defaults: 38 mm barrel.
2. `holder_cradle.py` — a wall cradle for a rectangular object. Key params:
   `obj_w`, `obj_d`, `obj_h` (it supports the object from below with a front lip).
   Defaults: 90 × 35 × 120 mm.

For each, a brief in `briefs/` whose hard dimensions are honestly measurable with the
existing probes (bbox, hole spacing/count). If a fit dimension can't be probed, say so
in the brief's assumptions — do not invent a probe or fake a measurement.

## Deliverable 2 — the proof app (`proof/`)

Stdlib-only server (`proof/server.py`, port 8766) + plain HTML/CSS/JS, warm neutral
canvas, one accent, humanist system sans, object-first layout. No frameworks, no CDN.
Pages/flow:

1. **Ask** — "What are we holding?" A short form in plain language: object name,
   shape (round / rectangular), three caliper readings in mm (diameter+length, or
   width+depth+height), mount (screws — only option wired; adhesive shown disabled
   as "coming later", honestly), material (default PETG). One button: **Make my
   holder**.
2. **Make** — on submit the server: picks the template, writes a generated brief to
   `briefs/generated/<slug>.yaml` with the readings as params (clearance taken from
   the profile store), runs the harness in a subprocess, and shows the result page:
   the part's renders, a plain-language summary ("Holds a 38 mm barrel · screws to
   the wall · no supports needed" style — derived from the actual report, e.g.
   overhang/support status and volume→filament grams estimate), gate status in plain
   words ("Checked: size, strength of shape, printability" — PASS only if the
   harness passed), and ONE primary button: **Download the print file** (the STL),
   enabled only when the harness passed. If gates fail, no download — the page says
   what failed in plain language and the details go to the run report.
3. **Prove** — under the result: "Printed it? How did it fit?" Three big buttons —
   **Perfect · Too tight · Too loose** — plus a smaller **It broke**. Clicking one:
   - appends one JSON line to `proof/outcomes.jsonl`:
     {ts, object, template, joint_type, material, printer:"default",
      clearance_used_mm, result}
   - updates `proof/profile.json`: the per-joint clearance adjustment
     (too_tight → +0.20 mm, too_loose → −0.20 mm, perfect/broke → no change;
     broke also flags the outcome for review). The next Make run for that joint uses
     profile clearance = template default + accumulated adjustment, and the brief it
     writes records the clearance it used.
   - appends a formatted entry to `prints/PRINT_LOG.md` per the magic-print-log
     skill's format.
   - replies with the spec's move: for Too tight / Too loose, offer the corrected
     version immediately ("Opened the clip 0.2 mm — make the new one?" linking back
     to Make with the same readings).
4. **Shelf (plain)** — a simple list page of past makes from outcomes.jsonl +
   generated briefs: object name, template, date, fit result if given. Proof photos
   are later; don't fake them.

## Deliverable 3 — mission-control reposition (light touch)

In `ui/`: the app title/header becomes "Magic CAD · Mission Control" with one line
in `ui/README.md` noting the studio pages are the internal view and the customer
loop lives in `proof/`. Nothing else changes there.

## End-to-end proof you must run

Drive the whole loop once with the spec's example: bike pump, round, 38 mm barrel,
screws. Show: generated brief contents, harness result (gates + sweep at defaults was
already proven for the template; the generated instance must pass `run`), the result
page HTML contains the download link, the STL downloads (curl, bytes > 0), then a
simulated Prove click of "Too tight" and the resulting diffs: outcomes.jsonl line,
profile.json adjustment = +0.20 for the clip joint, PRINT_LOG entry. Quote all of it
in your final message.

## Rules

- Numbers in the customer flow only as outcomes ("fits a 38 mm barrel"), never as
  parameter names or dimension walls. Gate PASS is never reworded into print
  confidence the product hasn't earned — the copy says "checked", not "guaranteed
  to fit"; the Prove step is what earns confidence.
- Never weaken a gate. A generated instance that fails gets reported, not shipped.
- No new dependencies. No network. Subprocess timeouts generous (harness runs take
  minutes) with structured failure pages, not stack traces, in the browser.
- Final message: files built, template gate/sweep numbers, the end-to-end proof
  transcript summary, and flagged assumptions (especially any fit dimension the
  probes can't measure).
