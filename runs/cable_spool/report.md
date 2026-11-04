# Magic CAD report: cable_spool.py

**Overall: PASS**  
Command: `magic.py run designs/cable_spool.py --brief evals/briefs/cable_spool.yaml --out runs/cable_spool`  
Brief: `evals/briefs/cable_spool.yaml`  
Parameters: `{"flange_dia": 90.0, "hub_dia": 50.0, "spool_height": 40.0, "flange_t": 6.0, "wall": 3.0, "lip_reach": 7.0, "lip_arc": 50.0, "lip_count": 3, "notch_w": 4.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 4.05 s; no hard-coded literals |
| 2 Geometry | PASS | 1/1 solids, volume 55577 mm³, 3/3 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 10.6 %, support risk 0.0 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 25/25 pass; dead params: none |
| 5 Exports | PASS | spool.stl, spool.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| flange_dia | 90.000 | 90.000 | 0.000 | PASS |
| spool_height | 40.000 | 40.000 | 0.000 | PASS |
| mount_holes | 1.000 | 1.000 | 0.000 | PASS |

## Printability: spool (reloaded STL)

- Watertight: True; components: 1; faces: 19430
- Extents: 89.99 x 89.99 x 40.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 10.64 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 6311 mm²
- Thinnest section (approximate, section sampling): ~2.0 mm (step 0.4; short tabs read high) at {'axis': 'Y', 'offset': -28.12}

## Parameter sweep

**25/25 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 22/25 pass; worst support risk 0.7 %, worst brief overhang 15.7 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 55577 | True | - |
| flange_dia=min | PASS | 47581 | True | - |
| flange_dia=max | PASS | 96985 | True | - |
| hub_dia=min | PASS | 50348 | True | - |
| hub_dia=max | PASS | 59311 | True | - |
| spool_height=min | PASS | 50261 | True | - |
| spool_height=max | PASS | 64436 | True | - |
| flange_t=min | PASS | 50913 | True | - |
| flange_t=max | PASS | 67215 | True | - |
| wall=min | PASS | 50335 | True | - |
| wall=max | PASS | 60678 | True | - |
| lip_reach=min | PASS | 53973 | True | - |
| lip_reach=max | PASS | 57996 | False | - |
| lip_arc=min | PASS | 54537 | True | - |
| lip_arc=max | PASS | 56616 | True | - |
| lip_count=min | PASS | 54710 | True | - |
| lip_count=max | PASS | 56443 | True | - |
| notch_w=min | PASS | 55660 | True | - |
| notch_w=max | PASS | 55338 | True | - |
| all=min | PASS | 30950 | True | - |
| all=max | PASS | 154111 | False | - |
| combo1 | PASS | 131592 | False | - |
| combo2 | PASS | 82529 | True | - |
| combo3 | PASS | 43700 | True | - |
| combo4 | PASS | 62635 | True | - |

## Assumptions surfaced

- RETAINING LIP IS TABS, NOT A FULL RING. Each tab's underside is a 44 deg self-supporting cone, but it still counts as downward-facing, and a full ring reads well over the 15 % overhang limit. Gaps between tabs also let a hand reach the coil.
- A single centre screw lets the spool turn on the wall if over-torqued by a pull. No anti-rotation key; the brief asks for a centre screw only.
- Coil capacity is not a hard dimension and is not measured. Tab reach and spacing, retention, and cable pull load are unverified on a real print.
- Wall anchors are the installer's choice.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
