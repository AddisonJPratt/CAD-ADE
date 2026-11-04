# cad-code

A [Claude Skill](https://docs.claude.com) for generating, editing, and
exporting 3D models through code — using **OpenSCAD**, **CadQuery**, or
**Build123d**.

Point Claude at this skill and it will:

- Pick the right tool for the job (declarative CSG vs. Python-based
  parametric modeling)
- Write parametric, modular scripts (named dimensions, one part = one
  function/module, structured so adding a part later is a small diff)
- Actually **install and execute** the toolchain in its sandbox rather than
  just generating untested code
- **Validate** the result (manifold/degenerate-geometry checks, scale sanity)
  before showing anything
- Export STL / STEP as appropriate
- Render a shaded preview — single-color for simple parts, multi-color for
  assemblies — and build a **spec sheet**: the render next to a parameter
  table with real, measured dimensions, as the standard deliverable
- Handle multi-part scenes like small architectural models (walls, roof,
  door, windows, fascia trim as distinct colored parts), not just single
  mechanical parts
- Build 3D buildings from a **2D DXF floor plan** (wall centerlines +
  door/window layer markers, auto-detected — not re-typed) or from a plain
  prompt when no drawing exists

## What's inside

```
cad-code/
├── SKILL.md                   # entry point: workflow, tool selection, principles
├── references/
│   ├── openscad.md            # OpenSCAD conventions, gotchas, assembly pattern, export
│   ├── cadquery.md            # CadQuery conventions, gotchas, assembly pattern, export
│   └── build123d.md           # Build123d conventions, gotchas, assembly pattern, export
└── scripts/
    ├── render_stl.py            # headless shaded preview render, single part (matplotlib)
    ├── render_assembly.py       # headless shaded preview render, multi-part/multi-color
    ├── check_model.py           # geometry sanity checks (manifold/degenerate/scale)
    ├── spec_sheet.py            # composites render + dimensions table into one image
    ├── dxf_floorplan.py         # parses a 2D DXF floor plan into structured JSON
    └── build_from_floorplan.py  # turns that JSON into real 3D walls with openings
```

All rendering/validation scripts work off exported STL regardless of which
of the three tools produced it, so there's one pipeline instead of three —
and no dependency on OpenGL or a display server.

**DWG note:** DWG is Autodesk's proprietary binary format — there's no
open-source reader available in this environment. The DXF importer covers
the same floor-plan workflow once a `.dwg` is converted/exported to `.dxf`
(LibreCAD, QCAD, the free Autodesk/ODA File Converter, or "Save As DXF" from
most CAD software all do this).

## Installing

### Claude.ai / Claude apps
Download [`cad-code.skill`](./cad-code.skill) from a
[release](../../releases) and upload it from Settings → Capabilities →
Customize → Skills.

### Claude Code / other environments that read skill folders directly
Clone this repo (or just the `cad-code/` folder) into your skills directory,
e.g.:

```bash
git clone https://github.com/<your-username>/cad-code.git /mnt/skills/public/cad-code
```

## Requirements

The sandbox/environment Claude runs in needs outbound access to:
- `archive.ubuntu.com` / apt mirrors (for `apt-get install openscad`)
- `pypi.org` / `files.pythonhosted.org` (for `pip install cadquery build123d numpy-stl ezdxf`)

If those aren't reachable, the skill falls back to writing code without
executing it and tells the user how to run it locally.

## Tested

OpenSCAD, CadQuery, and Build123d paths have all been run end-to-end,
including:
- A multi-part architectural model (a small house: walls, gable roof, door
  opening + panel, two windows with openings + panes), validated, rendered
  in multi-color, and delivered as a spec sheet.
- A full DXF → 3D pipeline: a synthetic floor plan (wall centerlines +
  door/window layer markers) parsed automatically, built into 3D walls with
  correctly-positioned openings, then extended with a roof, fascia trim, and
  door/window panels — openings landed exactly where drawn, not estimated.

See `references/` for tool-specific patterns and `scripts/` for the shared
pipeline.

## Known limitations

- **DWG is not supported directly** — see above; convert to DXF first.
- `check_model.py`'s manifold check is approximate (mesh-edge-based), not a
  full CAD-kernel check — it can miss some topology issues a tool's own
  build warnings would catch (e.g. OpenSCAD's "may not be a valid
  2-manifold"). Treat the tool's own warnings as authoritative.
- `render_assembly.py` uses a simple painter's-algorithm depth sort, not a
  true depth buffer — very busy/concave multi-part scenes can occasionally
  render a face in front of one that should occlude it. Generate a couple of
  views and inspect before delivering if the scene is complex.
- Rotated-and-unioned slabs meeting only along an edge (e.g. a gable roof
  ridge) can leave a hairline non-manifold seam from floating-point
  precision — cosmetically invisible, but worth a cleanup pass before
  CNC/print use.
- `dxf_floorplan.py` matches openings to walls by proximity/projection, not
  a full architectural-CAD block/attribute model — works well for simple
  layer-convention drawings, may need the layer names or matching tolerance
  adjusted for real-world files with different conventions.

## License

MIT — see [LICENSE](./LICENSE).
