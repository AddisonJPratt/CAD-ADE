# 1. The app reads one derived assembly manifest and never computes assembly geometry

Date: 2026-11-07. Status: accepted. Ticket: #56.

## Context

An assembly feeds many readers: the Studio tree and exploded view (#21), the parts list (#22),
the instructions (#23), playback (#24), joint motion (#30) and clearance across motion (#31).
The assembly gate (#20) already builds the assembly in build123d, but its report only gives each
instance's position and Euler rotation. It gives no meshes, no parent tree, no joint axes and no
explode directions. If each reader filled those gaps itself, each would infer the geometry a
little differently. For example, the hand-written `exploded_offset` in `assembly/demo.py` would
quietly diverge from the CAD.

## Decision

The assembly gate writes one **assembly manifest** per assembly: `outputs/_assembly/assembly.json`.
It follows `assembly/manifest.schema.json` and comes with one STL per instance, in that
instance's local frame. Every reader uses only this file.

- Everything is in the assembly frame, in mm and degrees. Transforms are a position plus a
  quaternion `[x, y, z, w]`, in three.js order, so Studio applies them without any conversion.
- The parent tree and the joints are derived from the assembly file's `fasten` and `press`
  connections. Explode offsets are derived by a fixed rule (see the `assembly/manifest.py`
  docstring). Nothing in the manifest is hand-written.
- A failing assembly still gets a manifest, marked `pass: false`, so Studio can show the
  collision. An assembly that does not build gets none, and a stale manifest is deleted.
- A joint's `range` is `null` until motion is declared (#30). Motion fills that field in
  without changing the schema version.
- There are two validators. The engine runs the JSON Schema plus cross-reference checks
  (`assembly.manifest.validate`). Studio runs a shape check (`parseManifest`). Its key lists are
  tied to the schema by a test and to the TypeScript interfaces by `tsc`.

## Consequences

- Studio can be built against the committed holder fixture,
  `tests/fixtures/assembly_manifest/holder_clip.json`, without running CAD.
- Changing a design or the explode rule changes the fixture. The test fails until someone
  reviews the change and runs `python -m assembly.manifest --refresh-fixture`.
- Each gate run exports the meshes again, which costs a little time.
- Any new reader of assembly data reads the manifest. Adding a field means bumping
  `schema_version`, or adding the field as optional and nullable as `range` is.
