---
name: cad-code
description: Generate, edit, and export 3D models using code-based CAD tools (OpenSCAD, CadQuery, Build123d). Use this skill whenever the user wants a parametric 3D model, mechanical part, enclosure, bracket, gear, jig, or any 3D-printable or CNC-able object described in words, wants to write or edit a .scad/.py CAD script, mentions OpenSCAD, CadQuery, or Build123d by name, or asks to export STL/STEP/SVG from a CAD design. Also use this when the user uploads a .scad file or a Python file that imports cadquery or build123d, even if they don't explicitly say "CAD." Trigger even for casual phrasing like "can you model a phone stand for me" or "I need a bracket with 4 mounting holes" — these are CAD generation requests even without CAD jargon.
---

# CAD as Code

Build real, dimensioned 3D geometry through code rather than a GUI. The three
supported tools cover different styles of modeling — pick based on the task
(see "Choosing a tool" below), write the script, actually **run it** in the
sandbox to catch geometry errors before showing the user anything, and export
the files they asked for (or sensible defaults if they didn't say).

Treating this as "write code that probably works" is not good enough — CAD
scripts fail in ways that are only visible at build time (self-intersecting
solids, boolean ops on non-manifold geometry, unit mismatches). Always execute
before presenting a result.

## Choosing a tool

| Signal | Tool |
|---|---|
| User names one explicitly, or uploads a `.scad` file, or a `.py` file importing `cadquery`/`build123d` | Use that one |
| Simple, mostly-solid shapes built from primitives + boolean ops (boxes, cylinders, holes, extrusions), or the user wants something short and self-contained | **OpenSCAD** |
| General-purpose parametric part, especially if the user wants Python, wants to integrate with other Python code/data, or the part has more complex geometry (fillets, chamfers, lofts, shelling) | **CadQuery** (default when nothing else points elsewhere) |
| User explicitly wants a modern/fluent Python API, or mentions Build123d, or wants algebra-style (`+`/`-`) construction | **Build123d** |

When genuinely ambiguous and it matters (e.g., the user will maintain this
script long-term), it's fine to ask. For a one-off "make me a ___" request,
just pick CadQuery and move on — don't block on a tool-choice question for a
simple part.

Read the matching reference file before writing code:
- `references/openscad.md`
- `references/cadquery.md`
- `references/build123d.md`

Each covers the tool's core mental model, common gotchas, export commands,
and the **assembly pattern** to use so the design stays easy to extend later
(see "Designing for future edits" below).

## Helper scripts

Three tool-agnostic scripts ship in `scripts/` and work off the exported
STL regardless of which of the three tools produced it — one rendering and
validation path instead of three, which is both simpler and more robust
(no X server, no OpenGL, nothing that can segfault):

- **`scripts/render_stl.py`** — shaded isometric (or front/top/right) preview
  PNG via matplotlib, headless-safe. Also prints the model's real bounding-box
  dimensions as JSON, measured from the mesh — never hand-typed.
- **`scripts/check_model.py`** — geometry sanity checks: degenerate
  triangles, zero-thickness axes, an approximate manifold check, and an
  optional max-dimension ceiling to catch unit-scale bugs. Run before
  delivering anything.
- **`scripts/spec_sheet.py`** — composites the render with a parameter table
  into one "spec sheet" image (render on the left, dimensions + descriptions
  on the right). This is the standard deliverable — see step 6.
- **`scripts/render_assembly.py`** — like `render_stl.py` but for multi-part,
  multi-color scenes (e.g. walls vs. roof vs. door vs. glazing). Takes a list
  of `(stl_path, hex_color)` pairs. Use this instead of `render_stl.py`
  whenever the model has more than one visually distinct part.
- **`scripts/dxf_floorplan.py`** — parses a 2D DXF floor plan (wall
  centerlines + door/window markers by layer) into structured JSON.
- **`scripts/build_from_floorplan.py`** — turns that JSON into real 3D
  walls with openings cut through, at any wall angle, not just axis-aligned.
  See "Architectural models" below.

These need `numpy`, `matplotlib` (usually already present), and `numpy-stl`:

```bash
python3 -c "import stl" 2>/dev/null || pip install numpy-stl --break-system-packages
```

## Workflow

### 1. Set up the environment

Check whether the tool is available before assuming it isn't:

```bash
which openscad                                  # OpenSCAD
python3 -c "import cadquery"                    # CadQuery
python3 -c "import build123d"                   # Build123d
```

If missing, install it:

```bash
# OpenSCAD (apt is available in this sandbox)
apt-get install -y openscad

# CadQuery / Build123d (pure pip, but pull in a fairly large OCP wheel —
# this can take a minute or two, that's normal)
pip install cadquery --break-system-packages
pip install build123d --break-system-packages
```

If an install genuinely fails (e.g. network restrictions in a different
environment), don't block the whole task on it — fall back to writing the
best possible script, explain to the user that you couldn't execute it in
this environment, and tell them how to run it locally (`openscad model.scad`,
or `python model.py`).

### 2. Write the script

Work in a scratch directory, e.g. `/home/claude/cad/`. Write the script with
real parameters as named variables at the top (not magic numbers buried in
the geometry calls) — the user will very likely want to tweak dimensions
afterward, and a script that's already parametric saves them a round trip.

### 3. Run it and fix errors before showing anything

Execute the script. CAD kernels fail loudly and specifically — read the error,
don't guess. Common failure classes:
- Boolean operations on geometry that doesn't actually overlap/touch (produces
  empty or non-manifold results)
