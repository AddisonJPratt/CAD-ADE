# CadQuery

Python library built on the OCCT (OpenCascade) kernel — the same kernel
behind FreeCAD and most professional CAD tools. Models are built with a
fluent, chainable API centered on a "workplane" and a selector stack, closer
to how you'd actually sketch-and-extrude in a real CAD GUI than OpenSCAD's
pure CSG approach.

## Mental model

You start a `Workplane`, sketch a 2D profile on it, then turn that profile
into 3D with an operation like `.extrude()`. Each call returns a new
`Workplane`, so you chain operations; `.faces()`, `.edges()`, `.vertices()`
with a selector string narrow down what the *next* operation applies to.

```python
import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(40, 20, 10)
    .faces(">Z")
    .workplane()
    .hole(6)
    .edges("|Z")
    .fillet(1.5)
)

cq.exporters.export(result, "part.step")
cq.exporters.export(result, "part.stl")
```

## Key conventions

- `cq.Workplane("XY")` (or `"XZ"`, `"YZ"`) sets the base plane. Chaining
  `.workplane(offset=...)` moves to a new plane relative to the last one —
  this is how you place features on the top face of a solid, etc.
- Selector strings like `">Z"` (face most positive in Z), `"|Z"` (edges
  parallel to Z), `"#Z"` (perpendicular to Z) pick which faces/edges the next
  operation acts on. This is the thing people new to CadQuery trip on most —
  double check selectors match what you intend, especially after a
  `.rotate()` changes what "up" means.
- The "stack" persists context: after `.faces(">Z")`, subsequent calls act on
  that selection until you call `.end()` or another selector.
- Sketch on 2D with `.rect()`, `.circle()`, `.polyline()`, `.spline()`, close
  with `.close()`, then `.extrude()`, `.cutBlind()`, `.revolve()`, or
  `.loft()`.

## Common gotchas

- **Selectors silently matching the wrong face** after a rotation or
  multi-solid union — if a fillet/hole ends up in the wrong place, print
  `result.faces(">Z").vals()` to inspect what's actually selected before
  assuming the geometry logic is wrong.
- **Units are mm** by convention, same as OpenSCAD — no built-in unit system,
  so be explicit in comments if the user gave inches and convert up front.
- **Boolean ops on non-touching/overlapping solids** raise OCCT errors — same
  class of issue as OpenSCAD, just with a more specific (and more useful)
  error message; read it, it usually names the actual geometric problem.
- **`.fillet()` / `.chamfer()` failing** on edges that are too small relative
  to the fillet radius, or on edge sets that don't form a valid loop — reduce
  the radius or narrow the edge selection if this happens.

## Structuring for easy edits

Build each named part as its own `Workplane` result, then combine with
`cq.Assembly` so parts stay individually addressable instead of collapsing
into one opaque solid:

```python
import cadquery as cq

base = cq.Workplane("XY").box(60, 40, 5)
boss1 = cq.Workplane("XY").center(10, 10).cylinder(12, 4)
boss2 = cq.Workplane("XY").center(50, 10).cylinder(12, 4)

assy = (
    cq.Assembly()
    .add(base, name="base_plate")
    .add(boss1, name="mounting_boss_1")
    .add(boss2, name="mounting_boss_2")
)

# assy.save(...) is deprecated — use the exporter function directly:
from cadquery.occ_impl.exporters.assembly import exportAssembly
exportAssembly(assy, "part.step")   # STEP preserves the assembly structure

# for a single fused solid (e.g. for STL/printing), union explicitly:
fused = base.union(boss1).union(boss2)
cq.exporters.export(fused, "part.stl")
```

Adding a new part later is "build it, `.add()` it to the assembly" — the
existing parts' code doesn't need to change. Keep dimensions that appear in
more than one part (e.g. a boss diameter used both to cut and to place) as
a single shared variable, not restated numbers.

## Getting real dimensions

Don't restate input parameters as the reported size — read the actual
bounding box off the built solid:

```python
bb = fused.val().BoundingBox()
print(bb.xlen, bb.ylen, bb.zlen)   # real, built dimensions in mm
```

## Running and exporting

```bash
python3 script.py    # just run it — errors surface as Python exceptions
```

```python
import cadquery as cq

cq.exporters.export(result, "part.step")   # STEP — best for CAD interchange
cq.exporters.export(result, "part.stl")    # STL — 3D printing
cq.exporters.export(result, "part.svg")    # 2D vector preview, no display needed
```

For a quick headless preview image, the SVG exporter is the reliable option
(no OpenGL/display required):

```python
cq.exporters.export(
    result, "preview.svg",
    opt={"projectionDir": (1, 1, 1), "showHidden": False}
)
```
