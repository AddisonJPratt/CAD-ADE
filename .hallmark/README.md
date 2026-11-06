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

## Parameter-panel implementation and toolbar pass (#10)

- Bounded inspector controls now create explicit numeric proposals through the
  same preview/accept/gates/version pipeline as chat. Defaults and ranges are read
  with AST literal parsing; units and intent come from brief metadata.
- Custom hierarchy, inspector and parameter-adjustment SVGs clarify toolbar roles.
  Active panel state is exposed, conflicting actions are disabled during review,
  and project location collapses after opening to leave room for controls.
- Continuous parameter types survive whole-number JSON submissions; regression
  coverage accepts 24 and then successfully proposes 24.5.
- Mobile export menu escapes toolbar clipping and produces a real .stl download.
- Two-axis code review: one shared numeric-type finding, fixed and rechecked;
  no remaining actionable standards/spec findings.
- Impeccable critique: 31/40, no remaining P0/P1. Independent accessibility audit
  found no remaining P0/P1 after mobile capture and export fixes.
- Rendered Hallmark audit: 0 FAIL, 5 recorded warnings. Live Impeccable detector:
  0 anti-patterns; its placeholder contrast advisory was corrected with themed ink.
- Capability gaps and recommended ticket sequence: docs/IMPLEMENTATION_STATUS.md.

## Claude M0 and contextual tools pass

- Plasticity/Shapr3D references inform compact property rows, restrained selected
  tools and functional translucent floating docks. Glass was explicitly requested
  by the owner; solid/reduced-transparency fallbacks remain available.
- Watermelon Command Search and Tooltip 8 source retrieved through its public MCP,
  adapted to native dialog/React portals and custom SVGs. See the MIT notice.
- Hallmark rendered workspace audit: 0 FAIL, 7 WARN. The previous five warnings
  remain as documented above. Two new warnings concern requested glass and a
  shared floating-surface recipe: consistent material identifies contextual
  controls over the canvas; panel dimensions and placement distinguish roles.
- Rendered Impeccable detector returned [] (unopened workspace). Loaded state
  screenshots and Playwright exercise the model, properties and command menu.
- Fixed command text inheriting legacy header color and Escape being consumed
  by the native search input before dismissing the dialog.

### Impeccable review provenance

DEGRADED: single-context final UI critique/audit. Independent review capacity was
exhausted during this run; this is not an independent two-assessment result.
Manual review uses source plus desktop/mobile screenshots, with deterministic
rendered checks above. Heuristics (0–4): status 3, real-world match 3, control 4,
consistency 3, prevention 3, recognition 3, efficiency 4, minimalism 3, recovery 3,
help 3 (32/40). The compact measured-property rows and large model retain CAD
context; searchable real commands improve keyboard efficiency without adding
fake capabilities.

Audit: accessibility 3, performance 2, theming 4, responsive 3, integrity 3
(15/20). No open P0/P1 found in the reviewed scope. P2: existing initial JS bundle
remains ~1.2 MB before gzip; later lazy-loading work should reduce startup cost.
P2: small desktop auxiliary labels remain dense; touch/physical-device use has
not been certified. Responsive screenshots are emulation, not device testing.
Questions skipped: user requested continuing implementation; scope is already set.

### Code review provenance

Spec reviewer identified an interrupt-during-stdin BrokenPipe race. Fixed and
covered with the blocked-input process regression. Standards sub-agent stopped
on account usage limit; manual standards review found no further actionable
violations. The final standards axis is therefore not an independent pass.
Owner live M0 acceptance remains explicitly outstanding (docs/M0_DEMO.md).

Final validation: 5/5 Playwright, 20/20 engine integration tests, 68/68 harness
checks; TypeScript/production build passed. Existing large-bundle warning remains.

## Watermelon viewport controls and original icon set

- Retrieved ButtonGroup 3, ButtonGroup 12 and Popover 9 from Watermelon's public
  MCP; retained MIT source references. Adapted grouping, tooltips, native popover,
  settings groups, range readout and reset to supported Studio actions.
- Fourteen original SVG glyphs use facet fills and calibrated 1.45-unit strokes.
  Integrated into orbit/pan, fit, display, grid, view presets, command search,
  surface swatches and hidden-body states. No icon/animation package was added.
- Saved-view controls alter only view state, never CAD/exported geometry. Matched
  proposal previews keep their existing presentation. Lighting updates reuse the
  environment texture rather than regenerating it on every slider movement.
- Source Hallmark: 0 FAIL, 8 WARN, no spacing notes. Rendered unopened workspace:
  0 FAIL; Impeccable live detector []. Loaded desktop/light/mobile display states
  visually reviewed and exercised in the curved-clip browser test.
- New swatch warning is intentional: a dark finish is shown as its true dark color
  on the neutral swatch backdrop. High-contrast text labels and selected checks
  convey its identity/state; the swatch color alone never carries the operation.
- Manual final critique/audit remains degraded (same independent review capacity
  limitation documented above). No P0/P1 found in the reviewed scope. Existing
  bundle-size P2 remains (~1.21 MB before gzip). Physical-device/touch validation
  remains unperformed; phone evidence is browser viewport emulation.
Questions skipped: the user supplied the direction and requested implementation.

Final viewport pass validation: 5/5 Playwright tests and TypeScript/production build
passed. Curved-model coverage verifies material changes in rendered pixels, native
lighting keyboard input, grid reset, drag-to-pan, display dismissal, and mobile
layout; existing accept/reject/version/export paths also pass. No backend changed.
