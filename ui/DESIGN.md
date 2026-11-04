# Design system

Two surfaces with two deliberately different worlds, because they do different jobs.

- **Studio** (`#/`, `#/studio`), the home view: a part on a workbench. Tokens in `studio.css`.
- **Mission Control** (`#/overview` and the other views), the expert surface: a drafting
  table at night. Tokens in `styles.css`.

They share one rule: the state vocabulary below, a word plus a shape.

# Studio: a part on a workbench

Pinned by `BRIEF_STUDIO.md` and the product spec's Look and feel. An Experience surface: the
work leads, and the interface recedes. Think a product photographed on a seamless sweep,
with the controls a camera app would float over it.

## Scene

Someone holding a problem in mind, looking at the object that solves it, in daylight at a
bench. Light comes from that scene. The object takes the screen, and nothing explains it
until asked.

## Color

Restrained: warm neutrals plus one accent. No gradients anywhere, and the workbench is a
flat page colour under a transparent canvas, so tone mapping can't shift it.

| Token | Value | Job |
|---|---|---|
| `--st-bench` | `#ece9e3` | The workbench |
| `--st-ink` | `#1d1b18` | Text and focus rings, 14:1 on the bench |
| `--st-ink-2` | `#58544d` | Labels and secondary text, at least 5:1 on any pane over a part |
| `--st-rule` | 13 % ink | 1 px hairlines |
| `--st-pane` | `#f7f5f1` at 76 % | Floating panes, with an 18 px backdrop blur |
| `--st-press` | white at 90 % | Pressed chip, current row |
| `--st-signal` | `#f25c05` | Safety orange fill: Build, its rising cut face, failure marks |
| `--st-signal-ink` | `#983300` | The same orange as text, 4.8:1 at worst over a pane on a part |
| `--st-on-signal` | `#190d05` | Text on orange, 5.7:1 |

**What orange means: build, or a problem.** Passing states stay ink. Focus is ink here too,
because orange focus would read as a problem on this surface.

## Material and light

All look values sit in the `LOOK` block at the top of `studio.js`, because they are judged
by eye.

- Filament: `MeshPhysicalMaterial`, light warm grey, roughness 0.56, sheen 0.35, specular
  0.42. Soft matte body with a hint of sheen, neither clay nor chrome.
- Normals: creased at 32 degrees, so curved faces read smooth and real edges stay crisp.
- Light: PMREM `RoomEnvironment` at 0.62, hemisphere fill, one warm key casting PCF soft
  self-shadow. ACES filmic, sRGB, antialiased, pixel ratio up to 2.
- Ground: a contact shadow baked per part from the STL's own triangles, a wide soft pool
  plus a tight core from the faces touching the bed. Both are blurred, so a hard edge can't
  occur. The key light does not shadow the ground.
- Framing: a lens of 26 degrees. The part fills 75 % of the height, or 62 % of the width
  beside the panel; on a phone, 82 % of the width. Measured against real STLs in
  `tests/studio-core.test.mjs`.

## Type

One humanist system stack, no webfonts: `Seravek, "Segoe UI Variable Text", "Segoe UI",
Ubuntu, "Noto Sans", Cantarell, Calibri, "Helvetica Neue", sans-serif`. No monospace here:
numbers are tabular figures in the same face.

| Role | Size | Notes |
|---|---|---|
| Design name | 1.75 rem, 400 | Tracking -0.014 em. 1.25 rem on a phone |
| Absent state | 1.375 rem, 400 | The whole message, centred on the bench |
| Verdict | 1.0625 rem | The end of a replay |
| Body | 0.9375 rem | Function line, values |
| Controls | 0.8125 to 0.875 rem | Chips, menu, stages |
| Fact labels | 0.6875 rem, 500 | Uppercase, tracking 0.08 em, always beside a value |
| Small print | 0.75 rem | Provenance, the replay's honesty line |

## Structure

Spacing steps by 4 and 8. Panes have radius 12 to 14 px, with a soft offset shadow and a
hairline. No pane sits inside another.

- **Top bar**, with no surface of its own: wordmark, design switcher, one quiet Mission
  control link.
- **Details panel**, right, collapsible: name, function line, only the numbers that matter,
  provenance, notices. Multi-part designs show one size row per part, because their union
  is bed layout rather than a size.
- **Dock**, bottom centre: view chips, then Build. The replay rail opens above them.
- **Phone** (760 px and below): the viewport stays full, the panel becomes a bottom sheet,
  stages show as marks, and targets are at least 44 px. The dock hides while the sheet is open.

## Motion

Everything eases with `easeInOutCubic` or its CSS equivalent. Nothing snaps or bounces.

| Moment | Duration |
|---|---|
| Camera tween, by slerp around the target | 600 ms |
| Keyboard nudge | 180 ms |
| Pane fades | 200 ms |
| Part arrives: canvas fades, part scales from 96.5 % | 600 to 700 ms |
| Chrome while orbiting: fades to 14 %, returns 350 ms after release | 200 ms |
| Auto-rotate | Slow, stops for good on first interaction, off if `?cam=` is set |