- Units mismatch (OpenSCAD and CadQuery both default to mm; double check if
  the user gave inches)
- Over-constrained sketches or profiles that don't close in CadQuery/Build123d

Iterate until it runs clean. If OpenSCAD reports warnings (not just errors),
check them too — "object may not be a valid 2-manifold" warnings often mean
the part won't slice cleanly for 3D printing even though OpenSCAD rendered it.

### 4. Export

Default export format depends on stated or implied use:
- **3D printing** → STL
- **Sharing with other CAD software / manufacturing (CNC, injection molding, sharing with engineers)** → STEP
- **User just wants to see the shape / no stated use** → STL, and mention STEP is available too
- User asked for something specific → give them exactly that

Commands are in the tool-specific reference files.

### 5. Validate before showing anything

```bash
python3 scripts/check_model.py model.stl --expect-max-dim 500
```

This is a second, independent sweep on top of step 3 — it catches
exported-mesh-level defects (degenerate triangles, open edges, zero-thickness
axes) that a tool's own build can miss. It's approximate, not a full CAD
kernel, so it's a supplement to the tool's own warnings, not a replacement —
if OpenSCAD prints a manifold warning, trust that even if this check passes
clean. If `check_model.py` fails, fix the geometry and re-export before
moving on; don't hand over a model that failed its own sanity check.

### 6. Render + build the spec sheet

```bash
python3 scripts/render_stl.py model.stl render_iso.png --view iso
# prints {"dims_mm": [x, y, z]} — use these real, measured numbers below
```

Build a `rows.json` of `[parameter_name, value, one-line description]` from
the script's actual named variables — not a paraphrase, the real names the
user will see if they open the script — then:

```bash
python3 scripts/spec_sheet.py render_iso.png spec_sheet.png \
  --title "Part Name" --rows rows.json --bbox <x>,<y>,<z> \
  --notes "Optional one-liner: fit notes, print orientation, load rating, etc."
```

`--view` also accepts `front`, `top`, `right` — use whichever face best shows
the feature the user cares about (e.g. `front` for a slot's cross-section).
For complex/concave parts, generate a couple of views and actually look at
each before picking one — matplotlib's depth-sorting is approximate and can
occasionally render overlapping faces in the wrong order.

### 7. Deliver

Copy the script, every exported file (STL/STEP), and the spec sheet PNG to
`/mnt/user-data/outputs/` and present them all. Users generally want the
source script *and* the export *and* the spec sheet, not just one — the
script is what they'll actually edit next time.

If any step above couldn't run (tool failed to install, rendering failed),
don't block delivery on it — hand over what you do have and say plainly what
was skipped and why.

## Designing for future edits

Assume the user will come back and ask to change or add something — because
they usually do. Structure every script so that's a small diff, not a
rewrite:

- **One named part = one function/module.** Never inline a second feature
  into an existing part's code block; give it its own named unit and call it
  from the top-level assembly.
- **Keep a single top-level assembly step** that just lists/calls the named
  parts, so adding a part is "write a new part + add one line," not "find
  where to splice new geometry into an existing boolean tree."
- **Use each tool's assembly/compound construct** (CadQuery `cq.Assembly`,
  Build123d `Compound`/named parts, OpenSCAD modules called from a single
  top-level union) so individual parts stay addressable and movable
  independently — see the reference files for the exact pattern.
- **Keep the parameter block at the top authoritative.** If a dimension is
  used in more than one place, it should be one variable referenced twice,
  never two numbers that happen to match today.

## Architectural models (buildings, rooms, floor plans)

Buildings are almost entirely rectilinear boolean geometry — walls are boxes,
door/window openings are boxes subtracted through wall thickness, floors and
roofs are extruded/lofted slabs. This fits code-CAD well; CadQuery/Build123d
are the natural choice over OpenSCAD here since assemblies with named,
colored parts (walls/roof/door/windows as separate objects) read far better
than one undifferentiated solid.

