# Build brief — the next ten designs (eval batch 2)

Read CLAUDE.md, README.md, evals/EVALS.md and docs/PRODUCT_VISION_UX_SPEC.md first.
Work only in this folder. Python is `.venv/bin/python`. Never weaken a gate. Every
geometry claim from files reloaded from disk. The harness makes no LLM calls.

## Job

Author TEN designs, end to end, one at a time, checkpointing as you go. For each:
brief (if new) → design in `designs/` → full `.venv/bin/python magic.py run` →
iterate on failures (max ~3 serious attempts) → record the outcome in
`batch_ten_progress.md` (design, status, dims x/y, sweep share, time, one-line note)
→ move on even if it FAILS. A design that cannot pass honestly is recorded FAIL with
the reason — never force a pass, never loosen a tolerance, never trim a sweep range
to make a dead design look parametric.

After each design, also append its row to evals/EVALS.md's table (status column) so
the file stays truthful throughout, not just at the end.

## The ten

Existing eval briefs (in `evals/briefs/`; design to the brief as written):

1. **box_with_lid** — box + separate lid, sliding fit. Two solids.
2. **cable_clip** — screw-down snap clip for one round cable.
3. **phone_stand** — 15° tilt, 9 mm case, cable slot. Known limit (README): no probe
   measures an internal slot gap. Gate what the probes CAN measure and state the
   unmeasured gap plainly in the brief's assumptions and your progress note.
4. **planter_pot** — tapered pot, drain hole, foot ring.

New briefs — write the brief in `briefs/<stem>.yaml` (same schema; every hard
dimension gets an honest `measures` probe from the existing set: bbox_x|y|z,
hole_spacing, hole_count) and symlink it into `evals/briefs/` exactly like
wall_bracket's, and add the row to EVALS.md:

5. **project_enclosure** — electronics enclosure ≈100×60×35 mm, separate lid, four
   heat-set insert bosses (use library/ heatset_boss + standard_parts data).
6. **gear_pair** — two spur gears that mesh; params for module and tooth counts;
   axle holes on both. Hard dims limited to what probes measure (bbox, hole
   spacing/count); tooth form goes in assumptions, honestly.
7. **pipe_clamp** — wall clamp for a 32 mm pipe, screw-mounted, compliant strap.
8. **drawer_tray** — desk drawer organizer tray with three compartments (dividers
   as real geometry), outer dims parametrised.
9. **doorstop** — wedge doorstop with grip ribs on the underside; watch the print
   orientation and overhang honestly.
10. **cable_spool** — wall-mounted cable winder spool with a retaining lip and a
    centre screw mount.

Domains matter: functional (1,2,7,8,9,10), electronics (5), mechanism (6), home (3,4).
Vary the geometry honestly — these ten are the "builds anything" evidence, not ten
boxes with different labels. Use `library/` helpers where they fit; if a design needs
a feature the library lacks, write it in the design and note it as a library
candidate in the progress file.

## Finish

- Run the full eval runner (`.venv/bin/python magic.py evals`) and quote its summary:
  pass rate AND coverage, separately.
- Update EVALS.md Results with the new numbers.
- Final message: the ten-row table (design · PASS/FAIL · dims · sweep · time), the
  eval summary, every FAIL's reason, and flagged assumptions. If you run out of
  road before ten, the progress file is the deliverable — say exactly where you
  stopped.
