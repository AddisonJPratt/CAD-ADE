# Eval report: 2026-11-03T20:53:38-06:00

## Summary

- **Pass rate (over designs present): 1/1 (100%)**
- **Coverage (designs present / total briefs): 1/5 (20%)**
- **NO_DESIGN: 4 of 5 briefs have no design (box_with_lid, cable_clip, phone_stand, planter_pot). Coverage gap, not a design failure.**
- **QUICK MODE: sweep not run. Parametric behaviour is unverified; a PASS here does not verify a design.**

## Per brief

| Brief | Status | Runs | Dimensional | Printable | Parametric | Time |
|---|---|---|---|---|---|---|
| box_with_lid | **NO_DESIGN** | - | - | - | - | - |
| cable_clip | **NO_DESIGN** | - | - | - | - | - |
| phone_stand | **NO_DESIGN** | - | - | - | - | - |
| planter_pot | **NO_DESIGN** | - | - | - | - | - |
| wall_bracket | PASS | Yes | 7/7 | Yes | not run (quick) | 30 s |

## Gates

| Brief | Gate | Status | Detail |
|---|---|---|---|
| wall_bracket | 1 Execute | PASS | built in 10.9 s; no hard-coded literals |
| wall_bracket | 2 Geometry | PASS | 1/1 solids, volume 78220 mm³, 7/7 dims in ±0.1 |
| wall_bracket | 3 Printability | PASS | watertight, single component, fits bed; overhang brief 4.6 %, support risk 0.9 % |
| wall_bracket | 4 Renders | PASS | 5 PNGs from reloaded STL |
| wall_bracket | Sweep | NOT RUN | --no-sweep: parametric behaviour not verified |
| wall_bracket | 5 Exports | NOT RUN | check mode: no exports kept |
