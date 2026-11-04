# Magic CAD report: project_enclosure.py

**Overall: PASS**  
Command: `magic.py run designs/project_enclosure.py --brief evals/briefs/project_enclosure.yaml --out runs/project_enclosure`  
Brief: `evals/briefs/project_enclosure.yaml`  
Parameters: `{"outer_x": 100.0, "outer_y": 60.0, "outer_z": 35.0, "lid_thickness": 5.0, "wall": 2.4, "floor": 2.0, "port_w": 12.0, "port_h": 6.0, "vent_count": 5, "vent_w": 2.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 4.35 s; no hard-coded literals |
| 2 Geometry | PASS | 2/2 solids, volume 64613 mm³, 6/6 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.5 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 27/27 pass; dead params: none |
| 5 Exports | PASS | base.stl, base.step, lid.stl, lid.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| outer_x | 100.000 | 100.000 | 0.000 | PASS |
| outer_y | 60.000 | 60.000 | 0.000 | PASS |
| outer_z | 35.000 | 35.000 | 0.000 | PASS |
| lid_thickness | 5.000 | 5.000 | 0.000 | PASS |
| insert_holes | 4.000 | 4.000 | 0.000 | PASS |
| lid_holes | 4.000 | 4.000 | 0.000 | PASS |

## Printability: base (reloaded STL)

- Watertight: True; components: 1; faces: 4272
- Extents: 100.00 x 60.00 x 35.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.48 %
- Flat undersides above bed: 28.80 mm²; bed contact: 5980 mm²
- Thinnest section (approximate, section sampling): ~1.2 mm (step 0.4; short tabs read high) at {'axis': 'X', 'offset': -43.75}

## Printability: lid (reloaded STL)

- Watertight: True; components: 1; faces: 4672
- Extents: 97.10 x 57.10 x 5.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 5198 mm²
- Thinnest section (approximate, section sampling): ~1.2 mm (step 0.4; short tabs read high) at {'axis': 'Y', 'offset': 39.82}
- Overlap base / lid: 0.000 mm³

## Parameter sweep

**27/27 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 27/27 pass; worst support risk 0.7 %, worst brief overhang 0.0 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 64613 | True | - |
| outer_x=min | PASS | 53575 | True | - |
| outer_x=max | PASS | 86689 | True | - |
| outer_y=min | PASS | 56544 | True | - |
| outer_y=max | PASS | 88820 | True | - |
| outer_z=min | PASS | 55459 | True | - |
| outer_z=max | PASS | 78343 | True | - |
| lid_thickness=min | PASS | 61821 | True | - |
| lid_thickness=max | PASS | 69266 | True | - |
| wall=min | PASS | 58478 | True | - |
| wall=max | PASS | 70441 | True | - |
| floor=min | PASS | 62587 | True | - |
| floor=max | PASS | 70691 | True | - |
| port_w=min | PASS | 64656 | True | - |
| port_w=max | PASS | 64555 | True | - |
| port_h=min | PASS | 64670 | True | - |
| port_h=max | PASS | 64555 | True | - |
| vent_count=min | PASS | 65213 | True | - |
| vent_count=max | PASS | 63413 | True | - |
| vent_w=min | PASS | 64913 | True | - |
| vent_w=max | PASS | 63863 | True | - |
| all=min | PASS | 33602 | True | - |
| all=max | PASS | 170725 | True | - |
| combo1 | PASS | 134703 | True | - |
| combo2 | PASS | 84272 | True | - |
| combo3 | PASS | 98337 | True | - |
| combo4 | PASS | 89090 | True | - |

## Assumptions surfaced

- Size is the brief's approximate figure; every outer dimension is an editable param.
- Heat-set insert values come from standard_parts.json, which README flags as from memory; check against the vendor's sheet.
- No board is specified, so there are no PCB standoffs, and the connector opening's position is a guess.
- The hole probes confirm the holes exist at the right diameter. Hole alignment between lid and base is not probed; it is checked out-of-band on the reloaded STLs.
- Parts are laid out apart on the bed, so the harness checks overlap in the print layout.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
