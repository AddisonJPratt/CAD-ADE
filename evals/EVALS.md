# Evals

A fixed set of briefs, rerun on every harness change so a new skill or prompt can be judged
by numbers. It starts with 5 and should grow to 30-50 across the four domains: functional
parts, electronics, machines and mechanisms, toys and organic shapes.

| Brief | Paragraph summary | Parts | Status |
|---|---|---|---|
| `briefs/phone_stand.yaml` | Phone stand, 15° tilt, 9 mm case, cable slot | 2 (with gauge) | `designs/phone_stand.py`: PASS (batch ten, unreviewed) |
| `briefs/wall_bracket.yaml` | The demo; real copy of `briefs/wall_bracket.yaml`, kept identical by `tests/test_evals.py` | 1 | `designs/wall_bracket.py` |
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

## Designer evals (#61)

A brief card in, a design out, with no design file to start from. The real Claude Code designer
(`engine/claude_designer.py`) runs through the engine API's proposal seam, the same one Studio uses.
It loops on the gates (`engine/designer.py`, ADR 0004), then the proposal is accepted: the gates run
again on the saved version and the independent reviewer scores it (ADR 0003).

```bash
.venv/bin/python evals/run_designer.py --brief briefs/wall_bracket.yaml [--attempts 6] [--seconds 2700]
```

Each run writes `evals/results/designer-<timestamp>-<brief>/` with `events.jsonl` (every designer,
gate and review event), the design file, the renders of the accepted run, and `result.json`. It
spends model usage on the logged-in account. The repo's own design for the brief (and `runs/`,
`evals/results/`, `proof/`) is denied to the designer's Read tool, so it can't copy the answer.

| Brief | Attempts | Gate runs (quick / full) | Gates on the saved version | Review | Designer time | Usage | Run |
|---|---|---|---|---|---|---|---|
| wall_bracket (design file withheld) | 1 of 6 | 1 / 1 | PASS, sweep included, version 2 | 15/20, direction approved | 11 min 17 s (15 min with accept + review) | $4.17, 2.7 M tokens (mostly cache reads) | `designer-20261108-200049-wall_bracket` |
| wall_bracket, with Eyes (#79) | 1 of 6 | 1 / 1 | PASS, sweep included, version 2 | 16/20, direction approved, but see the function error below | 11 min 5 s (16 min with accept + review) | $4.29, 1.8 M tokens | `designer-20261108-203842-wall_bracket` |
| wall_bracket, shipped config: Eyes + quick gates (#80) + magic-cad on the draft, no shell | 1 of 6 | 1 / 1 | PASS, sweep included, version 2 | 19/20, adopt-ready, but see the function error below | 14 min 23 s (19 min with accept + review) | $4.94, 1.6 M tokens | `designer-20261108-220759-wall_bracket` |

The first two runs checked their drafts with `magic.py check` through a scoped Bash rule. The third
is the configuration this PR ships: magic-cad runs in the draft (`MAGIC_CAD_PROJECT`), and the
designer called `run_check` twice (quick, then full) and `library_lookup` once.

Notes on the wall_bracket run:
- The part is a real bracket, not a box with holes. It has an inner stress-relief fillet and a
  centreline gusset whose ramp is self-supporting. The wall screws use teardrop counterbores from
  the room side, so the horizontal holes print without supports. The shelf screws are counterbored
  from below. The section render confirms the floor under each screw head.
- Reviewer tells: the 1 mm fillet on the bed-contact outer corner drives the sweep's support risk,
  and two cosmetic radii and the rib proportions have no stated reason. Its top fix is
  `outer_radius` → 0.5. That fix was not sent back, because the review passed.
- In its attempt, the designer read both skills, looked up M4 in the library, read four repo designs
  for house style, and ran `magic.py check` on its draft (no-sweep, then with the sweep). It also
  read its own renders. A try at running its own build script was denied by the permission rules,
  as intended.
- Eyes (#79) had not landed when this ran, so this is the "without artefacts" row in the table below.
  The designer still read its renders, because the prompt tells it to look at its own check.
- **Function error in runs 2 and 3, both of which passed every gate and the review (16 and 19/20).**
  Their shelf counterbores open on the z=0 face, the face that meets the shelf, so the screw heads
  would sit between bracket and shelf. Run 3's own docstring says the head "sits below the plate",
  so the geometry contradicts its stated intent. Run 1 and the repo's reference design open them on
  the far face (z=thickness), where a screw driven up from below the bracket seats its head. No gate
  checks which face a counterbore opens on, the reviewer missed it three times out of three
  chances, and a prompt line asking the designer to check interface direction (added before run 3)
  didn't prevent it. The brief's "counterbored from below the shelf" can be misread. Found by
  reading the source after looking at the iso render. Follow-ups: a measurable interface probe
  (which face each counterbore opens on), a reviewer check of every interface line against the
  geometry, and a clearer interface line in the brief.
- Not yet run: the ESP32-DevKitC base-plate brief (catalogue board, M2.5 inserts), and a real
  negative control. The scripted test covers the negative control.

## Eyes: iterations with and without artefacts (#79)

Since #79, every check that reaches Gate 4 hands the agent its renders, an overhang heatmap,
sections at the thinnest wall and each named feature, the face map and per-part metrics
(`harness/eyes.py`, returned by magic-cad `run_check`). The comparison the ticket asks for,
wall_bracket-from-brief iterations with artefacts against without, needs the designer loop
that writes a design from a brief (#61); M0 makes one bounded parameter edit and has no
iterations to count. Record the two runs here when #61 lands:

| Brief | Artefacts | Iterations to a pass | Wall time | Run |
|---|---|---|---|---|
| wall_bracket-from-brief | without (renders only) | 1 attempt (1 quick + 1 full gate run) | 11 min 17 s designer, 15 min with accept + review | `designer-20261108-200049-wall_bracket` |
| wall_bracket-from-brief | with | 1 attempt (1 quick + 1 full gate run) | 11 min 5 s designer, 16 min with accept + review | `designer-20261108-203842-wall_bracket` |
| wall_bracket-from-brief | with, plus #80 and magic-cad on the draft | 1 attempt (1 quick + 1 full gate run) | 14 min 23 s designer, 19 min with accept + review | `designer-20261108-220759-wall_bracket` |

On this brief Eyes made no difference to the iteration count: both runs passed on the first attempt.
The designer read 3 of its own images with Eyes (`Reading its own render` events). The second run
also shows a pass that is wrong on function (see the designer notes above). A harder brief, such as
the ESP32 base plate, is needed to see whether the artefacts save attempts.
