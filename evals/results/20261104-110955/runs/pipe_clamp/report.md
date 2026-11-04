# Magic CAD report: pipe_clamp.py

**Overall: PASS**  
Command: `magic.py run /home/hatch/workspace/magic-cad/designs/pipe_clamp.py --brief /home/hatch/workspace/magic-cad/evals/briefs/pipe_clamp.yaml --out /home/hatch/workspace/magic-cad/evals/results/20261104-110955/runs/pipe_clamp`  
Brief: `/home/hatch/workspace/magic-cad/evals/briefs/pipe_clamp.yaml`  
Parameters: `{"pipe_dia": 32.0, "strap_width": 18.0, "strap_t": 2.0, "base_t": 7.0, "hole_spacing": 70.0, "mouth_ratio": 0.85}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 4.03 s; no hard-coded literals |
| 2 Geometry | PASS | 1/1 solids, volume 15784 mm³, 4/4 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 12.8 %, support risk 2.0 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | PASS | 19/19 pass; dead params: none |
| 5 Exports | PASS | clamp.stl, clamp.step |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| hole_spacing | 70.000 | 70.000 | 0.000 | PASS |
| strap_width | 18.000 | 18.000 | 0.000 | PASS |
| mount_holes | 2.000 | 2.000 | 0.000 | PASS |
| clamp_bolts | 1.000 | 1.000 | 0.000 | PASS |

## Printability: clamp (reloaded STL)

- Watertight: True; components: 1; faces: 3240
- Extents: 81.00 x 49.00 x 18.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 12.77 %
- Support-risk metric (within 45° of straight down, off the bed): 2.00 %
- Flat undersides above bed: 0.68 mm²; bed contact: 894 mm²
- Thinnest section (approximate, section sampling): ~1.6 mm (step 0.4; short tabs read high) at {'axis': 'Y', 'offset': 33.69}

## Parameter sweep

**19/19 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 18/19 pass; worst support risk 2.5 %, worst brief overhang 15.5 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 15784 | True | - |
| pipe_dia=min | PASS | 14019 | True | - |
| pipe_dia=max | PASS | 16906 | True | - |
| strap_width=min | PASS | 12208 | True | - |
| strap_width=max | PASS | 26515 | True | - |
| strap_t=min | PASS | 14891 | True | - |
| strap_t=max | PASS | 17702 | True | - |
| base_t=min | PASS | 14373 | True | - |
| base_t=max | PASS | 20007 | True | - |
| hole_spacing=min | PASS | 14158 | True | - |
| hole_spacing=max | PASS | 19035 | True | - |
| mouth_ratio=min | PASS | 15702 | True | - |
| mouth_ratio=max | PASS | 15843 | True | - |
| all=min | PASS | 8177 | False | - |
| all=max | PASS | 46944 | True | - |
| combo1 | PASS | 41422 | True | - |
| combo2 | PASS | 33794 | True | - |
| combo3 | PASS | 24321 | True | - |
| combo4 | PASS | 28108 | True | - |

## Assumptions surfaced

- PIPE BORE IS NOT A HARD DIMENSION. A hole_count probe has a fixed diameter and pipe_dia is a param, so it would fail the sweep. Bore diameter is checked out-of-band on the reloaded STEP at defaults.
- Strap strain is a hand estimate, no FEA: about 1.2 % root strain to pass a 32 mm pipe through a 27 mm mouth with a 2 mm strap, using 1.5 t d / L^2 with d 2.4 mm per side and L about 25 mm of free arc. Load on the wall screws is not rated. Unverified on a real print.
- PLA creeps under sustained clamp load and softens on warm pipes; use PETG or better on hot lines. Not suitable for pressure service, and the part does not seal anything.
- The M3 bolt spans the open mouth (about 27 mm), so it needs a bolt of about 40 mm. It is not in standard_parts.json.
- Wall anchors are the installer's choice.
- Holes are plain, not counterbored. Horizontal counterbores read 21.6 % on the overhang gate against this part's small bed contact. Heads therefore stand proud of the plate and the ears.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
