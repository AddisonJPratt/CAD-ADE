# Magic CAD report: wall_bracket.py

**Overall: PASS**  
Command: `magic.py check /home/hatch/workspace/magic-cad/designs/wall_bracket.py --brief /home/hatch/workspace/magic-cad/evals/briefs/wall_bracket.yaml --out /home/hatch/workspace/magic-cad/evals/results/20261103-205308/runs/wall_bracket --no-sweep`  
Brief: `/home/hatch/workspace/magic-cad/evals/briefs/wall_bracket.yaml`  
Parameters: `{"width": 60.0, "shelf_depth": 80.0, "wall_height": 80.0, "thickness": 8.0, "wall_hole_spacing": 40.0, "shelf_hole_spacing": 40.0, "inner_radius": 4.0, "outer_radius": 1.0, "corner_radius": 4.0, "gusset_thickness": 5.0, "gusset_reach": 0.7, "gusset_edge_radius": 1.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 10.9 s; no hard-coded literals |
| 2 Geometry | PASS | 1/1 solids, volume 78220 mm³, 7/7 dims in ±0.1 |
| 3 Printability | PASS | watertight, single component, fits bed; overhang brief 4.6 %, support risk 0.9 % |
| 4 Renders | PASS | 5 PNGs from reloaded STL |
| Sweep | NOT RUN | --no-sweep: parametric behaviour not verified |
| 5 Exports | NOT RUN | check mode: no exports kept |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| width | 60.000 | 60.000 | 0.000 | PASS |
| shelf_depth | 80.000 | 80.000 | 0.000 | PASS |
| wall_height | 80.000 | 80.000 | 0.000 | PASS |
| wall_hole_spacing | 40.000 | 40.000 | 0.000 | PASS |
| shelf_hole_spacing | 40.000 | 40.000 | 0.000 | PASS |
| wall_holes | 2.000 | 2.000 | 0.000 | PASS |
| shelf_holes | 2.000 | 2.000 | 0.000 | PASS |

## Printability: bracket (reloaded STL)

- Watertight: True; components: 1; faces: 4800
- Extents: 80.00 x 60.00 x 80.00 mm; fits 250x250 bed: True
- Brief overhang metric (downward faces >45° from straight down): 4.58 %
- Support-risk metric (within 45° of straight down, off the bed): 0.95 %
- Flat undersides above bed: 0.00 mm²; bed contact: 4701 mm²
- Thinnest section (approximate, section sampling): ~4.0 mm (step 0.4; short tabs read high) at {'axis': 'Y', 'offset': -18.75}

## Assumptions surfaced

- Only width (60) and the 2x M4 + 2x M4 holes were specified. Everything else is my choice.
- Shelf depth 80 and wall height 80 are chosen; a typical small bookshelf bracket.
- Hole spacing 40 in both legs; holes centred on the free part of each leg.
- Load: 5 kg per bracket at the shelf's front edge (the vision doc's example). Hand estimate only, no FEA: under 2 MPa in the plate beyond the gusset. Load-test before trusting it over anything fragile.
- Thickness 8 mm, set by the M4 counterbore (4.2 deep) plus a 3.8 mm floor, not by load.
- Printed shelf-face-down. Layers cross the wall leg, its weaker direction; the gusset and low stress are what make that acceptable. Unverified on a real print.
- Wall anchors are the installer's choice; M4 screws into a real wall usually need plugs.

## Renders (flat QA renders)

![iso.png](renders/iso.png)
![front.png](renders/front.png)
![top.png](renders/top.png)
![side.png](renders/side.png)
![section.png](renders/section.png)
