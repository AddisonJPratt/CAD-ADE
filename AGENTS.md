# Magic CAD — agent instructions (any coding agent: Codex, Claude Code, …)

Magic CAD aims to be an agent-driven engineering studio for editable parts and
complete products, including assemblies, hardware, electronics, motion,
exploded views and build instructions. It should be approachable without CAD
expertise and offer a modern, crisp workspace with the depth of professional CAD.
Today its foundation is a deterministic CAD harness: a brief goes in, parametric
build123d code is written, and the harness grades it. Agents propose; evidence
establishes what is known. See `docs/PRODUCT_VISION_UX_SPEC.md`. Read `CLAUDE.md` too — it holds
the house style, clearances, and the design-quality gates, and everything in
it applies no matter which agent you are.

## Project map

- `magic.py` — the harness CLI. `run` (five gates: execute, geometry,
  printability, render, sweep), `evals` (the eval corpus runner).
- `harness/` — the gate implementations. The harness makes NO LLM calls.
- `briefs/` + `evals/briefs/` — brief cards (YAML: function, hard dimensions
  with measurement probes, params with ranges).
- `designs/` — parametric build123d designs, one per brief.
- `library/` — reusable features (counterbored hole, heat-set boss, snap
  cantilever) + `standard_parts.json` (fasteners, bearings, fits).
- `runs/`, `evals/results/` — run evidence. All gate checks read files
  RELOADED FROM DISK, never in-memory shapes.
- `ui/` — the local web app (stdlib Python server, port 8765): the Studio
  (orbitable 3D part, build replay) + Mission Control (expert views).
  Three.js is vendored in `ui/vendor/` — no CDN at runtime.
- `engine/` — the engine API (`magic.py serve`): a project folder in, verdict, live gate
  events and artifacts out. `magic.py project` and `magic.py run` call the same functions.
  `engine/versions.py`: project folders with versions (git inside, never shown as git),
  save and rollback; rollback re-runs the gates.
- `mcp/magic_cad_server.py` — the project's own MCP server (7 typed tools).
- `docs/PRODUCT_VISION_UX_SPEC.md` — the product/UX north star. The customer
  surface stays seamless and simple; the engineering lives underneath.
- `batch_ten_progress.md`, `BUILD_LOG.md` — what has been built and how it
  scored.

## Non-negotiables

1. A design is verified only when `.venv/bin/python magic.py run <design>`
   exits 0 — all gates on the reloaded files, sweep included.
2. If a gate fails, fix the design or the harness. **Never weaken a gate**,
   never edit a brief's hard dimensions to make a design pass, and never
   report a pass you did not run.
3. Report pass rate and coverage separately (the eval runner does).
4. Harness pass ≠ design verdict. Judge the design itself (see the CAD
   critique gate in `CLAUDE.md`); renders are evidence, flat QA previews
   are not product visuals.
5. UI work follows the premium bar: it must feel like a design CAD studio —
   see `ui/DESIGN.md` and the Impeccable workflow in `CLAUDE.md`.
6. Units are mm; Z is print-up; designs are modelled in print orientation
   with the base on z=0; `PARAMS` at the top of every design file.

## Current state (2026-11-05)

- Eval corpus: 11 briefs, **10/11 passing** at 100% coverage
  (`evals/results/20261104-110955/`). The one failure is `planter_pot`:
  its brief's literal overhang metric counts a printable tapered wall at
  83.6% vs a 15% limit. The gate and brief were deliberately left
  unchanged — the owner decides (allow supports in that brief, revisit
  the metric, or accept the fail). Do not resolve this unilaterally.
- Studio view built; **enrichment not yet built** — brief is
  `BRIEF_STUDIO2.md` (bench grid, axis gizmo, scale bar, Grid toggle;
  `ui/` only).
- **First Proof prototype built:** `proof/` offers a round clip and rectangular
  cradle with an Ask→Make→Prove→Shelf flow. Both templates passed their full
  gates and sweeps; their fit and strength have not been physically validated.
- **Tauri development shell drafted:** `desktop/` depends on this checkout and its
  Python environment. It has not been compiled or launched here; it is not an
  installable package. See `desktop/README.md`.
- Future capabilities include assembly modeling, fasteners and electronics,
  exploded views, motion, engineering checks, BOMs and assembly instructions.
  Treat the holder as a first proof, not the full product scope.
- Nothing has been sliced or physically printed yet. "Printable" so far
  means geometry rules only; printer values in `CLAUDE.md` are
  placeholders awaiting the owner's real printer profile.

## Setup

See `MAC_SETUP.md`.
