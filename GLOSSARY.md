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

**Feature**: a named region of a part that a design declares while building, by wrapping the
cutter or boss that makes it in `library.feature(name, shape)`. The harness names every face of
the finished part that lies on that shape's boundary.

**Face map**: `<part>.faces.json`, written by the harness worker beside each STL and kept with the
exports: every B-rep face of the part with its kind, centre, normal or axis, area, bounding box and
feature name (or null). Studio reads it to name a picked face; it never computes names itself.

**Pick**: one thing the user pointed at on the model in Studio: a body, a face, a circled area or a
point. A pick carries its feature name from the face map when the face has one, and always its
geometry, so the agent gets a description either way. A circled area also carries its catch: every
visible face (with its face-map id and feature) and corner point inside the drawn loop, on any body.

**Note pin**: a short comment the user attaches to a spot on the model. A pin belongs to one saved
version and is kept beside it in `.magic/pins/<version id>.json`, not in the version's files, so
adding one never makes the project unsaved. Every request from that version carries its pins as
`selection.pins`.

**Measurement**: the distance and angle between two picks. Two parallel flat faces measure plane to
plane on the face map's exact planes, the same B-rep reading the geometry gate's bbox probes use;
other pairs measure centre to centre. The angle is between the faces' planes (0° parallel, 90° square).

**Explode offset**: how far an instance moves in the fully exploded view, its ancestors' moves
included. It's derived by the explode rule in `assembly/manifest.py` and scaled by Studio's slider.

**Designer**: the agent that turns a request into a proposal (`AgentAdapter`: Claude Code, or the
scripted fake in tests). In M0 it proposes one bounded parameter change. Given only a brief card it
writes a whole new design (`engine/designer.py`, #61): the engine runs the gates after each attempt
and feeds the report back until the design passes or the budget runs out. See ADR 0004.

**Brief-only project**: a project holding a brief card and no design yet, the designer's input. It
has versions like any project (`create_project_from_brief`); running its gates waits for a design.

**Attempt**: one pass of the designer's loop: the agent writes the design files, the engine reverts
any edit outside `designs/*.py` and `assembly.py`, then runs the quick gates and, once they pass, the
full run with the sweep. The **budget** is a number of attempts and a wall time.

**Reviewer**: the independent agent that judges a kept, gate-passing change with the
magic-cad-reviewer rubric (`engine/reviewer.py`). It has a fresh context and read-only tools, and
never sees the designer's conversation. See ADR 0003.

**Review**: the reviewer's verdict on a version: five scores of 0-4 (20 in all), a band
(adopt-ready, direction approved, rework, reject), slop tells and ranked fixes. 13 or more passes.
It is stored in `.magic/reviews/<version id>.json`. A review is not a print.

**Send-back**: when a review fails, the engine turns its top fix into a new designer proposal, once
per change. The owner still decides whether to keep it.
