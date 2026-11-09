# 4. Coarse textures are B-rep; fine textures are applied to the mesh at export

Date: 2026-11-08. Status: accepted. Ticket: #52.

## Context

Drafter can add patterns (linear, grid, circular, along a path) and textures (knurl, diamond,
hex, ribbing, embossed or engraved text) to a picked face, from `library/surface.py`. A texture is
many small cells. As B-rep every cell is a boolean tool: a 60 mm coaster with a 2.4 mm diamond is
over 600 cells, slow to build in every sweep sample and a heavy STEP. A diamond knurl on a
cylinder is helical, which the B-rep library does not attempt. Meanwhile every gate the harness
runs on printability already works on the exported STL reloaded from disk, not on the B-rep.

## Decision

- Textures up to `print_rules.texture_brep_max_cells` cells are real B-rep geometry: in the STEP,
  named in the face map (each texture is a `feature`), and checked for new unsupported overhang
  when proposed. Past that, the B-rep functions refuse and `texture()` routes to the mesh.
- `mesh_texture(shape, face, kind, pitch, depth)` records a height field on a planar face or an
  upright cylinder, without holes. The worker applies it to that part's STL right after export:
  manifold3d refines the whole mesh (edges at most pitch/8) and warps the vertices on the face
  inward, fading to zero over two depths at the face edges. The STL stays watertight and one body.
- The STEP stays smooth. Gate 3 therefore expects the STL volume to equal the STEP volume plus
  the texture's recorded volume change, still within the same 1 % facet tolerance.
- Every texture's bounds come from `print_rules` (standard_parts.json): minimum feature =
  nozzle x texture_min_lines, minimum depth = layer_height x texture_min_layers, maximum depth =
  texture_max_aspect x feature width. The library refuses a B-rep texture outside them; Gate 3
  checks every declared texture (B-rep and mesh) again, and the sweep checks every sample. A mesh
  texture is only checked there, because that is where it is made.
- The slicer's fuzzy skin is the cheapest alternative: no geometry, every outer wall roughened at
  print time. It is the right call for "more grip" or "hide layer lines" with no pattern pinned.

## Consequences

- A mesh-textured part's STEP is not the printed shape. Anyone taking the STEP to another CAD
  tool gets the untextured part; the STL is the print file. The report lists each texture with
  its representation so this is visible.
- Mesh textures have no named faces: a pick on a mesh-textured face names the untextured face.
- Refining the whole mesh makes textured STLs large (about 150-250k triangles for a palm-sized
  part); sweep samples pay that each time.
- Print direction still rules: knurl and ribbing grooves run along print-up and add no downward
  faces. Diamond and hex on a wall add steep downward flanks; Gate 3's brief overhang share counts
  them, so on a wall those textures pass only on a part with a large bed footprint. On up-facing
  faces every texture is clear.
