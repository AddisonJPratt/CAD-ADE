# Magic CAD report: drawer_tray.py

**Overall: PASS**  
Command: `magic.py run designs/drawer_tray.py --brief evals/briefs/drawer_tray.yaml --out runs/drawer_tray`  
Brief: `evals/briefs/drawer_tray.yaml`  
Parameters: `{"outer_x": 240.0, "outer_y": 120.0, "height": 45.0, "wall": 1.8, "floor": 1.6, "divider_t": 1.6, "divider_ratio": 0.75, "split_x": 0.6, "split_y": 0.5, "scoop_r": 6.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 4.61 s; no hard-coded literals |
| 2 Geometry | PASS | 1/1 solids, volume 122467 mm³, 3/3 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 27/27 pass; dead params: none |
| 5 Exports | PASS | tray.stl, tray.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| outer_x | 240.000 | 240.000 | 0.000 | PASS |
| outer_y | 120.000 | 120.000 | 0.000 | PASS |
| height | 45.000 | 45.000 | 0.000 | PASS |

## Printability: tray (reloaded STL)

- Watertight: True; components: 1; faces: 21012
- Extents: 240.00 x 120.00 x 45.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 28726 mm²
- Thinnest section (approximate, section sampling): ~1.9 mm (step 1.0; short tabs read high) at {'axis': 'X', 'offset': -105.0}

## Parameter sweep

**27/27 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 27/27 pass; worst support risk 0.0 %, worst brief overhang 0.0 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 122467 | True | - |
| outer_x=min | PASS | 75582 | True | - |
| outer_x=max | PASS | 124420 | True | - |
| outer_y=min | PASS | 97538 | True | - |
| outer_y=max | PASS | 172324 | True | - |
| height=min | PASS | 91042 | True | - |
| height=max | PASS | 161570 | True | - |
| wall=min | PASS | 104598 | True | - |
| wall=max | PASS | 157745 | True | - |
| floor=min | PASS | 111604 | True | - |
| floor=max | PASS | 144193 | True | - |
| divider_t=min | PASS | 119828 | True | - |
| divider_t=max | PASS | 131662 | True | - |
| divider_ratio=min | PASS | 117770 | True | - |
| divider_ratio=max | PASS | 127163 | True | - |
| split_x=min | PASS | 125660 | True | - |
| split_x=max | PASS | 120072 | True | - |
| split_y=min | PASS | 122466 | True | - |
| split_y=max | PASS | 122467 | True | - |
| scoop_r=min | PASS | 116653 | True | - |
| scoop_r=max | PASS | 130554 | True | - |
| all=min | PASS | 27235 | True | - |
| all=max | PASS | 370211 | True | - |
| combo1 | PASS | 198680 | True | - |
| combo2 | PASS | 141939 | True | - |
| combo3 | PASS | 186379 | True | - |
| combo4 | PASS | 140012 | True | - |

## Assumptions surfaced

- Outer size is a guess for a typical desk drawer; 245 mm is the bed-limited maximum on the 250 mm placeholder bed.
- Compartment sizes and divider height are not hard dimensions: no probe reads an internal wall. They are checked by eye in the section render only.
- A 240 mm long, thin-walled, flat part in PLA can warp at the corners on a real bed; unverified, no slicer or printer has seen it.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
