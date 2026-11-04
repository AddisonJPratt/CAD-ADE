# Magic CAD report: phone_stand.py

**Overall: PASS**  
Command: `magic.py run /home/hatch/workspace/magic-cad/designs/phone_stand.py --brief /home/hatch/workspace/magic-cad/evals/briefs/phone_stand.yaml --out /home/hatch/workspace/magic-cad/evals/results/20261104-100341/runs/phone_stand`  
Brief: `/home/hatch/workspace/magic-cad/evals/briefs/phone_stand.yaml`  
Parameters: `{"width": 80.0, "depth": 90.0, "slot_gap": 9.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 3.8 s; no hard-coded literals |
| 2 Geometry | PASS | 2/2 solids, volume 164961 mm³, 3/3 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 5.3 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 13/13 pass; dead params: none |
| 5 Exports | PASS | stand.stl, stand.step, slot_gauge.stl, slot_gauge.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| width | 80.000 | 80.000 | 0.000 | PASS |
| depth | 90.000 | 90.000 | 0.000 | PASS |
| slot_gap | 9.000 | 9.000 | 0.000 | PASS |

## Printability: stand (reloaded STL)

- Watertight: True; components: 1; faces: 560
- Extents: 90.00 x 80.00 x 99.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 5.27 %
- Flat undersides above bed: 343.39 mm²; bed contact: 6172 mm²
- Thinnest section (approximate, section sampling): ~4.4 mm (step 0.4; short tabs read high) at {'axis': 'X', 'offset': 50.63}

## Printability: slot_gauge (reloaded STL)

- Watertight: True; components: 1; faces: 12
- Extents: 43.98 x 6.00 x 9.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 264 mm²
- Thinnest section (approximate, section sampling): ~6.0 mm (step 0.4; short tabs read high) at {'axis': 'X', 'offset': 45.77}
- Overlap stand / slot_gauge: 0.000 mm³

## Parameter sweep

**13/13 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 13/13 pass; worst support risk 7.3 %, worst brief overhang 0.0 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 164961 | True | - |
| width=min | PASS | 122678 | True | - |
| width=max | PASS | 228385 | True | - |
| depth=min | PASS | 114913 | True | - |
| depth=max | PASS | 256109 | True | - |
| slot_gap=min | PASS | 146284 | True | - |
| slot_gap=max | PASS | 236213 | True | - |
| all=min | PASS | 74158 | True | - |
| all=max | PASS | 479401 | True | - |
| combo1 | PASS | 320640 | True | - |
| combo2 | PASS | 179264 | True | - |
| combo3 | PASS | 479401 | True | - |
| combo4 | PASS | 303244 | True | - |

## Assumptions surfaced

- Phone plus case is 9 mm thick, per the vision doc's example.
- Width and depth are guesses from a typical 6 inch phone.
- slot_gap is measured on a slot_gauge part: the eval expects a test gauge alongside the stand.
- UNMEASURED: no probe reads the stand's internal lip-to-rest gap. The gate reads only the gauge, whose height equals the param by construction, so a wrong gap in the stand itself would still pass. The physical test is whether the printed gauge fits the slot.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
