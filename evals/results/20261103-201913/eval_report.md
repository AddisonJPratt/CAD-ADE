# Eval report: 2026-11-03T20:21:30-06:00

## Summary

- **Pass rate (over designs present): 1/1 (100%)**
- **Coverage (designs present / total briefs): 1/5 (20%)**
- **NO_DESIGN: 4 of 5 briefs have no design (box_with_lid, cable_clip, phone_stand, planter_pot). Coverage gap, not a design failure.**

## Per brief

| Brief | Status | Runs | Dimensional | Printable | Parametric | Time |
|---|---|---|---|---|---|---|
| box_with_lid | **NO_DESIGN** | - | - | - | - | - |
| cable_clip | **NO_DESIGN** | - | - | - | - | - |
| phone_stand | **NO_DESIGN** | - | - | - | - | - |
| planter_pot | **NO_DESIGN** | - | - | - | - | - |
| wall_bracket | PASS | Yes | 7/7 | Yes | 31/31 (100%) | 2 min 16 s |

## Gates

| Brief | Gate | Status | Detail |
|---|---|---|---|
| wall_bracket | 1 Execute | PASS | built in 7.62 s; no hard-coded literals |
| wall_bracket | 2 Geometry | PASS | 1/1 solids, volume 78220 mm³, 7/7 dims in ±0.1 |
| wall_bracket | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 4.6 %, support risk 0.9 % |
| wall_bracket | 4 Renders | PASS | 5 PNGs from reloaded STL |
| wall_bracket | Sweep | PASS | 31/31 pass; dead params: none |
| wall_bracket | 5 Exports | PASS | bracket.stl, bracket.step |
