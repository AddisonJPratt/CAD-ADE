# Eval report: 2026-11-04T11:25:32-06:00

## Summary

- **Pass rate (over designs present): 10/11 (91%)**
- **Coverage (designs present / total briefs): 11/11 (100%)**

## Per brief

| Brief | Status | Runs | Dimensional | Printable | Parametric | Time |
|---|---|---|---|---|---|---|
| box_with_lid | PASS | Yes | 4/4 | Yes | 17/17 (100%) | 1 min 24 s |
| cable_clip | PASS | Yes | 2/2 | Yes | 13/13 (100%) | 51 s |
| cable_spool | PASS | Yes | 3/3 | Yes | 25/25 (100%) | 1 min 46 s |
| doorstop | PASS | Yes | 3/3 | Yes | 21/21 (100%) | 1 min 17 s |
| drawer_tray | PASS | Yes | 3/3 | Yes | 27/27 (100%) | 1 min 44 s |
| gear_pair | PASS | Yes | 2/2 | Yes | 25/25 (100%) | 2 min 58 s |
| phone_stand | PASS | Yes | 3/3 | Yes | 13/13 (100%) | 48 s |
| pipe_clamp | PASS | Yes | 4/4 | Yes | 19/19 (100%) | 1 min 6 s |
| planter_pot | **FAIL** | Yes | 3/3 | No | - | 15 s |
| project_enclosure | PASS | Yes | 6/6 | Yes | 27/27 (100%) | 1 min 44 s |
| wall_bracket | PASS | Yes | 7/7 | Yes | 31/31 (100%) | 1 min 46 s |

## Not passing

- planter_pot: FAIL: failed gates: 3 Printability

## Gates

| Brief | Gate | Status | Detail |
|---|---|---|---|
| box_with_lid | 1 Execute | PASS | built in 12.14 s; no hard-coded literals |
| box_with_lid | 2 Geometry | PASS | 2/2 solids, volume 36799 mm³, 4/4 dims in ±0.1 |
| box_with_lid | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| box_with_lid | 4 Renders | PASS | 5 PNGs from reloaded STL |
| box_with_lid | Sweep | PASS | 17/17 pass; dead params: none |
| box_with_lid | 5 Exports | PASS | box.stl, box.step, lid.stl, lid.step |
| cable_clip | 1 Execute | PASS | built in 3.73 s; no hard-coded literals |
| cable_clip | 2 Geometry | PASS | 1/1 solids, volume 1173 mm³, 2/2 dims in ±0.1 |
| cable_clip | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| cable_clip | 4 Renders | PASS | 5 PNGs from reloaded STL |
| cable_clip | Sweep | PASS | 13/13 pass; dead params: none |
| cable_clip | 5 Exports | PASS | clip.stl, clip.step |
| cable_spool | 1 Execute | PASS | built in 4.19 s; no hard-coded literals |
| cable_spool | 2 Geometry | PASS | 1/1 solids, volume 55577 mm³, 3/3 dims in ±0.1 |
| cable_spool | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 10.6 %, support risk 0.0 % |
| cable_spool | 4 Renders | PASS | 5 PNGs from reloaded STL |
| cable_spool | Sweep | PASS | 25/25 pass; dead params: none |
| cable_spool | 5 Exports | PASS | spool.stl, spool.step |
| doorstop | 1 Execute | PASS | built in 4.03 s; no hard-coded literals |
| doorstop | 2 Geometry | PASS | 1/1 solids, volume 87936 mm³, 3/3 dims in ±0.1 |
| doorstop | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| doorstop | 4 Renders | PASS | 5 PNGs from reloaded STL |
| doorstop | Sweep | PASS | 21/21 pass; dead params: none |
| doorstop | 5 Exports | PASS | doorstop.stl, doorstop.step |
| drawer_tray | 1 Execute | PASS | built in 4.22 s; no hard-coded literals |
| drawer_tray | 2 Geometry | PASS | 1/1 solids, volume 122467 mm³, 3/3 dims in ±0.1 |
| drawer_tray | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| drawer_tray | 4 Renders | PASS | 5 PNGs from reloaded STL |
| drawer_tray | Sweep | PASS | 27/27 pass; dead params: none |
| drawer_tray | 5 Exports | PASS | tray.stl, tray.step |
| gear_pair | 1 Execute | PASS | built in 7.82 s; no hard-coded literals |
| gear_pair | 2 Geometry | PASS | 2/2 solids, volume 14382 mm³, 2/2 dims in ±0.1 |
| gear_pair | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| gear_pair | 4 Renders | PASS | 5 PNGs from reloaded STL |
| gear_pair | Sweep | PASS | 25/25 pass; dead params: none |
| gear_pair | 5 Exports | PASS | gear_a.stl, gear_a.step, gear_b.stl, gear_b.step |
| phone_stand | 1 Execute | PASS | built in 3.83 s; no hard-coded literals |
| phone_stand | 2 Geometry | PASS | 2/2 solids, volume 164961 mm³, 3/3 dims in ±0.1 |
| phone_stand | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 5.3 % |
| phone_stand | 4 Renders | PASS | 5 PNGs from reloaded STL |
| phone_stand | Sweep | PASS | 13/13 pass; dead params: none |
| phone_stand | 5 Exports | PASS | stand.stl, stand.step, slot_gauge.stl, slot_gauge.step |
| pipe_clamp | 1 Execute | PASS | built in 4.03 s; no hard-coded literals |
| pipe_clamp | 2 Geometry | PASS | 1/1 solids, volume 15784 mm³, 4/4 dims in ±0.1 |
| pipe_clamp | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 12.8 %, support risk 2.0 % |
| pipe_clamp | 4 Renders | PASS | 5 PNGs from reloaded STL |
| pipe_clamp | Sweep | PASS | 19/19 pass; dead params: none |
| pipe_clamp | 5 Exports | PASS | clamp.stl, clamp.step |
| planter_pot | 1 Execute | PASS | built in 3.94 s; no hard-coded literals |
| planter_pot | 2 Geometry | PASS | 1/1 solids, volume 77314 mm³, 3/3 dims in ±0.1 |
| planter_pot | 3 Printability | FAIL | pot: overhang_brief_pct 83.6 > 15.0 |
| planter_pot | 4 Renders | PASS | 5 PNGs from reloaded STL |
| planter_pot | Sweep | SKIPPED | - |
| planter_pot | 5 Exports | SKIPPED | - |
| project_enclosure | 1 Execute | PASS | built in 4.53 s; no hard-coded literals |
| project_enclosure | 2 Geometry | PASS | 2/2 solids, volume 64613 mm³, 6/6 dims in ±0.1 |
| project_enclosure | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.5 % |
| project_enclosure | 4 Renders | PASS | 5 PNGs from reloaded STL |
| project_enclosure | Sweep | PASS | 27/27 pass; dead params: none |
| project_enclosure | 5 Exports | PASS | base.stl, base.step, lid.stl, lid.step |
| wall_bracket | 1 Execute | PASS | built in 4.05 s; no hard-coded literals |
| wall_bracket | 2 Geometry | PASS | 1/1 solids, volume 78220 mm³, 7/7 dims in ±0.1 |
| wall_bracket | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 4.6 %, support risk 0.9 % |
| wall_bracket | 4 Renders | PASS | 5 PNGs from reloaded STL |
| wall_bracket | Sweep | PASS | 31/31 pass; dead params: none |
| wall_bracket | 5 Exports | PASS | bracket.stl, bracket.step |
