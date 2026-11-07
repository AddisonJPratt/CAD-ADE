---
name: magic-slicer-check
description: "Slice a Magic CAD export with a real slicer CLI and judge the result: print time, material, support volume, and first-layer sanity. Use when a design is claimed printable, before adoption, when comparing orientations, or when the printability gate's geometry-only numbers need ground truth. A geometry pass is not a slice pass."
---

# Slicer check — geometry rules are not a sliced part

The harness printability gate checks geometry (watertight, overhang %, bed fit). It has
never seen G-code. This skill closes that gap with a real slicer.

## Workflow

1. **Pick the slicer that's actually installed.** Check in order and use the first found:
   `orca-slicer`, `prusa-slicer`, `bambu-studio` CLI, `cura` engine. If none is
   installed, STOP and report exactly that — "not sliced: no slicer on this machine" —
   never substitute the geometry gate and call it sliced.
2. **Profile:** the project profile from CLAUDE.md (currently placeholder: 0.4 mm nozzle,
   PLA, 3 walls, supports as the design requires). Use the design's stated orientation;
   do not silently re-orient to make numbers prettier.
3. **Slice the reloaded export** (STL or 3MF from disk, the same file the harness gated).
4. **Report:**
   - estimated print time and filament (g and m)
   - support material volume and where the supports land (bed-only vs on-part)
   - layer count, first-layer area
   - any slicer warnings verbatim (floating regions, repaired faces, thin walls)
5. **Judge:** supports touching finished surfaces, a first layer that's mostly brim, or a
   time wildly off the part's size are findings, not footnotes. Compare against a second
   orientation only when the design's print-intent is undecided.

## Rules

- Slice the exact exported file, not a re-export with different tessellation.
- Numbers come from the slicer's own output/G-code header — never estimated by eye.
- A failed or warned slice is a design finding: feed it back as (a) re-orient,
  (b) redesign the overhang to 44° chamfers, or (c) accept supports explicitly.
- Record the result in the design's run folder (`slice_report.md`) so Phase 2's reviewer
  agent can diff slice results across revisions.

## Current status on this machine

**ElegooSlicer 1.5.2.2** (`/Applications/ElegooSlicer.app`) is the project slicer, wired
into the engine as `engine/slicer.py`: `run_project(project, slice=True)` or
`POST /runs {"slice": true}` slices each passing design with the Centauri Carbon 2
0.4 nozzle machine, the 0.20mm Standard process and the project's PLA/PETG filament
(preset paths in `library/printer_profiles.py`). It writes `outputs/<part>/<part>.3mf`,
adds a `Slice` claim, and upgrades the printability claims to `slicer-checked`.
Supports follow the brief's `allow_supports`. The engine slices and exports only; it never
sends a print job. Use it in place of steps 1–4 above; the judging in step 5 still applies.
