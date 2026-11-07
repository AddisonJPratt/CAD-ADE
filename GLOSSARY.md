# Glossary

**Assembly file**: `assembly.py` in a project. It's Python with a `PARAMS` table and
`assemble(asm, **params)`, and it declares instances and how they connect. Written by people
or agents, and evaluated by the assembly gate.

**Assembly manifest**: `outputs/_assembly/assembly.json`, which the assembly gate derives from
the assembly file (schema `assembly/manifest.schema.json`). It's the only thing Studio, the parts
list and the instructions read. Never written by hand. See ADR 0001.

**Instance**: one placed thing in an assembly: a printed part, a piece of library hardware
(screw, heat-set insert) or a purchased component from the catalogue. It has an id, a parent
in the assembly tree, a transform and a mesh.

**Joint**: a connection between a parent instance and a child instance, with an origin, a unit
axis, a rest value and an optional range of motion. Its type is `fixed`, `revolute` or
`prismatic`; its role is `fastener` (a screw in its host), `press` (an insert in its host) or
`clamp` (a part screwed down onto another part through an insert).

**Explode offset**: how far an instance moves in the fully exploded view, its ancestors' moves
included. It's derived by the explode rule in `assembly/manifest.py` and scaled by Studio's slider.
