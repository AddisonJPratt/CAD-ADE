# Magic CAD: project context

Designs are parametric build123d Python; the harness (`magic.py`) verifies them. Keep this file short.

## Printer: Elegoo Centauri Carbon 2
- Build volume: 256 x 256 x 256 mm; nozzle: 0.4 mm; single colour.
- PLA and PETG are selectable per project. Fit clearances are uncalibrated starting values.
- Supports: off by preference. Design around them; a brief must allow them explicitly.
- The canonical profile and material settings are in `library/printer_profiles.py`.

## Clearances: starting values, not yet calibrated on a real print
| Fit | Per-side clearance (mm) |
|---|---|
| Sliding | 0.25 |
| Press | 0.10 |
| Print-in-place | 0.35 |

## House style
- Units: mm. Z is print-up; a design is modelled in its print orientation with its base on z=0.
- `PARAMS` at the top of the file, each with unit, range and one-line intent in a comment.
- Every feature is derived from PARAMS or `library/standard_parts.json`, never from hard-coded numbers.
- Name features in comments and variables; set `.label` on the returned solids. Wrap a cutter
  or boss in `feature("name", shape, params="driving_param")` from `library` so Studio can name
  its faces, and the parameter behind them, when picked.
- Fillet before boolean where possible.
- Use `library/` helpers before writing custom geometry.

## Guardrails
- No weapon or firearm components; decline those briefs.
- Original designs only: no trademarked characters or someone else's licensed models.
- Never send a print job. Printer actions always need the user's confirmation.

## Workflow
`.venv/bin/python magic.py run designs/<x>.py` must exit 0 before calling a design verified.
Mid-session, `magic.py check designs/<x>.py --quick` (build, geometry, printability; seconds) is
for iterating only: a quick pass is a draft and never counts as verified.
If a gate fails, fix the design or the harness; never weaken the gate.

## Tools wired into this project
- **build123d MCP server** (user scope, tools allowed): drive build123d interactively —
  execute snippets, measure, render, export — for exploration and step-by-step building.
  The harness still gates anything that ships: an MCP-built shape is a draft until
  `magic.py` passes it on the reloaded files.
- **Project skills** (`.claude/skills/`, also installed globally): `magic-kernel-pitfalls`
  (consult before debugging strange kernel behaviour), `magic-cad-reviewer` (the scored
  design verdict after gates pass), `magic-slicer-check` (real slicer CLI ground truth),
  `magic-print-log` (print evidence → calibrated clearances), plus `cad-code`, the
  cad-3d-printing reference set, Impeccable, and Superpowers.

## Design quality: no AI slop (Impeccable + CAD critique gate)

Two different surfaces, two different tools. Do not confuse them.

### UI surfaces (web app shell, any HTML/CSS/JS) — Impeccable skill
- The Impeccable skill (pbakaus/impeccable, installed in `.claude/skills/impeccable/`
  and globally in `~/.claude/skills/impeccable/`) is mandatory for any interface work.
- Before calling UI work done: run an Impeccable `critique` (scored UX review) and
  `audit` (a11y / performance / responsive, findings ranked P0–P3) on the target, and
  run the deterministic detector (`scripts/impeccable detect <target>`); fix P0/P1
  findings and every slop tell it flags.
- Known slop tells (detector rules + craft floor): Inter-for-everything, purple-to-blue
  gradients, gradient text, cards nested in cards, same-size icon+heading+text card
  grids as page structure, hero-metric template, kickers/eyebrows above headings
  (banned), gray text on colored backgrounds, glass/blur as decoration, emoji or
  unicode glyphs as icons, generic rounded-square icon tiles above every heading.
- "Make it pop" is not a brief. Use the skill's vocabulary (bolder / quieter /
  distill / typeset / layout / polish) with a named target.

### CAD designs — critique gate (Impeccable's reviewer model, adapted)
Impeccable's detector does not scan geometry; this is the CAD equivalent, applied
by a reviewer who did not write the design (per the vision doc's reviewer agent):
- CAD slop tells — any one is a fix-first finding, not a nit:
  - Default-everything: uniform fillet radius on every edge, uniform wall thickness
    with no reason, a plain box/cylinder with a hole called finished.
  - No design intent in proportions: dimensions that are all round defaults
    (10/20/50) with no brief or functional reason.
  - Detail-free surfaces where the real object has detail (panel lines, ribs,
    fasteners, labels) — "looks like a frame, not the thing."
  - Features copied from the library without checking they fit this part's loads,
    orientation, or print direction.
  - A render presented as evidence that no one actually looked at critically.
- The reviewer scores the design against the brief (function, proportions, detail,
  finish) and returns specific fixes, ranked. A design that passes the harness but
  fails critique is NOT done — same as SnapWorks: gate pass ≠ design verdict.
- The brief wins: pinned aesthetics/materials/dimensions override these tells,
  exactly as Impeccable's craft floor defers to a pinned brief.

## Agent skills

### Issue tracker

GitHub issues on AddisonJPratt/CAD-ADE via `gh`; the spec is a parent issue, tickets are sub-issues with native blocking links. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary; `ready-for-agent` = AFK loop may take it, `ready-for-human` = needs Addison's review/demo. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root, created lazily. See `docs/agents/domain.md`.
