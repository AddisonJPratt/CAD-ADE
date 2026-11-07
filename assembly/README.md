# Assemblies

## Assembly file and gate

An assembly file is Python with a `PARAMS` table (same `(default, min, max)` form and
the same no-literals lint as a design) and `assemble(asm, **params)`. It declares:

- printed part instances, each built from its own parametric design: `asm.printed(id, stem, **params)`
- library hardware from `library/standard_parts.json`: `asm.screw(id, "M3", length)`, `asm.insert(id, "M3")`
- purchased components from the catalogue: `asm.component(id, "esp32-devkitc-v4")`
- placements, `asm.place(instance, (x, y, z))`, and connections made with build123d
  `RigidJoint`s: `asm.press(insert, host, mouth)` and `asm.fasten(screw, host, seat, insert=... | into="substrate")`

`model.seats(part, "M3")` and `model.insert_mouths(part, "M3")` find screw-head seats and
insert holes on the built part, so an assembly never repeats a design's hole positions.
See `holder_clip.py` (the demo below as an assembly file) and
`tests/fixtures/assembly_stack/assembly.py` (a lid screwed into a heat-set insert).

`assembly/gate.py` checks, in a subprocess:

| Check | Rule |
|---|---|
| Assembly file | lint passes; every instance builds and every joint connects |
| Collisions | no instance pair overlaps by more than 0.1 mm³, except an insert in its host and a screw in its insert |
| Fasteners | clearance hole from the ISO 273 medium clearance to that + 2 × the sliding fit; into an insert, at least 1.5 × the thread diameter engaged and the tip short of the hole floor and the insert hole's depth; into a substrate, the screw reaches past the part (and no further than `max_depth`, when given) |
| Derived entries | the parts list and assembly order are derived from the assembly; each names every instance exactly once |

The fastener rules are uncalibrated starting values, like the clearance table in
`CLAUDE.md`. Hardware is a simplified envelope (no threads or sockets): a PASS is a
computed check, not a physical assembly test.

```
.venv/bin/python magic.py assembly assembly/holder_clip.py --project .
.venv/bin/python magic.py assembly tests/fixtures/assembly_stack/assembly.py
```

### Parts list

`assembly/parts_list.py` turns the gate's derived rows into the parts list: printed parts
(design and parameters), hardware with size and length, and purchased components with their
source link and dimension provenance, each with a quantity and the instances it covers. It is
never edited by hand. The gate writes it beside its report as `parts_list.csv` and
`parts_list.json`; the engine API serves the current assembly's list at
`GET /projects/parts-list?project=<folder>[&format=csv]`, and Mission Control shows it.

A project folder with an `assembly.py` runs the gate after its designs (`magic.py project`,
or POST `/runs` on the engine API); its verdict carries an `assembly` entry, gate
`6 Assembly`, and passes only if the assembly does. The report is `outputs/_assembly/report.json`.

## Illustrative demo

`demo.get_demo(project_root)` is one **illustrative, read-only example**, not a general
assembly solver. It returns a millimetre-space description containing
three named instances, their mesh URLs, assembled translations and exploded
offsets, a bill of materials, and an ordered illustrative sequence. Rendering
or interpolating those vectors is not a collision-checked tool path, a motion
simulation, or a validated physical assembly procedure. `holder_clip.py` expresses
the same assembly as an assembly file; `test_assembly.py` checks that the gate places
the screws exactly where the demo shows them.

The clip mesh and STEP originate from the `runs/holder_clip` full run. Two M3
screw meshes are simplified envelopes with a nominal 12 mm under-head length;
threads, sockets, and the wall are not modeled. The screw length and mounting
substrate must be selected for the actual build. Fit, insertion, retention,
strength and durability have not been physically verified.

`demo_hashes.json` pins the holder source, relevant library files, brief, report,
STEP and mesh, plus the screw mesh and generator, to this example. A changed or
missing source or artifact is surfaced as a warning; missing or changed meshes
are flagged unavailable. This snapshot detects later changes but does not prove
original artifact provenance. Rerunning or modifying the design requires a new
review of placements and updating the snapshot; do not just replace the hashes.

Run tests from the project root:

```
XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m unittest assembly.test_demo assembly.test_assembly -v
.venv/bin/python tests/test_assembly_api.py
```

The demo tests validate the structural contract, source drift behavior, and static
interference between the screw envelopes and the holder reloaded from its STEP.
