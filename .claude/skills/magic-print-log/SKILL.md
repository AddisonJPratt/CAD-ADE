---
name: magic-print-log
description: "Log real print results and turn them into calibrated numbers: fit outcomes, measured-vs-modelled dimensions, failures, and the clearance updates that feed back into CLAUDE.md. Use whenever a physical print happened, a fit was tested, a part failed on the printer or in the hand, or before trusting any table clearance for a new design."
---

# Print log — the printer is the ground truth

Every clearance in CLAUDE.md is a placeholder until a real print replaces it. This skill
is how print evidence becomes design numbers instead of anecdotes.

## Log format

Append one entry per print to `~/workspace/magic-cad/prints/PRINT_LOG.md`:

```
## YYYY-MM-DD — <design> v<n> — <printer>, <filament>, <nozzle>
- Modelled vs measured: <feature>: modelled X.XX → measured Y.YY (tool: calipers)
- Fit results: <joint>: too tight / good / sloppy — one line each, with the clearance used
- Failures: <what broke, delaminated, warped, or didn't fit — and at what layer/feature>
- Verdict: keep / adjust <param> by <delta> / redesign <feature>
```

No entry, no learning: a print that isn't logged didn't happen, calibration-wise.

## Calibration coupons first

Before a new joint type goes into a design, print a coupon: a small plate sweeping the
clearance in 0.05 mm steps (e.g. 0.05–0.50 mm for sliding fits), labelled per step.
Record which step gives the target fit in the log, then update:

- `CLAUDE.md` printer block: replace the placeholder clearance with the measured one,
  dated, with the coupon print referenced.
- The library feature that uses it (snap cantilever, counterbore, boss) gets the new
  default in the same change.

## Rules

- **Measured beats modelled beats table.** When sources conflict, that order wins, and
  §14-style published tables are starting points only.
- One variable per reprint: change the clearance *or* the orientation *or* the material,
  never two, or the log entry can't teach anything.
- A failed print is data: log it with the same care as a success, including photos'
  filenames when they exist.
- Never update a CLAUDE.md clearance from memory or from a single unlogged impression —
  cite the log entry date.
- Holes print undersize, Z is weaker than XY, first layers squish: when a measurement
  surprises you, check those three before inventing a new theory.
