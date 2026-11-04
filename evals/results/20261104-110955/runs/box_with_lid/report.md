# Magic CAD report: box_with_lid.py

**Overall: PASS**  
Command: `magic.py run /home/hatch/workspace/magic-cad/designs/box_with_lid.py --brief /home/hatch/workspace/magic-cad/evals/briefs/box_with_lid.yaml --out /home/hatch/workspace/magic-cad/evals/results/20261104-110955/runs/box_with_lid`  
Brief: `/home/hatch/workspace/magic-cad/evals/briefs/box_with_lid.yaml`  
Parameters: `{"outer_x": 80.0, "outer_y": 60.0, "box_height": 30.0, "lid_height": 8.0, "wall": 2.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 12.14 s; no hard-coded literals |
| 2 Geometry | PASS | 2/2 solids, volume 36799 mm³, 4/4 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 17/17 pass; dead params: none |
| 5 Exports | PASS | box.stl, box.step, lid.stl, lid.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| outer_x | 80.000 | 80.000 | 0.000 | PASS |
| outer_y | 60.000 | 60.000 | 0.000 | PASS |
| box_height | 30.000 | 30.000 | 0.000 | PASS |
| lid_height | 8.000 | 8.000 | 0.000 | PASS |

## Printability: box (reloaded STL)

- Watertight: True; components: 1; faces: 1576
- Extents: 80.00 x 60.00 x 30.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 4786 mm²
- Thinnest section (approximate, section sampling): ~2.0 mm (step 0.4; short tabs read high) at {'axis': 'X', 'offset': -35.0}

## Printability: lid (reloaded STL)

- Watertight: True; components: 1; faces: 1580
- Extents: 80.00 x 60.00 x 8.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 4786 mm²
- Thinnest section (approximate, section sampling): ~2.0 mm (step 0.4; short tabs read high) at {'axis': 'X', 'offset': -35.0}
- Overlap box / lid: 0.000 mm³

## Parameter sweep

**17/17 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 17/17 pass; worst support risk 0.0 %, worst brief overhang 0.0 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 36799 | True | - |
| outer_x=min | PASS | 25549 | True | - |
| outer_x=max | PASS | 63049 | True | - |
| outer_y=min | PASS | 27699 | True | - |
| outer_y=max | PASS | 64099 | True | - |
| box_height=min | PASS | 28794 | True | - |
| box_height=max | PASS | 63484 | True | - |
| lid_height=min | PASS | 35380 | True | - |
| lid_height=max | PASS | 39970 | True | - |
| wall=min | PASS | 22912 | True | - |
| wall=max | PASS | 55644 | True | - |
| all=min | PASS | 8307 | True | - |
| all=max | PASS | 259627 | True | - |
| combo1 | PASS | 151683 | True | - |
| combo2 | PASS | 77919 | True | - |
| combo3 | PASS | 21731 | True | - |
| combo4 | PASS | 112323 | True | - |

## Assumptions surfaced

- Size is a guess; every outer dimension is an editable param.
- Parts are laid out apart on the bed, so overlap is checked in the print layout.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
