# 2. Faces are named by a harness face map, matched geometrically in Studio

Date: 2026-11-07. Status: accepted. Ticket: #25.

## Context

Studio lets the user click a face, a body, a point or a circled area and send it with a request.
The mesh Studio renders is an STL: triangles with no record of which B-rep face they came from,
and no name. build123d keeps a `label` on solids but not on faces (`shape.faces()` returns fresh
wrappers each call, and no label survives a boolean), so a design cannot label a face directly.
The agent still needs to hear "the lid pocket", not "a face at (0, 0, 9)".

## Decision

- A design names a feature where it makes it: `part -= feature("lid pocket", Box(...))`.
  `library.feature(name, shape)` labels the shape and records it; the worker reads the record
  after `build()`. A face of the finished part belongs to the first declared feature whose
  boundary passes through a point on that face: the faces a cutter leaves behind lie on the
  cutter's faces, and a boss's faces are its own.
- The worker writes `<part>.faces.json` beside each STL: every face with its kind, a point on it,
  its normal or axis, area, bounding box and feature name or null. The pipeline keeps it with the
  exports and deletes it with them on a failed run, so it is a version artifact like the STL.
- Studio reads the map and matches a pick geometrically (`studio-app/src/Features.ts`): the
  picked point lies on the face it came from, a flat pick also knows its plane, and the smallest
  face of the expected kind under the point wins. An unnamed face keeps its geometric description.
- The request carries the selection as data, `selection: {design, picks, measurement}`, next to
  the prose the chat already appended. The engine hands it to the agent adapter unchanged and
  echoes it from `GET /proposals/<id>`; the scripted fake agent narrates each pick as a plan
  event. The Claude Code adapter already put `selection` in its context, so it now receives the
  structured picks too.

## Consequences

- Naming is opt-in per design: a design with no `feature(...)` calls still gets a face map, with
  every face unnamed, so older designs keep today's behaviour.
- The map's key list is tied to the worker by the committed fixture
  `tests/fixtures/faces_map/plate.faces.json`: a Python test fails when a fresh export differs,
  and the Studio spec parses the same fixture. Changing the export means reviewing both.
- Matching is geometric, so two coincident faces (an unlikely zero-thickness case) can be
  confused. Per-triangle face ids would need a mesh format that carries them (GLB); not needed yet.
- A feature's name is the first match in declaration order, so a face shared by two features
  belongs to the one declared first.
