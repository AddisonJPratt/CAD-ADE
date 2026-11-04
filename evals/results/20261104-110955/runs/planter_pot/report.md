# Magic CAD report: planter_pot.py

**Overall: FAIL**  
Command: `magic.py run /home/hatch/workspace/magic-cad/designs/planter_pot.py --brief /home/hatch/workspace/magic-cad/evals/briefs/planter_pot.yaml --out /home/hatch/workspace/magic-cad/evals/results/20261104-110955/runs/planter_pot`  
Brief: `/home/hatch/workspace/magic-cad/evals/briefs/planter_pot.yaml`  
Parameters: `{"rim_dia": 100.0, "height": 90.0, "taper_deg": 8.0, "wall": 2.4}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 3.94 s; no hard-coded literals |
| 2 Geometry | PASS | 1/1 solids, volume 77314 mm³, 3/3 dims in ±0.1 |
| 3 Printability | FAIL | pot: overhang_brief_pct 83.6 > 15.0 |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | SKIPPED | - |
| 5 Exports | SKIPPED | - |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| rim_dia | 100.000 | 100.000 | 0.000 | PASS |
| height | 90.000 | 90.000 | 0.000 | PASS |
| drain_holes | 1.000 | 1.000 | 0.000 | PASS |

## Printability: pot (reloaded STL)

- Watertight: True; components: 1; faces: 12450
- Extents: 100.00 x 99.97 x 90.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 83.63 %
- Support-risk metric (within 45° of straight down, off the bed): 13.00 %
- Flat undersides above bed: 3606.47 mm²; bed contact: 937 mm²
- Thinnest section (approximate, section sampling): ~2.4 mm (step 0.4; short tabs read high) at {'axis': 'X', 'offset': -31.25}

## Assumptions surfaced

- Size is a guess for a 10 cm herb pot.
- PLA softens in direct summer sun; use PETG outdoors. Unverified here.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
