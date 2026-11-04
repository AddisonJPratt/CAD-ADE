# OpenSCAD

Declarative, functional CSG modeling. You describe the final shape as a tree
of primitives combined with boolean operations — there's no notion of
"history" or "features" to edit later, just re-run the script.

## Mental model

Everything is an expression. `cube()`, `cylinder()`, `sphere()` are
primitives; `union()`, `difference()`, `intersection()` combine them;
transforms (`translate()`, `rotate()`, `scale()`) wrap around children.
Order matters inside `difference()` — the first child is the base, everything
after is subtracted.

```scad
difference() {
    cube([40, 20, 10], center=true);
    translate([0, 0, 0])
        cylinder(h=12, r=3, center=true, $fn=32);
}
```

## Key conventions

- Units are millimeters by convention (nothing enforces it — just be consistent).
- `$fn` controls circle/cylinder/sphere smoothness (segment count). Leaving it
  at the default (very low) makes curves look faceted. Use `$fn = 64;` at the
  top of the file for a reasonable global default, or per-object for
  performance-sensitive parts.
- Modules (`module foo(...) { ... }`) are reusable named shapes — use them
  instead of copy-pasting geometry, especially for repeated features like
  mounting holes.
- Variables assigned at the top of the file double as your parameter
  interface — put every dimension the user might want to tweak there.
- `for` loops are common for patterns (bolt hole circles, grids of vents).

## Common gotchas

- **Z-fighting / coincident faces**: when two solids share an exact face
  (e.g. a cylinder hole exactly the same length as the wall it's cutting),
  you can get rendering artifacts or non-manifold results. Overshoot cut
  volumes slightly, e.g. `h = wall_thickness + 2` and center the cut so it
  pokes out both sides.
- **`$fn` too low** silently makes round features look like polygons —
  easy to miss until you look at a render.
- **`minkowski()` and `hull()`** are powerful but slow; avoid on complex
  geometry unless actually needed.
- Preview (`F5` in the GUI) skips full CSG evaluation and can hide real
  errors — always do a full render / actual file export to be sure the model
  is valid.

## Running and exporting

```bash
# Validate + render to check for errors (throws on invalid CSG)
openscad -o /tmp/check.stl model.scad

# Export STL (3D printing)
openscad -o model.stl model.scad

# Export STEP (if OpenSCAD build supports it; falls back to STL if not)
openscad -o model.step model.scad

# Preview PNG — needs a virtual display, plain openscad -o *.png segfaults
# without one ("Unable to open a connection to the X server")
apt-get install -y xvfb   # once per session

# Use --autocenter --viewall instead of guessing --camera coordinates —
# manual camera params easily crop the object out of frame entirely.
xvfb-run -a openscad -o preview.png --imgsize=800,600 --autocenter --viewall model.scad
```

If the STEP export fails ("Current CGAL version does not support STEP
export" or similar), say so and stick to STL — not all OpenSCAD builds
include STEP support.

## Structuring for easy edits

One module per named part, called from a single top-level union — never grow
an existing module to add an unrelated feature:

```scad
module base_plate() { ... }
module mounting_boss(x, y) { ... }   // parameterized so it can be reused per-hole
module lid() { ... }

// --- Top-level assembly: add new parts here, one line each ---
union() {
    base_plate();
    mounting_boss(10, 10);
    mounting_boss(60, 10);
    lid();
}
```

Adding a part later is then "write a new module + add one call," not
untangling an existing boolean tree. If a part should be removable/optional,
gate it with a boolean variable (`include_lid = true;`) rather than deleting
code.

If you need libraries beyond the built-ins (rounded shapes, threads, gears),
BOSL2 is the standard community library, but don't assume it's installed —
check first (`find / -iname "BOSL2" 2>/dev/null`) and fall back to
hand-rolled geometry if it isn't rather than blocking on an install.
