# Hallmark polish audit

Skill: https://github.com/Nutlope/hallmark, version 2.0.0.
Scope: application polish; immersive viewport and compact edit card preserved.

This pass tokenized existing CSS colours and font families, normalized spacing,
added pressed states, improved disabled controls, and fixed rendered empty-state,
focus-ring and input-border contrast. Long history metadata keeps wrapping.

Verification:
- Source audit before: 102 FAIL, 86 REFLEX, 6 WARN.
- Final rendered audit: 0 FAIL, 5 WARN, 0 open REFLEX.
- Rendered URL was the unopened workspace, at 375, 1280, 1440 and 1920 widths.
- Loaded project and proposal flow were checked separately by both passing
  Playwright tests and their desktop/mobile captures.
- TypeScript and production build passed.

Remaining warnings reviewed:
- Contrast warning targets an earlier orange accept rule, overridden by the
  current green Keep action. Retain for the later stylesheet consolidation.
- Two tabular-number warnings target earlier declarations; explicit overrides
  now apply to the status bar and save label.
- Export menu uses a border plus shadow. Its edge defines the menu against the
  viewport; elevation distinguishes it from docked controls.
- Two filled controls warning refers to active panel toggles, not competing
  primary actions.

Render captures are local audit evidence and are ignored by git.

## Second polish pass

- Replaced on-model numeric overlay with an Envelope disclosure, keeping actual
  computed bounds accessible without covering geometry.
- Added selected camera-preset states and removed decorative status dots.
- Preview browser now counts the proposal's actual bodies and labels its rows
  Preview, rather than implying unloaded saved artifacts contain zero geometry.
- Slightly widened shared camera framing so the model clears the camera dock.
- Added a public browser test using the real cable-clip design: creates an isolated
  project, prepares a cable-diameter proposal, opens the Envelope disclosure and
  rejects the proposal. It captures desktop/mobile curved geometry.
- Hallmark source and rendered workspace audit: 0 FAIL, 5 previously documented
  warnings. Loaded proposal captures also receive visual review.
- Finish-review request for units in the edit diff is deferred: proposal parameter
  metadata has no unit field and may represent unitless counts. The code-style
  diff retains exact source names; geometry envelope dimensions explicitly use mm.
