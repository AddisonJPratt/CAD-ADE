# Build brief — Studio view: a design CAD studio, not a dashboard

Read `docs/PRODUCT_VISION_UX_SPEC.md` (especially Look and feel + Design
principles), CLAUDE.md's no-slop section, and the existing `ui/` app first.
Work ONLY inside `ui/` (plus `ui/vendor/`). Do not touch designs/, runs/,
evals/, harness/ or magic.py — another session is working there. Python is
`.venv/bin/python`.

## Why

The user rejected the current UI's feel: it reads as an admin dashboard of
tables. Verbatim direction: "Should still feel like a design cad studio. I
want where I can see it being built. I want also to be able to move it
around. Should be clean." The spec agrees: the object owns the screen,
material not wireframe, controls float and stay quiet.

## Build: a new default view, "Studio"

The existing views (Overview / Design / Brief / Evals / Library) stay as-is —
they are Mission Control, the expert surface. Studio becomes the home view
(`#/` and `#/studio`), linked back and forth with one quiet "Mission control"
link.

### The 3D viewport (the whole point)

- Full-viewport canvas. The part is the hero: 70–80% of the screen, centred,
  on a **warm off-white workbench** (the spec's light canvas), soft ground
  shadow, matte material rendering (slightly glossy light-grey "filament"),
  hemisphere + key light. No blueprint blue, no grid, no gradients.
- **Three.js, vendored**: download a pinned release (e.g. 0.160.0) at build
  time — `three.module.js`, `examples/jsm/controls/OrbitControls.js`,
  `examples/jsm/loaders/STLLoader.js` — into `ui/vendor/` and import locally
  via importmap. Runtime must work fully offline; NO CDN links in the page.
  If the download fails, stop and report it rather than hotlinking.
- **Server**: extend `ui/server.py` routing to serve `.stl` files under
  `runs/` (keep the Host allowlist and path protections; correct content
  type). All other behaviour unchanged.
- **Model choice**: for the selected design, use its newest run folder that
  contains STL files (check the overview API's run data; fall back sensibly
  and say so in the UI if only a check run exists). Multi-part designs ship
  per-part STLs (e.g. box.stl + lid.stl) — load every `.stl` in the folder
  as its own mesh, laid out as exported (they share coordinates).
- **Move it around**: OrbitControls — drag to orbit, wheel/pinch to zoom,
  right-drag to pan, with damping. Gentle auto-rotate that stops on first
  interaction. Floating translucent view chips (Iso / Front / Top / Side)
  that tween the camera; support `?cam=iso|front|top|side` in the URL to set
  the opening camera.

### "See it being built" — the Build replay

A prominent **Build** button (the one accent-coloured control). Playing it:
1. Parts appear one at a time (multi-part designs), each growing upward via
   a rising clipping plane — like watching it print/build — ~1.2 s per part.
2. Alongside (slim stage rail, right side or bottom), the five harness gates
   light up in sequence with their REAL status and one-line detail from
   report.json: Execute → Geometry → Printability → Renders → Sweep →
   Exports, ending on the verdict in plain words ("All checks passed" /
   "Failed at printability — see Mission Control").
3. Replayable; scrubbing not required. Label it honestly in small type:
   "Build replay — a visualisation of the verification run."

### The premium bar (user direction, non-negotiable)

This must feel **high quality and premium** — Keyshot-meets-Apple-product-page
restraint, not dev-tool. Concretely:

- **Renderer quality**: antialiasing on, pixel ratio up to 2, ACES filmic tone
  mapping, sRGB output, PCF soft shadows, and environment lighting via
  PMREM + RoomEnvironment (vendor it too) so the material has real light to
  reflect. A contact-soft ground shadow — no hard-edged shadow blob.
- **Material**: a physical material with a soft matte body and a hint of
  sheen — printed filament on a product page, not grey CG clay and not
  chrome. Tune env intensity and roughness until it looks photographed.
- **Motion**: every transition eased (easeInOutCubic or similar), camera
  tweens ~600 ms, panel fades ~200 ms, the build replay smooth. Nothing
  snaps, nothing bounces. Controls fade while the user is orbiting and
  return when they stop (the spec's behaviour).
- **Type and space**: a deliberate type scale (large calm title, small
  precise labels with letterspacing where they're uppercase), generous
  whitespace, 1 px hairlines at low contrast, consistent 4/8 spacing.
  Panels are translucent with a *subtle functional* backdrop blur over the
  3D view (the product spec's floating controls — this is function, not
  decoration).
- **Details**: the part fades/scales in on load (no spinner); focus states
  are designed, not default; scrollbars hidden or hairline; selection
  colour matches the accent; the whole view stills works with
  prefers-reduced-motion (replay and autorotate respect it).
- In the Impeccable critique, add an explicit **perceived-quality** pass:
  score the view against "would this sit comfortably on a premium product
  page?" and fix what drags it down before finishing.

### Chrome (kept quiet)

- Top bar: "Magic CAD Studio", a design switcher (chips or a select listing
  every design with its status dot — including FAIL and NO_DESIGN states,
  disabled where there's no model), and the Mission Control link.
- One floating translucent panel (right, collapsible): the design's name,
  its one-line function from the brief, and only the numbers that matter:
  overall size (mm), volume, estimated filament (volume × 1.24 g/cm³,
  labelled "est."), gate verdict. NO tables, NO parameter walls.
- Humanist system sans, generous type, hairline rules, one accent (safety
  orange) reserved for Build + status problems. Impeccable bans still apply
  (no gradients, no nested cards, no eyebrow kickers, no emoji icons).
- Mobile: viewport stays full; panel becomes a bottom bar/sheet; chips stay
  reachable; orbit works by touch (OrbitControls does this natively).

### Process + verification

- Use the impeccable skill: update `ui/DESIGN.md` with the studio design
  language, then critique the Studio view, run audit + the deterministic
  detector over the new/changed files, fix P0/P1, and report scores.
- Verify with curl: page 200, vendor files 200, an STL route returns bytes
  (>0, correct design), APIs unchanged. You cannot run a browser here (the
  headless Chrome is policy-blocked) — say so; Pax screenshots it.
- `ui/README.md`: add the Studio view, the vendored Three.js version, and
  the replay's honesty note.

## Final message

Files built/changed, the vendored Three.js version, curl proof (page, vendor,
STL bytes), critique/audit/detector results for the Studio view, how the
model folder is chosen per design, and anything unfinished.
