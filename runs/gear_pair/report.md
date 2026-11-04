# Magic CAD report: gear_pair.py

**Overall: PASS**  
Command: `magic.py run designs/gear_pair.py --brief evals/briefs/gear_pair.yaml --out runs/gear_pair`  
Brief: `evals/briefs/gear_pair.yaml`  
Parameters: `{"module": 1.5, "teeth_a": 20, "teeth_b": 36, "pressure_angle": 20.0, "thickness": 8.0, "web": 3.0, "hub_wall": 3.0, "flank_clearance": 0.35, "flank_steps": 6}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 7.7 s; no hard-coded literals |
| 2 Geometry | PASS | 2/2 solids, volume 14382 mm³, 2/2 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 0.0 %, support risk 0.0 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 25/25 pass; dead params: none |
| 5 Exports | PASS | gear_a.stl, gear_a.step, gear_b.stl, gear_b.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| thickness | 8.000 | 8.000 | 0.000 | PASS |
| axle_holes | 2.000 | 2.000 | 0.000 | PASS |

## Printability: gear_a (reloaded STL)

- Watertight: True; components: 1; faces: 2792
- Extents: 32.99 x 32.99 x 8.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 648 mm²
- Thinnest section (approximate, section sampling): ~2.0 mm (step 0.4; short tabs read high) at {'axis': 'X', 'offset': -14.43}

## Printability: gear_b (reloaded STL)

- Watertight: True; components: 1; faces: 3816
- Extents: 56.84 x 56.84 x 8.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 0.00 %
- Support-risk metric (within 45° of straight down, off the bed): 0.00 %
- Flat undersides above bed: 0.00 mm²; bed contact: 2204 mm²
- Thinnest section (approximate, section sampling): ~1.6 mm (step 0.4; short tabs read high) at {'axis': 'Z', 'offset': 0.5}
- Overlap gear_a / gear_b: 0.000 mm³

## Parameter sweep

**25/25 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 25/25 pass; worst support risk 0.0 %, worst brief overhang 0.0 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 14382 | True | - |
| module=min | PASS | 6889 | True | - |
| module=max | PASS | 56823 | True | - |
| teeth_a=min | PASS | 13780 | True | - |
| teeth_a=max | PASS | 20758 | True | - |
| teeth_b=min | PASS | 7404 | True | - |
| teeth_b=max | PASS | 29042 | True | - |
| pressure_angle=min | PASS | 14382 | True | - |
| pressure_angle=max | PASS | 14469 | True | - |
| thickness=min | PASS | 10887 | True | - |
| thickness=max | PASS | 22539 | True | - |
| web=min | PASS | 12696 | True | - |
| web=max | PASS | 16069 | True | - |
| hub_wall=min | PASS | 14084 | True | - |
| hub_wall=max | PASS | 15953 | True | - |
| flank_clearance=min | PASS | 14544 | True | - |
| flank_clearance=max | PASS | 14140 | True | - |
| flank_steps=min | PASS | 14371 | True | - |
| flank_steps=max | PASS | 14388 | True | - |
| all=min | PASS | 2201 | True | - |
| all=max | PASS | 224378 | True | - |
| combo1 | PASS | 92260 | True | - |
| combo2 | PASS | 37573 | True | - |
| combo3 | PASS | 10468 | True | - |
| combo4 | PASS | 39526 | True | - |

## Assumptions surfaced

- TOOTH FORM IS NOT GATED. No probe reads an involute, pitch, or module. Flanks are faceted involutes from the standard formulas (addendum 1 m, dedendum 1.25 m), with radial flanks below the base circle and straight root chords, no root fillets.
- CENTRE DISTANCE IS NOT A HARD DIMENSION. It follows module and tooth counts, and a hard dimension can only be constant or follow a same-named param. Its only harness evidence is the overlap gate on the meshed print layout, at default params only. Sweep samples are not checked for overlap.
- Mesh clearance and centre distance are checked out-of-band on reloaded files across one tooth pitch, at defaults and at the tightest corner. The results are in batch_ten_progress.md.
- Printed in one pose, the two bodies are about one clearance apart at the flanks; whether they stay separate at this gap is unverified on a real printer.
- No load rating. PLA gears at light duty only; backlash and wear are untested.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
