---
name: magic-kernel-pitfalls
description: "build123d / OpenCascade / trimesh / manifold3d pitfalls and their fixes, learned the hard way in this harness and the SnapWorks pipeline. Use whenever CAD code fails strangely, geometry measures wrong, a boolean misbehaves, an STL is watertight in memory but broken on reload, overhang numbers look impossible, or before writing any non-trivial build123d design. Check here before debugging from scratch."
---

# Kernel pitfalls — check this list before debugging

Every item below cost real debugging time. Match the symptom, apply the fix.

## Reload discipline (the #1 rule)

- **A part can be watertight in memory and fail on STL reload.** float32 export merges
  near-coincident vertices into 4-face edges. Causes seen: a teardrop prism ∩ cone
  intersection; a hull circle vertex ~1° from a flank tangent point.
  → **Always gate on the file reloaded from disk**, never the in-memory shape. The harness
  does this; any ad-hoc check must too.
- Build pins/frustums as **one convex hull**, not an intersection of primitives, to avoid
  the near-coincident-vertex trap.
- **Meshing a shape's faces one at a time poisons its later STL export.** OCC caches each
  face's triangulation on the shape; per-face meshes don't share edge points, and
  `export_stl` reuses them, so a curved part (a thread) reloads with ~1000 open edges.
  Planar parts hide it. → Any analysis that calls `face.tessellate()` runs on
  `copy.deepcopy(shape)` (see `library/engineering.py: unsupported_area`).
- Helical threads: one `sweep(profile, Helix(...), is_frenet=True)` is valid, fast and
  sliver-free; bd_warehouse `Thread` leaves horizontal slivers at segment joints and its
  `fade` ends slope at exactly 45°. Keep profile corners off the core surface (run the
  flanks on into the core) or the union leaves coincident-edge slivers.

## build123d 0.13 specifics

- `Solid.is_valid` is a **property**, not a method — `is_valid()` throws TypeError.
- `shape.fillet(radius, edges)`: the algebra `fillet()` has **no `target` argument**.
- Edge/face **selection tolerances** (e.g. 0.001) are fragile and trip the harness's
  hard-coded-literal lint. Select edges by **nearest expected position** instead.
- Importing build123d costs 7–15 s under load. Budget subprocess timeouts accordingly;
  never shrink a timeout to "make it pass."

## Convex hull traps

- A radius profile that **narrows then runs straight** (cone into a stub, countersink
  into a bore) is NOT convex. A single `hull_points` silently fills it into one fat cone
  — this once made a pin 86% overhang and 33 mm³ into the mating body.
  → Build such shapes as **coaxial hulls and union them**.
- `prism_xz` / `prism_yz`-style hull helpers have the same trap: any non-convex profile
  (notch, footwell, step) **silently fills in** and shows up as unexplained overhang %.
  Split profiles into convex pieces.

## Boolean discipline

- Union overlaps must sit **inside** the other shape's section. Starting an overlap
  "0.1 mm early for safety" moves the catch face — a 0.30 mm snap gap became 0.20 mm.
  Only an exact clearance check caught it.
- Measure mating pairs with `Manifold.min_gap(other, search_len)` on **reloaded** STLs —
  exact clearance, no sampling error.
- Polygon bores read **under nominal** on min_gap (flats sit inside the radius). Size
  polygon bores at `r / cos(pi/n)`.
- Probe one feature by clipping: `A ^ box` isolates a region for measurement.
- In manifold3d 3.5 CrossSection: **no `.intersect()`** — use `a ^ b`. Gap checks at
  exactly 3.0 mm need Round offsets with ~0.01 tolerance; Miter overshoots.

## Overhang measurement traps

- The overhang gate counts faces whose normal points >45° from straight down. Faces at
  exactly 45° land on either side on float noise → build deliberate chamfers at **44°**
  for deterministic results.
- **Vertical** faces can pick up float noise (nz ≈ −1e-17) from `rotation_matrix(±90°)`
  and get counted — one seat read 56% instead of 7%. Snap 90° rotations with `np.round(...)`.
- A flat underside **above** the bed (part standing on pin tips) is invisible to the
  overhang %. Report "flat undersides above bed" alongside any overhang number.

## Environment gaps (cad venvs here have no scipy extras in some envs)

- `mesh.section()` may fail (needs scipy) → use `trimesh.intersections.mesh_plane`.
- `trimesh.convex.convex_hull` may fail → `manifold3d.Manifold.hull_points(pts).to_mesh()`.
- No rtree/networkx/shapely → count STL components with a hand-rolled vertex union-find.
- Text outlines: matplotlib `TextPath(...).to_polygons()` → `CrossSection(polys, FillRule.EvenOdd)`.

## Harness-check traps (from the Phase 1 build log)

- **Dead-param false negative:** moving a symmetric hole pair changes neither volume nor
  bbox. The fingerprint needs mesh **second moments** and **bbox position**, not just
  volume + extents. A param that only moves a part is still alive.
- **Wall estimate bias:** a rasterized wall-thickness estimate read ~0.5 px/side high.
  Calibrate any raster measure against known slabs before trusting it.
- Thinnest-section estimates are approximate: the bracket read ~4.0 mm where construction
  said 3.8 mm. Treat raster numbers as ±0.2 mm unless calibrated tighter.

## Assembly paths

- Static clearance is not assemblability. **Sweep-test** insertion paths: translate each
  part along its insertion path in 0.25 mm steps, boolean against what's already placed.
  (A notched glass band once passed every static check but could not be assembled.)

## When stuck

State which symptom matched, which fix you applied, and what the reloaded-file check says
now. Never report a geometry claim from an in-memory shape.
