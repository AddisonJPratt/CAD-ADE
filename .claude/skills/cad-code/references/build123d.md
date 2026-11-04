# Build123d

Newer Python CAD library, also built on OCCT, positioned as CadQuery's
successor by much of the same community. Two builder styles are available —
prefer **algebra mode** for scripts you write from scratch; it's more
readable and what most current examples use.

## Mental model (algebra mode)

Objects are plain Python objects combined with operators: `+` (union), `-`
(subtract), `&` (intersect). Locations are set with `Pos`/`Rot`/`Location`
and applied with `*`.

```python
from build123d import *

box = Box(40, 20, 10)
hole = Pos(0, 0, 0) * Cylinder(radius=3, height=12)
part = box - hole
part = fillet(part.edges().filter_by(Axis.Z), radius=1.5)

export_step(part, "part.step")
export_stl(part, "part.stl")
```

There's also **builder mode** (`with BuildPart() as part:` context managers,
closer to CadQuery's imperative style) — use it if the user's existing code
is already written that way, otherwise default to algebra mode for new
scripts.

## Key conventions

- `Box`, `Cylinder`, `Sphere`, `Cone`, `Torus` are ready-made solids;
  2D shapes (`Rectangle`, `Circle`, `Polygon`) get extruded with `extrude()`
  or swept/revolved for more complex forms.
- `.edges()`, `.faces()`, `.vertices()` return `ShapeList` objects you filter
  with `.filter_by(Axis.Z)`, `.filter_by(GeomType.CIRCLE)`, or sort with
  `.sort_by(Axis.Z)[-1]` (topmost) — more explicit than CadQuery's selector
  strings, which makes debugging selection issues easier.
- `Pos(x, y, z)`, `Rot(x, y, z)`, and `Location((x,y,z), (rx,ry,rz))` compose
  with `*` to place/orient geometry; multiply left-to-right applies
  transforms in that order.
- `align=(Align.CENTER, Align.CENTER, Align.MIN)` on primitives controls
  where the origin sits relative to the shape — very useful for stacking
  parts flush on a face instead of doing manual offset math.

## Common gotchas

- **Mixing algebra and builder mode** in the same object graph causes
  confusing errors — pick one style per script.
- **Filter chains returning empty ShapeLists** silently propagate until a
  later operation fails with an unrelated-looking error — if something
  downstream breaks, print `len(shape.edges().filter_by(...))` to check the
  selection actually matched something.
- **Units are mm** by default (same convention as OpenSCAD/CadQuery).
- Build123d is younger and evolves faster than CadQuery — if an API call
  errors as "not found," it's worth checking installed version
  (`python3 -c "import build123d; print(build123d.__version__)"`) rather than
  assuming the script is wrong.

## Structuring for easy edits

Build each named part as its own object, tag it with `.label`, and combine
into a `Compound` so STEP output keeps the parts individually addressable —
union separately (with `+`) only for the fused solid you need for STL:

```python
from build123d import *

base = Box(60, 40, 5)
base.label = "base_plate"          # .label is a plain attribute, not a method

boss1 = Pos(10, 10, 0) * Cylinder(radius=4, height=12)
boss1.label = "mounting_boss_1"

boss2 = Pos(50, 10, 0) * Cylinder(radius=4, height=12)
boss2.label = "mounting_boss_2"

# Named-parts compound — STEP keeps this structure, so downstream CAD
# software (and future edits) can select "mounting_boss_1" directly.
assy = Compound(children=[base, boss1, boss2])
export_step(assy, "part.step")

# Fused single solid for STL/printing:
fused = base + boss1 + boss2
export_stl(fused, "part.stl")
```

Adding a new part later means building it, labeling it, and adding it to
both the `Compound` children list and the `+` chain — the existing parts'
code is untouched.

## Getting real dimensions

```python
bb = fused.bounding_box()
print(bb.size.X, bb.size.Y, bb.size.Z)   # real, built dimensions in mm
```

## Running and exporting

```bash
python3 script.py
```

```python
from build123d import export_step, export_stl, export_svg

export_step(part, "part.step")   # CAD interchange
export_stl(part, "part.stl")     # 3D printing
export_svg(part, "preview.svg")  # headless-safe 2D preview
```
