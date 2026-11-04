# Magic CAD report: wall_bracket.py

**Overall: PASS**  
Command: `sweep`  
Brief: `briefs/wall_bracket.yaml`  
Parameters: `{"width": 60.0, "shelf_depth": 80.0, "wall_height": 80.0, "thickness": 8.0, "wall_hole_spacing": 40.0, "shelf_hole_spacing": 40.0, "inner_radius": 4.0, "outer_radius": 1.0, "corner_radius": 4.0, "gusset_thickness": 5.0, "gusset_reach": 0.7, "gusset_edge_radius": 1.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 9.81 s |
| Sweep | PASS | 31/31 pass; dead params: none |

## Parameter sweep

**31/31 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 31/31 pass; worst support risk 2.8 %, worst brief overhang 6.4 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 78220 | True | - |
| width=min | PASS | 73343 | True | - |
| width=max | PASS | 126988 | True | - |
| shelf_depth=min | PASS | 66860 | True | - |
| shelf_depth=max | PASS | 100938 | True | - |
| wall_height=min | PASS | 66860 | True | - |
| wall_height=max | PASS | 100938 | True | - |
| thickness=min | PASS | 69777 | True | - |
| thickness=max | PASS | 94753 | True | - |
| wall_hole_spacing=min | PASS | 78220 | True | - |
| wall_hole_spacing=max | PASS | 78220 | True | - |
| shelf_hole_spacing=min | PASS | 78220 | True | - |
| shelf_hole_spacing=max | PASS | 78220 | True | - |
| inner_radius=min | PASS | 78137 | True | - |
| inner_radius=max | PASS | 78456 | True | - |
| outer_radius=min | PASS | 78229 | True | - |
| outer_radius=max | PASS | 78117 | True | - |
| corner_radius=min | PASS | 78302 | True | - |
| corner_radius=max | PASS | 77890 | True | - |
| gusset_thickness=min | PASS | 76953 | True | - |
| gusset_thickness=max | PASS | 82020 | True | - |
| gusset_reach=min | PASS | 75118 | True | - |
| gusset_reach=max | PASS | 81226 | True | - |
| gusset_edge_radius=min | PASS | 78242 | True | - |
| gusset_edge_radius=max | PASS | 78182 | True | - |
| all=min | PASS | 44709 | True | - |
| all=max | PASS | 263552 | True | - |
| combo1 | PASS | 171433 | True | - |
| combo2 | PASS | 107752 | True | - |
| combo3 | PASS | 133776 | True | - |
| combo4 | PASS | 161186 | True | - |

## Assumptions surfaced

- Only width (60) and the 2x M4 + 2x M4 holes were specified. Everything else is my choice.
- Shelf depth 80 and wall height 80 are chosen; a typical small bookshelf bracket.
- Hole spacing 40 in both legs; holes centred on the free part of each leg.
- Load: 5 kg per bracket at the shelf's front edge (the vision doc's example). Hand estimate only, no FEA: under 2 MPa in the plate beyond the gusset. Load-test before trusting it over anything fragile.
- Thickness 8 mm, set by the M4 counterbore (4.2 deep) plus a 3.8 mm floor, not by load.
- Printed shelf-face-down. Layers cross the wall leg, its weaker direction; the gusset and low stress are what make that acceptable. Unverified on a real print.
- Wall anchors are the installer's choice; M4 screws into a real wall usually need plugs.