### Two entry points: a drawing, or just a prompt

**From a 2D DWG/DXF floor plan:**
- **DWG is not readable directly** — it's Autodesk's proprietary binary
  format and there's no open-source reader available (no apt package, no
  pip package handles real DWG, only DXF). Tell the user this plainly rather
  than pretending it works. They need to export/convert to DXF first —
  LibreCAD, QCAD, the free Autodesk/ODA File Converter, or "Save As DXF"
  from AutoCAD or most CAD software, all do this in seconds.
- Once you have a `.dxf`: `scripts/dxf_floorplan.py` parses wall centerlines
  and door/window openings by **layer name convention** (default `WALLS`,
  `DOORS`, `WINDOWS` — pass `--wall-layer` etc. if the file uses different
  names; open the DXF with `ezdxf` and list layers if unsure:
  `doc.layers` / check what layers entities actually sit on before assuming).
  It handles walls at any angle, not just axis-aligned rectangles.
- `scripts/build_from_floorplan.py` turns the resulting JSON into real 3D
  wall solids with the openings already cut, positioned and sized exactly as
  drawn — not re-typed or estimated.
- Always report what was actually found (`walls_found`, `openings_found`,
  and any `warnings` from the parser) before proceeding — if it found 0
  walls, the layer name is almost certainly wrong; don't silently build an
  empty building.

**From just a prompt ("make me a small house with a porch"):** skip the DXF
step and write the same `floorplan.json` structure by hand (or build walls
directly in CadQuery/Build123d, whichever is faster for the shape) — the
downstream steps (roof, fascia, panels, rendering, spec sheet) are identical
either way. Ask for a footprint size / room count / style if the prompt is
too open-ended to pick reasonable defaults confidently, otherwise just pick
sensible numbers (typical residential: ~2.4-2.7m wall height, ~900mm doors,
~1.0-1.2m windows) and say what you assumed.

### Building up the design

1. Walls first (from DXF or hand-specified), with openings cut through.
2. **Roof**: a gable is two slanted slabs meeting at a ridge; a hip roof adds
   slabs on all four sides. Building each slab as a separately rotated box
   and unioning them is straightforward but can leave a hairline
   non-manifold seam right at the ridge line where two independently-rotated
   parts only touch rather than fully fuse — `check_model.py` will flag this.
   It's usually cosmetically invisible but worth calling out to the user
   rather than silently ignoring, especially if the output is headed for
   CNC/3D printing rather than just visualization.
3. **Fascia / trim**: a thin board (roughly 150-250mm tall, 20-40mm thick is
   typical residential proportion) running along the eave edge at the
   wall-top height, positioned just below/behind the roof overhang. Barge
   boards (the equivalent trim along the gable end's sloped edges) follow
   the same idea, angled to match the roof slope instead of horizontal.
4. **Door/window panels**: model these as separate thin boxes positioned in
   the openings (recessed slightly), not just left as holes — this reads as
   an actual door/window in the render and gives the user something to
   reference if they want to change the glazing style, add a frame, add
   trim, etc. later.
5. Other common architectural features, same boolean-geometry approach:
   **foundation/plinth** (a slightly wider, shorter box below the walls),
   **porch/steps** (stacked boxes narrowing toward the door), **columns**
   (cylinders or chamfered boxes), **soffit** (a thin horizontal panel under
   the roof overhang, closing the gap fascia leaves open).
6. Render with `render_assembly.py`, giving each part its own color — a
   single-color render of a building is much harder to read than a
   mechanical part is.

Scale note: architectural dimensions are usually meters, but keep the script
in millimeters for consistency with the rest of this skill (a 6m wall is
just `6000`) — say so in a comment so the user isn't confused by the large
numbers.

## General principles

- **Parametrize.** Named variables/constants for every dimension the user is
  likely to want to change (wall thickness, hole diameter, overall size).
- **Comment the "why," not the "what."** `// clearance for M3 heat-set insert`
  is useful; `// make a cylinder` is not.
- **Prefer round, standard numbers where the user hasn't specified.** M3/M4
  screw clearances, standard sheet thicknesses, etc., rather than arbitrary
  decimals — say what you assumed.
- **Sanity-check real-world scale.** If a "small bracket" comes out to 400mm
  across, something's wrong — check units before exporting.
- **Dimensions come from the geometry, not from memory.** Always pull the
  bounding box from `render_stl.py`'s output (or the tool's own `.BoundingBox()`
  for CadQuery/Build123d — see reference files) rather than restating the
  input parameters and trusting they match what actually got built.
