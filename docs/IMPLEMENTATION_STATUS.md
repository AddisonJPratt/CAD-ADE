# Implementation status

Snapshot: November 6, 2026, after the task 7/10 Studio work and local task 8 runtime implementation.
This describes this checkout. GitHub issues may remain open after local implementation;
open issue status alone is not evidence that code is missing.

## Working in the TypeScript app

- Local project opening and version inspection, with saved mesh artifacts.
- Orbit/pan/zoom, camera presets, body visibility, wireframe and per-body STL download.
- Dark/light workspace, collapsible browser/inspector and custom SVG tools.
- Claude Code chat proposals (bounded single-parameter M0), plus an explicit scripted test runtime, before/after preview, interrupt/resume, reject, accept,
  live gate progress, saved version and previous/current verdict comparison (#7).
- Bounded parameter controls create structured proposals through the same lifecycle
  (#10). Values/ranges come from literal PARAMS; units/intent from brief metadata.
  Missing units are identified explicitly. Parameter editing does not use an LLM.

## Next functional work

| Ticket | Missing integration or capability | Existing foundation |
|---|---|---|
| #8 | Owner live demo/acceptance remains | Real Claude adapter; gate-passing opt-in M0 and interrupt evaluations |
| #9 | Make / Studio / Mission Control over shared project state; current-version code, brief and report views | Studio plus existing separate proof and expert apps |
| #12 | Per-claim evidence tiers and production export gating in the new app | Harness reports and verdicts |
| #25, #26 | Model/face selection payload, lasso, note pins, picked distance/angle tools | Orbitable meshes and design selection |
| #11, #13 | Real printer/material profile integration and ElegooSlicer checks | Geometry printability gate; no physical validation |
| #14–#18 | Guided Make/Shelf, print outcomes and approved calibration in the new app | Separate proof app and project versions |
| #19, #20 | Provenance catalogue and general assembly gate | Standard-part library and assembly demos |
| #21–#24 | Assembly tree, isolate/ghost, exploded view, BOM and instructions/playback | Multi-body mesh viewing |
| #27, #28 | Lead briefing and independent reviewer agents in the app | Existing briefs, skills and gate engine |
| #30, #31 | Joint motion and clearance throughout motion | Static geometry checks |

Recommended sequence: owner M0 walkthrough (#8), shared modes (#9), evidence tiers (#12),
selection (#25), then printer/slicer and assembly tracks in dependency order.
Keep the UX quality checks inside each functional ticket. Icons or disabled controls
must never imply an engineering operation that the engine cannot perform.

Physical print acceptance and calibration approval remain owner actions. This status
is not a claim that a finished part has been printed, calibrated or physically tested.

The command menu runs existing camera, panel, browser and theme actions. Watermelon UI
patterns were retrieved through its public MCP and adapted to local CSS/custom SVGs;
no Tailwind, icon library or runtime network dependency was introduced. See M0_DEMO.md.
