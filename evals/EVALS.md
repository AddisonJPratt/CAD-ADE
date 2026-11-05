# Evals

A fixed set of briefs, rerun on every harness change so a new skill or prompt can be judged
by numbers. It starts with 5 and should grow to 30-50 across the four domains: functional
parts, electronics, machines and mechanisms, toys and organic shapes.

| Brief | Paragraph summary | Parts | Status |
|---|---|---|---|
| `briefs/phone_stand.yaml` | Phone stand, 15° tilt, 9 mm case, cable slot | 2 (with gauge) | `designs/phone_stand.py`: PASS (batch ten, unreviewed) |
| `briefs/wall_bracket.yaml` | The demo; symlink to `../../briefs/wall_bracket.yaml` | 1 | `designs/wall_bracket.py` |
| `briefs/cable_clip.yaml` | Screw-down snap clip for one round cable | 1 | `designs/cable_clip.py`: PASS (batch ten, unreviewed) |
| `briefs/box_with_lid.yaml` | Box and separate lid with a sliding fit | 2 | `designs/box_with_lid.py`: PASS (batch ten, unreviewed) |
| `briefs/planter_pot.yaml` | Stepped-taper pot, drain hole, drain grooves under a flat foot | 1 | `designs/planter_pot.py`: PASS (issue #3, reviewed 14/20) |
| `briefs/project_enclosure.yaml` | Electronics enclosure, 4 M3 heat-set bosses, flush screw-down lid | 2 | `designs/project_enclosure.py`: PASS (batch ten, unreviewed) |
| `briefs/gear_pair.yaml` | Two meshing spur gears, module and tooth counts as params | 2 | `designs/gear_pair.py`: PASS (batch ten, unreviewed) |
| `briefs/pipe_clamp.yaml` | Wall clamp for 32 mm pipe, compliant strap, cross bolt | 1 | `designs/pipe_clamp.py`: PASS (batch ten, unreviewed) |
| `briefs/drawer_tray.yaml` | Three-compartment desk drawer tray, parametric outer size | 1 | `designs/drawer_tray.py`: PASS (batch ten, unreviewed) |
| `briefs/doorstop.yaml` | Wedge doorstop with underside grip ribs, printed on its side | 1 | `designs/doorstop.py`: PASS (batch ten, unreviewed) |
| `briefs/cable_spool.yaml` | Wall-mounted cable winder, retaining tabs, centre screw | 1 | `designs/cable_spool.py`: PASS (batch ten, unreviewed) |

Each brief's `function` field is its one-paragraph statement. `tests/run_tests.py` checks the
schema of all of them.

## Runner

```bash
.venv/bin/python evals/run_evals.py [--quick] [--out DIR] [--timeout S]   # or: magic.py evals
```

For each brief it runs `magic.py run` on `designs/<stem>.py` and writes `eval_report.json` and
`eval_report.md` to `evals/results/<timestamp>/`. A brief with no design is `NO_DESIGN`: a
coverage gap, not a failure. Pass rate (over designs present) and coverage (designs present /
total briefs) are always separate numbers. Exit 1 if any present design fails or gives no
trustworthy result (`ERROR`), otherwise 0.

`--quick` runs `magic.py check --no-sweep`. It leaves the Parametric column unmeasured and a
quick PASS verifies nothing, so don't record quick numbers below.

## Metrics

Phase 1 tracks the first four columns plus time. The vision doc's Functional, tokens/iterations,
and Physical measures need later phases.

| Metric | How it's measured |
|---|---|
| Runs | Script executes without error |
| Dimensional | Hard dimensions within ±0.1 mm of the brief |
| Printable | Passes printability checks (slicer check comes later), without supports where the brief says so |
| Parametric | Share of sampled parameter combinations that still pass |
| Time | Wall-clock per part |

## Results

| Brief | Runs | Dimensional | Printable | Parametric | Time |
|---|---|---|---|---|---|
| wall_bracket | Yes | 7/7 | Yes, no supports | 31/31 (100 %) | 2 min 16 s, sweep included |
| phone_stand | No design | - | - | - | - |
| cable_clip | No design | - | - | - | - |
| box_with_lid | No design | - | - | - | - |
| planter_pot | No design | - | - | - | - |

**Pass rate (over designs present): 1/1. Coverage (designs present / total briefs): 1/5.** The
pass rate rests on one part, and four briefs are untested. Run `20261103-201913`, full mode, with
`evals/run_evals.py`. "Printable" is the geometric gate; no slicer has checked these parts.
