# Brief: Studio enrichment — bench, grid, axes (Magic CAD UI, round 2)

Read first: `CLAUDE.md`, `docs/PRODUCT_VISION_UX_SPEC.md`, `BRIEF_STUDIO.md`
(includes the premium bar — still fully in force), `ui/DESIGN.md`,
`ui/PRODUCT.md`, and the current `ui/studio.js`, `ui/studio.css`,
`ui/studio-core.js`. Work ONLY inside `ui/`. Another workflow owns
designs/runs/evals — do not touch them.

## Why

The user's verdict on the Studio as built: it looks **almost too simple**.
The part floats in a void — premium and calm, yes, but there is nothing to
judge orientation or scale against, and it reads more like a product photo
than a design studio. The fix is studio *furniture*, added with the same
restraint: a bench, a grid, axes. Not clutter, not a dashboard, and the
part still owns the screen.

## Build

1. **Bench grid.** A ground grid at the part's base plane (z = 0):
   - 10 mm minor cells, 50 mm majors, warm grey lines at low opacity,
     fading radially to nothing well before the frame edges (shader,
     fog, or a generated texture — your choice, but the fade must be
     smooth, not a visible disc edge).
   - Sized generously relative to the part and rescaled when a much
     bigger or smaller design is loaded, so the cells stay honest mm.
   - It must sit *under* the existing soft contact shadow and not fight
     it. The part still grounds visually.
2. **Axis gizmo.** A small orientation triad in a screen corner
   (bottom-left, clear of the view chips): three short axes with tiny
   X / Y / Z letters, rendered in a corner viewport that tracks the main
   camera. Styled from the design tokens — muted ink/graphite with the
   single accent used sparingly (e.g. only where the palette already
   uses it); NOT the rainbow default AxesHelper look. ~56–72 px, quiet.
3. **Scale bar.** A small ground scale indicator near the bottom edge
   ("50 mm" style) that picks the nearest round length for the current
   zoom, hairline with end ticks, same quiet type as the hints. It must
   stay truthful at any zoom — compute it from the camera each frame or
   on change.
4. **Depth.** Give the canvas gentle photographic depth without colour:
   a soft warm radial falloff behind the part (studio backdrop, not a
   decorative gradient — monochrome, barely perceptible) and distance
   fog matched to the canvas colour so the grid melts into it.
5. **A Grid chip** joins the view chips (Iso / Front / Top / Side /
   Grid) toggling the grid + scale bar; default ON; `?grid=0` in the
   URL starts with it off (the axis gizmo stays). Everything else from
   BRIEF_STUDIO keeps working: orbit, tweens, build replay, parts
   fly-in, design switcher, panel, Mission Control untouched.

## Rules

- The Impeccable workflow from BRIEF_STUDIO applies in full: update
  DESIGN.md (document the bench/gizmo as studio furniture with its own
  tokens), critique + audit + detector on the Studio, fix P0/P1, and
  include the perceived-quality pass — this time the question is
  "does it feel like a *studio* now, at the same premium level?"
- Quality floor unchanged: ACES, env lighting, soft shadows, eased
  motion, prefers-reduced-motion respected. The grid fades in on load
  with the part; toggling it is a fade, not a pop.
- Verify with curl (page + assets still 200) and keep the node tests
  green (extend studio-core tests for the scale-bar length choice if
  that logic lands in studio-core).
- Honesty unchanged: no fake data, harness labels stay exact.

## Done looks like

A concise summary: what was added and how the grid fade + gizmo are
implemented, files changed, review scores (critique / audit / detector,
perceived-quality note), curl proof, anything unfinished or faked —
nothing faked.
