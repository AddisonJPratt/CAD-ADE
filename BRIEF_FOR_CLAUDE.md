# Magic CAD — Phase 1 Build Brief

You are building Phase 1 of "Magic CAD: An AI Engineering Harness for 3D Models"
(a personal design studio: loose input → brief card → parametric Python CAD →
verification loop → printable STL/STEP + renders + report).

Source vision doc is at `~/workspace/user/files/Magic-CAD-AI-Engineering-Harness.pdf`
in the main workspace — the principles below are distilled from it. Do NOT try to
build the whole vision. Build ONLY the Phase 1 slice below, end-to-end and working.

## Working directory and environment

- Work ONLY in `~/workspace/magic-cad/` (this folder). It is a fresh project, not
  the SnapWorks sprint workspace — do not touch SnapWorks files.
- Python: use `~/workspace/magic-cad/.venv/bin/python` for everything
  (build123d, trimesh, manifold3d, numpy, matplotlib, pyyaml are installed there).
  If build123d is missing, report it in README and stop — do not pip install
  into other environments.
- All code must run headless on Linux. No GUI, no display.

## What Phase 1 is (the gate)

Phase 1 gate, in the doc's terms: *a functional part described in a brief card
comes back as verified, parametric build123d code + STL + STEP + renders + a
machine-readable check report, and a parameter sweep proves it is parametric,
not just working at defaults.*

## Deliverables — build all of these

### 1. Project context file: `CLAUDE.md`
Short, always-loaded, per the doc: printer placeholder block (bed 250×250 mm,
0.4 mm nozzle, PLA, supports-off preference — clearly marked EDIT ME), calibrated
clearances table (sliding 0.25, press 0.10, print-in-place 0.35 mm — marked as
starting values), units mm, house style (parameters at top with units/ranges/intent,
named features, fillet-before-boolean where possible). Also the guardrails:
no weapon components, original designs only, never send a print job.

### 2. Brief card format: `briefs/` + schema
- A brief is a YAML file: `name, function, hard_dimensions (dict of name→mm),
  interfaces, soft_preferences, assumptions, params (name → {value, min, max, unit, intent})`.
- Ship one example: `briefs/wall_bracket.yaml` — an L wall bracket, 60 mm wide,
  holds a shelf load, 2× M4 wall holes, 2× M4 shelf holes. You choose sensible
  remaining dimensions and record them as assumptions.

### 3. The harness: `harness/` package + CLI `magic.py`
Few, general tools per the doc. CLI usage:
`python magic.py run <design.py> [--brief brief.yaml] [--out runs/<name>]`
`python magic.py sweep <design.py> [--samples N]`
`python magic.py check <design.py>` (alias for run without exports)

Design file contract: a design is a Python file that
- declares `PARAMS = {name: (value, min, max)}` (or a dict of dicts — pick one, document it),
- defines `build(**params)` returning a build123d solid (or list of named solids),
- contains NO hard-coded dimensions outside PARAMS-derived values in features.

The harness runs checks cheapest-first and writes `report.json` + `report.md`:
1. **Execute** — import/run the design in a subprocess with a timeout; capture traceback.
2. **Geometry** — exactly the expected number of valid closed solids (`is_valid()`),
   volume > 0, bounding box; compare bbox + any named hard dimensions from the brief
   within ±0.1 mm; multi-part: pairwise overlap volume ≈ 0 (use build123d/OCC or
   exported-mesh boolean via manifold3d — pick what works, document it).
3. **Printability** — on the exported mesh (reload STL from disk, never trust in-memory):
   watertight, single component, bed fit vs 250×250, overhang: % of downward faces
   >45° from straight down (report %, fail if >15% unless brief allows supports),
   min wall/feature: report thinnest section via a documented approximation
   (e.g. section sampling) — a report value is fine, don't fake precision.
4. **Renders** — PNG standard views (iso, front, top, side) + one section cut,
   rendered from the reloaded mesh with matplotlib (reuse a simple numpy
   z-buffer / Poly3D approach — flat QA renders are acceptable HERE because
   these are engineering check renders, label them as such).
5. **Exports** — STL + STEP into the run folder.

Parameter sweep: sample each param at min / default / max (and a few combos,
cap total runs), rebuild + geometry-check each; report pass share. A design
that only passes at defaults must FAIL the sweep gate.

Exit code 0 only if all gates pass. `report.md` must be human-readable:
checks table, measured vs spec, sweep result, assumptions surfaced.

### 4. Feature library: `library/`
Three tested features as importable build123d helpers, each with a docstring
stating its param range:
- `counterbored_hole(screw="M4")` — from the standard-parts DB, not hard-coded.
- `heatset_boss(screw="M4")` — boss OD / insert hole from DB.
- `snap_cantilever(length, width, thickness, deflection)` — beam with root fillet,
  flex in layer plane.
Plus `library/standard_parts.json`: M3/M4/M5 screws (clearance + tap + counterbore),
heat-set inserts M3/M4, 608 bearing (8×22×7), NEMA17 mount spacing (31 mm),
2020 extrusion slot width, Gridfinity pitch (42 mm). Real values.

### 5. Demo design: `designs/wall_bracket.py`
A real parametric bracket implementing `briefs/wall_bracket.yaml`, using at least
the counterbored-hole helper, passing ALL harness gates including the sweep.
This is the proof, not a toy: gusset, fillets, correct hole spacing from params.

### 6. Eval starter: `evals/EVALS.md` + 5 briefs
Five one-paragraph eval briefs (phone stand, wall bracket (the demo), cable clip,
simple 2-part box+lid, planter pot) in the brief YAML format, so the eval set
can grow to 30–50. Note the metrics table from the doc (Runs / Dimensional /
Printable / Parametric / Time).

### 7. `README.md`
What it is, how to run the demo end-to-end (exact commands), what Phase 1 does
NOT do (slicer integration, vision reviewer agent, electronics/mechanisms/SDF
modules, FEA, web UI — phases 2–5), the phase roadmap in 5 lines, and any
assumptions or blockers you hit, flagged explicitly.

## Rules

- Verify your own work: run the harness on the demo design yourself, reload
  STLs from disk, and show the passing report in your final summary. If a gate
  fails, fix the design/harness — don't weaken a gate to pass.
- Deterministic harness code does checks; no LLM calls inside the harness.
- Keep files small and readable. No dependencies beyond what's in the venv.
- Write a short `BUILD_LOG.md` noting key decisions (e.g. build123d vs CadQuery:
  doc says test both — you are choosing build123d for Phase 1; say why in 2 lines).
