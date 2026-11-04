# Magic CAD report: doorstop.py

**Overall: PASS**  
Command: `magic.py run /home/hatch/workspace/magic-cad/designs/doorstop.py --brief /home/hatch/workspace/magic-cad/evals/briefs/doorstop.yaml --out /home/hatch/workspace/magic-cad/evals/results/20261104-110955/runs/doorstop`  
Brief: `/home/hatch/workspace/magic-cad/evals/briefs/doorstop.yaml`  
Parameters: `{"length": 120.0, "wedge_height": 32.0, "width": 45.0, "tip_t": 2.4, "rib_depth": 1.6, "rib_pitch": 6.0, "cord_dia": 6.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 4.03 s; no hard-coded literals |
| 2 Geometry | PASS | 1/1 solids, volume 87936 mm³, 3/3 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 21/21 pass; dead params: none |
| 5 Exports | PASS | doorstop.stl, doorstop.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| length | 120.000 | 120.000 | 0.000 | PASS |
| wedge_height | 32.000 | 32.000 | 0.000 | PASS |
| width | 45.000 | 45.000 | 0.000 | PASS |

## Printability: doorstop (reloaded STL)

- Watertight: True; components: 1; faces: 660
- Extents: 120.00 x 32.00 x 45.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 1954 mm²
- Thinnest section (approximate, section sampling): ~2.9 mm (step 0.5; short tabs read high) at {'axis': 'Z', 'offset': 2.81}

## Parameter sweep

**21/21 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 21/21 pass; worst support risk 0.0 %, worst brief overhang 0.0 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 87936 | True | - |
| length=min | PASS | 65796 | True | - |
| length=max | PASS | 117600 | True | - |
| wedge_height=min | PASS | 69252 | True | - |
| wedge_height=max | PASS | 136536 | True | - |
| width=min | PASS | 58624 | True | - |
| width=max | PASS | 117248 | True | - |
| tip_t=min | PASS | 85776 | True | - |
| tip_t=max | PASS | 90096 | True | - |
| rib_depth=min | PASS | 89772 | True | - |
| rib_depth=max | PASS | 86424 | True | - |
| rib_pitch=min | PASS | 87864 | True | - |
| rib_pitch=max | PASS | 88368 | True | - |
| cord_dia=min | PASS | 88643 | True | - |
| cord_dia=max | PASS | 86946 | True | - |
| all=min | PASS | 34573 | True | - |
| all=max | PASS | 242624 | True | - |
| combo1 | PASS | 121312 | True | - |
| combo2 | PASS | 155748 | True | - |
| combo3 | PASS | 121424 | True | - |
| combo4 | PASS | 89578 | True | - |

## Assumptions surfaced

- PRINT ORIENTATION: on its side, with one side face on the bed. Printed flat on the ribs, every rib valley would be a downward face and the slope would need a long bed contact; this avoids both.
- Rib form is not a hard dimension; no probe reads a tooth. Rib depth and pitch are params and checked by render only.
- Rigid PLA ribs grip poorly on tile or polished wood; this is an estimate, not a tested holding force. TPU would grip better but is not this project's material.
- Height and length are guesses for a typical interior door gap. wedge_height sets the door gap it can stop.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
