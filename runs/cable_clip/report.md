# Magic CAD report: cable_clip.py

**Overall: PASS**  
Command: `magic.py run designs/cable_clip.py --brief evals/briefs/cable_clip.yaml --out runs/cable_clip`  
Brief: `evals/briefs/cable_clip.yaml`  
Parameters: `{"clip_width": 12.0, "cable_dia": 6.0, "arm_thickness": 1.6}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 3.78 s; no hard-coded literals |
| 2 Geometry | PASS | 1/1 solids, volume 1173 mm³, 2/2 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 13/13 pass; dead params: none |
| 5 Exports | PASS | clip.stl, clip.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| clip_width | 12.000 | 12.000 | 0.000 | PASS |
| mount_holes | 1.000 | 1.000 | 0.000 | PASS |

## Printability: clip (reloaded STL)

- Watertight: True; components: 1; faces: 2764
- Extents: 17.21 x 9.70 x 12.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 104 mm²
- Thinnest section (approximate, section sampling): ~1.6 mm (step 0.4; short tabs read high) at {'axis': 'X', 'offset': -8.37}

## Parameter sweep

**13/13 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 13/13 pass; worst support risk 0.0 %, worst brief overhang 0.0 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 1173 | True | - |
| clip_width=min | PASS | 756 | True | - |
| clip_width=max | PASS | 2006 | True | - |
| cable_dia=min | PASS | 1045 | True | - |
| cable_dia=max | PASS | 2018 | True | - |
| arm_thickness=min | PASS | 914 | True | - |
| arm_thickness=max | PASS | 1755 | True | - |
| all=min | PASS | 520 | True | - |
| all=max | PASS | 4690 | True | - |
| combo1 | PASS | 2830 | True | - |
| combo2 | PASS | 1241 | True | - |
| combo3 | PASS | 4690 | True | - |
| combo4 | PASS | 2585 | True | - |

## Assumptions surfaced

- Cable diameter 6 mm is a guess; it is an editable param.
- PLA arms survive repeated flex only at low strain; arm thickness needs a check.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
