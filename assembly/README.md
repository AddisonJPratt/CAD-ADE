# Assembly foundation

This is one **illustrative, read-only example**, not a general assembly solver.
`demo.get_demo(project_root)` returns a millimetre-space description containing
three named instances, their mesh URLs, assembled translations and exploded
offsets, a bill of materials, and an ordered illustrative sequence. Rendering
or interpolating those vectors is not a collision-checked tool path, a motion
simulation, or a validated physical assembly procedure.

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
XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m unittest assembly.test_demo -v
```

The tests validate the structural contract, source drift behavior, and static
interference between the screw envelopes and the holder reloaded from its STEP.
