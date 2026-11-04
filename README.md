# Magic CAD: Phase 1

A personal design studio's core loop: a brief card goes in, and verified parametric
build123d code, STL, STEP, QA renders and a machine-readable check report come out. A
parameter sweep proves the part is parametric, not just working at its defaults. The
harness is deterministic and makes no LLM calls.

## Run the demo

From this folder (headless Linux; about 4 minutes per command on 4 cores):

```bash
.venv/bin/python magic.py run designs/wall_bracket.py --brief briefs/wall_bracket.yaml --out runs/wall_bracket
.venv/bin/python magic.py sweep designs/wall_bracket.py --brief briefs/wall_bracket.yaml
.venv/bin/python magic.py check designs/wall_bracket.py
.venv/bin/python tests/run_tests.py    # library tests + harness negative controls, about 6 min
```

Results land in `runs/wall_bracket/`: `report.md`, `report.json`, `bracket.stl`,
`bracket.step` and `renders/`. Exit code is 0 only if every gate passes (1 = a gate failed,
2 = unusable arguments).

- `run` does all gates, including the sweep.
- `check` is `run` without keeping STL/STEP; it writes to `runs/<design>-check/`.
  `check --no-sweep` skips the sweep and marks it NOT RUN, for fast feedback only.
- `sweep` does the sweep alone; it writes `sweep.md`/`sweep.json` to `runs/<design>-sweep/`.
- `evals` runs every eval brief that has a design; see `evals/EVALS.md`. The `magic-cad` MCP
  server wraps these commands; see `mcp/README.md`.
- `--brief` defaults to `briefs/<design stem>.yaml` if present. Without a brief, hard
  dimensions are not checked, and the report says so.
- `--samples N` caps sweep runs. N must cover default + min and max of every param, so
  it can't quietly skip a range. The default is that plus 6 combos; the hard limit is 64.

## Design file contract

```python
PARAMS = {"name": (default, min, max)}   # tuples; ints stay ints in the sweep
EXPECTED_SOLIDS = 1                      # optional; a brief's expected_solids wins
def build(**params): ...                 # solid, or a list / dict of named solids
def section_plane(**params): ...         # optional: {"axis": "Y", "offset": mm} for the QA section
```

Model in print orientation: Z is print-up, base on the bed. Numeric literals outside
`PARAMS` fail the Execute gate, except 0, 1, 2, 0.5, 90 and 180. Put library and database
lookups behind helpers.

## Brief card

YAML with `name, function, hard_dimensions, interfaces, soft_preferences, assumptions,
params` (`name: {value, min, max, unit, intent}`). I added three fields the checks need:

- `measures` (required for each hard dimension): how to measure it, so the design can't
  grade itself. Probes: `bbox_x|y|z`, `hole_spacing`, `hole_count` (with `axis`, `dia`), and
  optional `part`.
- `allow_supports` (default false).
- `expected_solids` (default 1).

A hard dimension with the same name as a param follows that param during the sweep.

## Gates, cheapest first

| # | Gate | Checks |
|---|---|---|
| 1 | Execute | Contract lint; design run in a subprocess with a timeout; traceback captured |
| 2 | Geometry | Exact solid count, valid, closed, volume > 0; hard dimensions ±0.1 mm on the reloaded STEP; design and brief params agree; pairwise overlap ≤ 0.1 mm³ |
| 3 | Printability | On the STL reloaded from disk: watertight, single component, 250×250 bed fit, bed contact, both overhang metrics ≤ 15 % unless supports are allowed, STL volume within 1 % of STEP; thinnest section reported |
| 4 | Renders | Iso, front, top, side and a section, from the reloaded STL. Labelled as flat QA renders |
| - | Sweep | Min/max per param plus combos; every sample must pass geometry and every param must change the shape |
| 5 | Exports | STL and STEP in the run folder, only if everything above passed |

**Overlap method:** manifold3d boolean on STLs reloaded from disk.
**Thinnest section:** eight section planes per axis, rasterized at about 0.2 mm, then a
morphological opening scan. It is an approximation: long walls read within 0.4 mm, short
tabs can read high, and features between planes can be missed. It is reported, and only warns.

## Feature library

`library/`: `counterbored_hole`, `heatset_boss`, `snap_cantilever`, plus
`standard_parts.json`. Each docstring states its valid range.

## Flagged assumptions and blockers

- **Overhang definition.** The brief says "% of downward faces >45° from straight down".
  Taken literally, that counts steep, printable faces and misses flat ceilings. The vision
  doc says "overhangs past about 45°". I gate on both: the literal metric, and a
  `support_risk_pct` for off-bed faces within 45° of straight down. Both are shares of all
  downward area, bed contact included. `tests/fixtures/ceiling.py` shows why the second is needed.
- **Sweep gate requires 100 %** of samples, and also fails params with no effect. The brief
  doesn't set a share; this is the strict choice. Printability per sample is reported
  but not gated, as the brief specifies geometry only.
- **Heat-set insert values are from memory.** The datasheet lookup was not permitted during
  the build, so check `heatset_inserts` against your vendor's sheet before printing.
  Other database values are standard (ISO 273/4762, 608, NEMA17, Gridfinity); the 2020
  slot width of 6 mm fits common profiles, but slots vary by vendor.
- **Bracket load is a hand estimate,** with no FEA and no real print: 5 kg at the shelf's
  front edge gives about 1.7 MPa in the plate beyond the gusset and about 58 N per wall
  screw. The part prints with layers crossing the wall leg, the weaker direction.
- **Printer block and clearances are placeholders** until calibrated.
- **No slicer check,** so "printable" means these geometric rules pass, not that a
  slicer or printer agreed.
- **Eval briefs have no designs yet** except the bracket. `evals/run_evals.py` runs them; see
  `evals/EVALS.md`.
- **`phone_stand` eval expects a `slot_gauge` test part,** because no probe can yet
  measure an internal gap.

## What Phase 1 does NOT do

Slicer integration, vision reviewer agent, electronics / mechanisms / SDF modules, FEA,
web UI, photo input. Those are phases 2-5.

## Roadmap

1. **Core loop** (this): CAD template, renders, checks, eval set. Gate: eval set passes.
2. **Magic layer:** brief, library, candidates, viewer, sliders. Gate: first prints work.
3. **Electronics:** KiCad import, photo to mm, click to edit. Gate: a real board case.
4. **Machines:** assemblies, motion checks, load analysis. Gate: a working gearbox.
5. **Toys, organic:** SDF engine, mesh starts, toy safety. Print feedback and dreaming run from phase 2 on.

Note: Phase 1's own doc gate is "eval set passes". This build meets the brief's narrower
gate on one part; four eval briefs still need designs.
