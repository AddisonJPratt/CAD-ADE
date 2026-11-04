# Batch ten progress (BRIEF_TEN.md)

Status is the harness verdict from `magic.py run` on reloaded files. A PASS is a gate result, not a
design verdict: all designs here are **unreviewed** (no independent magic-cad-reviewer pass) and no
slicer or printer has seen them. Dims = hard dimensions in ±0.1 mm. Sweep = samples passing geometry.

| # | Design | Status | Dims | Sweep | Time | Note |
|---|---|---|---|---|---|---|
| 1 | box_with_lid | PASS | 4/4 | 17/17 | 77s | Lip fit checked out-of-band on reloaded STLs: seated overlap 0, 0.25 mm wall gap. Rim chamfer and thumb notch; bed edge left square (brief's outside-edge chamfer preference only partly met). |
| 2 | cable_clip | PASS | 2/2 | 13/13 | 53s | Brief conflict: the Z hole probe makes the M3 screw parallel to the cable, so it fixes to a surface the cable leaves at 90 deg, not along a wall as the function text reads. Built to the probe. Arm snap strain is a hand estimate (~2 %). |
| 3 | phone_stand | PASS | 3/3 | 13/13 | 52s | UNMEASURED by the harness: stand's lip-to-rest gap (gauge bar is self-graded; stated in brief assumptions). Out-of-band on reloaded STL at defaults: gap 9.000 mm, tilt 15.0 deg. Rest wedge is solid because a leaning slab's back would fail overhang; heavy. Cable slot 12 mm with 5.3 % bridge under rest. |
| 4 | planter_pot | FAIL | 3/3 | 15/15 (run separately; printable 0/15) | 17s | Gate 3: overhang_brief_pct 83.6 > 15. Every wider-at-rim wall has one down-facing side, and the literal metric counts it (a printable 8 deg lean). Attempt 2 rim-down: 82.5 % and support_risk 15.4 %, also FAIL. Attempt 3 no ring, flat base: analytic, 76-85 % across the taper range. Stepped wall moves it to support_risk. Not passable without changing the gate or the brief's allow_supports; both left alone. |
| 5 | project_enclosure | PASS | 6/6 | 27/27 | 105s | Full gates passed once with corner fillers poking through the rounded outer corners; only the render showed it, fixed. Lid default raised 4 to 5 mm after 0.8 mm under-head floor. Out-of-band: lid seated overlap 0, wall gap 0.25, hole axes match. No PCB standoffs; no board given. Insert data from memory per README. |
| 6 | gear_pair | PASS | 2/2 | 25/25 | 193s | Tooth form, module and centre distance are NOT gated (stated in brief). Out-of-band over one tooth pitch on reloaded STLs: overlap 0 and worst gap = flank clearance (default 0.351, 18/60 and 18/18 at m1 0.250). Radial flanks below base circle and no root fillets; root is narrow for PLA. Library candidate: involute gear profile. |
| 7 | pipe_clamp | PASS | 4/4 | 19/19 (printable 18/19; all=min reads 15.5 % overhang, not gated in sweep) | 79s | 3 attempts: overhang 21.6, 15.2, then 12.8 %. Passing cost the counterbores and the teardrop on the cross bolt, because the literal metric penalises horizontal holes against a small bed contact; heads stand proud. Pipe bore not gated; out-of-band 32.5 mm on reloaded STEP. Strain ~1.2 % hand estimate. Library candidate: plain teardrop hole. |
| 8 | drawer_tray | PASS | 3/3 | 27/27 | 120s | First run failed the sweep with split_y reported dead: 0.35 and 0.65 are mirror images, which the fingerprint can't tell apart (volume, bbox, diagonal moments). Param was alive; range changed to 0.3-0.65 in my own new brief. Harness false positive worth a look. Internal walls not probed. Warp risk unverified. |
| 9 | doorstop | PASS | 3/3 | 21/21 | 63s | Printed on its side, so ribs are prisms and overhang is 0 %. First version had the teeth backwards with all gates passing; caught by reading the render. Rib form and direction are not probed. Holding force on smooth floors untested. |
| 10 | cable_spool | PASS | 3/3 | 25/25 (printable 22/25; 3 samples read 15.2-15.7 % overhang, not gated in sweep) | 98s | Lip is tabs, not a full ring, because a ring fails the overhang gate; stated in brief. Sweep first caught tabs outgrowing a small flange: reach now capped, flange min raised 70 to 80 in my own brief. One screw, no anti-rotation. |

## Library candidates
- Involute spur gear profile (`designs/gear_pair.py`), with root fillets added.
- Plain teardrop hole with no counterbore (`designs/pipe_clamp.py`); `counterbored_hole` can't do this.
- Rounded-corner plan prism, repeated in box_with_lid, project_enclosure and drawer_tray.

## Shared changes
- `library/standard_parts.json`: added `fits` (mirrors the CLAUDE.md clearance table) and `brief_constants`
  (values existing briefs pin but do not declare as params). No gate or test changed.
- `evals/briefs/phone_stand.yaml`: added one assumption stating the unmeasured gap, as BRIEF_TEN asks. Params and hard dimensions unchanged.
- Helper scripts for full runs and out-of-band fit checks are in `runs/_batch_tools/`. Not part of the harness.

## Harness observations (no gate changed)
- `overhang_brief_pct` counts any downward face over 45 deg from straight down, so a printable flared wall counts in full. It is what fails planter_pot, and it forced compromises on pipe_clamp. README already flags this metric. Deciding whether to keep it is your call.
- Mirror-image param extremes read as a dead param, since the fingerprint uses volume, bbox and diagonal moments (drawer_tray split_y).
- Gates passed with real defects that only render or fit checks showed: enclosure corner fins, doorstop teeth backwards.
- `magic.py run` looks only in `briefs/`, so the four existing eval designs must be run with `--brief evals/briefs/<stem>.yaml`; without it they run with no hard dimensions checked. `magic.py evals` passes the brief.