With `prefers-reduced-motion`: no auto-rotate, camera cuts, and Build shows the final gates
and verdict at once, with the part whole.

## Signature move: the rising cut

Build grows each part upward behind a clipping plane, 1.2 s per part. Back faces seen
through the cut are drawn flat in the accent, so the cross-section reads as a solid orange
layer rising through the part, like watching it print. The gates light beside it with their
real status and detail. A small line under the rail says this is a visualisation of the
verification run, because it is: the build happened earlier, and no geometry is computed.

## Honesty on this surface

- Every figure and gate comes from the shown model's `report.json`; nothing is computed
  except filament, labelled "est.".
- If the shown model isn't from the newest run, or a run didn't write the files beside it,
  or inputs changed since, a notice says so.
- "All checks passed" sits beside "Harness checks only, not a design review or a print."

## Studio bans

The product spec's translucent floating panes are functional here and allowed. Everything
else in the Bans section below still applies, along with: blueprint blue, grids, wireframe
rendering, spinners, tables, parameter walls.

# Mission Control: drafting table at night

Pinned by `BRIEF_UI.md`. This is an Operate surface: standard navigation, standard tables,
standard controls. The world lends type, palette, density, and one signature move, and
nothing else. Tokens live at the top of `styles.css`; this file explains them.

## Scene

One engineer at a desk after dark, reading harness output between agent runs. Dark comes
from that scene and from the brief, not from the category.

## Color

Restrained: tinted neutrals plus one signal.

| Token | Value | Job |
|---|---|---|
| `--ground` | `#12181f` | Work area |
| `--rail` | `#0c1116` | Rail and top bar, the second neutral layer |
| `--raise` | `#1a222b` | Hovered rows and controls |
| `--ink` | `#ece9e1` | Off-white primary text and numbers |
| `--ink-2` | `#a7b2bd` | Labels and secondary text, at least 7:1 on every surface |
| `--rule` | `#2b3641` | Hairlines between rows |
| `--rule-2` | `#6f7f8e` | Strong hairlines, control borders (at least 3:1) |
| `--signal` | `#ff6d1f` | Safety orange, the only hue |
| `--on-signal` | `#0c1116` | Text on an orange fill; never gray |

**What orange means: look here.** Current location, keyboard focus, failures, stale or
draft warnings, and the slider's brief value. Nothing decorative. A PASS stays off-white, because a
pass needs no attention.

## State vocabulary

Shared with Studio, which keeps the shapes and uses its own ink and signal tokens. Every
state is a word plus a shape, so it survives without color.

| State | Mark | Color |
|---|---|---|
| PASS | filled circle | ink |
| NOT RUN, SKIPPED | hollow circle | ink-2 |
| NO_DESIGN, NO_RUN, no data | dash | ink-2 |
| FAIL, ERROR | filled square | signal |
| STALE, PLACEHOLDER, UNCALIBRATED | hollow square | signal |
| DRAFT | filled orange label with `--on-signal` text | signal |

## Type

System stacks only, because the brief bans webfonts.

- UI: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- Data: `ui-monospace, "SF Mono", "Cascadia Mono", "JetBrains Mono", Menlo, Consolas, monospace`

Monospace is for numbers, measurements, parameter names, and file paths, because those are
data and code. Words stay in the sans. Fixed rem scale with tight steps: 0.8125, 0.875
(base), 1.0625, 1.3125, 1.625. Numerals are tabular and right-aligned.

## Structure

- Left rail at desktop; below 760 px it collapses to a top bar with five equal targets at
  least 44 px tall.
- Hairlines separate rows and sections. No cards, no shadows, no boxes in boxes.
- One column of work up to 1120 px wide. Prose keeps to about 70ch; tables take the width.
- Wide tables scroll inside a region that is focusable only when it overflows. The page
  itself never scrolls sideways. Two-column tables cap at 36rem so labels stay near values.

## Signature move: dimension lines

Numeric ranges are drawn the way a drawing dimensions a part: a hairline between two
witness ticks, with the value marked on it.

- Dimensions table: the ±tolerance band is a dimension line, with a tick at the measured
  delta.
- Brief sliders: the min and max are witness ticks on a dimension line, with a fixed tick
  at the brief's value so a moved slider always shows its origin.

The move adds reading precision to a standard table and a native range input. It never
replaces either.

## Title block

Each data view opens with a title block, a single hairline row in the spirit of a drawing's
title block: source file, modified time, and mode. This keeps the first product principle
(show the source) in one consistent place.

## Motion

State only, 150 ms ease-out on hover and focus colors. No page-load choreography. All of it
is removed under `prefers-reduced-motion`.

## Renders

QA PNGs are evidence and are shown unaltered on their white background, not inverted or
tinted. Each links to its full-size file.

## Bans

From the brief and the Impeccable floor: gradients, gradient text, nested cards, kickers or
eyebrows above headings, hero-metric layouts, icon-plus-heading-plus-text card grids,
emoji or unicode glyphs as icons, glass or blur (Studio's floating panes are the one
exception, and only there), gray text on colored backgrounds.
