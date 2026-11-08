# Studio application direction

The owner's November 6 direction supersedes the earlier minimal comparison layout:
a professional CAD workstation with the material presence of an industrial creative
studio. The 3D space occupies the workspace; tools dock over it rather than shrinking
it into a content panel.

- Graphite viewport by default, with a warm neutral light alternative.
- Compact project and tool bars. Browser and inspector can collapse.
- One large comparison view; Before/After switches preserve identical framing.
- Review decisions stay attached to the viewport, with orange reserved for applying work.
- Local environment lighting adds readable reflections without network assets.
- Custom 24-unit SVG icon family: consistent 1.55-unit strokes, no decorative icon tiles.
- Every exposed control must operate a supported function. Assembly, motion and sketch
  authoring remain engine roadmap capabilities and must not appear as working tools.
- Screenshots use actual test geometry. The two-block test is evidence of interaction,
  not a finished CAD product visual.

Check desktop and mobile captures, keyboard access, dark/light focus, model loading,
review errors and acceptance before shipping changes to this surface.

Hallmark 2.0.0 is also used for polish and rendered audits. Preserve this application
layout and user-selected density; apply its app-screen rules rather than marketing
page composition. Record unresolved warnings in `.hallmark/README.md`.

November 6 refinement: use Plasticity's viewport-first sculptural workflow and
Shapr3D's contextual, model-led hierarchy as references, without copying their
branding or implying their modeling capabilities. Owner explicitly requested
restrained glassmorphism on floating docks; this supersedes the earlier no-glass
rule for those functional surfaces. Keep solid fallbacks and reduced-transparency
support. Text uses pearl headings, steel secondary copy and ice-tinted values;
compact property rows replace tall full-width number fields. Remove orange
underlines from navigation and camera buttons.
References: https://www.plasticity.xyz/ and
https://www.shapr3d.com/de-de/content-library/refreshing-the-shapr3d-user-interface

Watermelon UI compatibility pass: Command Search and Tooltip 8 were retrieved from
its public MCP registry and adapted to native dialog/React portals, our design tokens
and custom SVG system. The command menu exposes actual Studio actions, supports
Cmd/Ctrl K, arrows, Enter and Escape, and contains keyboard focus. Source/license
are preserved in src/watermelon/NOTICE.md. No Tailwind/shadcn scaffold is required.

Second Watermelon MCP pass: ButtonGroup 3/12 and Popover 9 inform the contextual
viewport rail, icon/label view segments and native display popover. This adds
working pan/orbit modes, fit visible bodies, surface finishes, studio illumination,
and an XY workplane grid. These are view settings; they never alter CAD geometry
or exported files. Comparison keeps its matched before/after presentation.
Fourteen original SVG glyphs use 1.45-unit strokes and subtle cut-face fills,
including distinct front/top/side faces, orbit, pan, grid and fit. Existing labels
remain accessible names; icon-only tools include pointer/keyboard explanations.

Owner-requested icon finish: colored optical glass. Original SVG silhouettes gain
translucent hue fills, pale refracted rims and subtle offset shadows, with sky,
mint, amber and violet role palettes. Same-hue SVG gradients are confined to the
glyphs, an explicit exception to the previous blanket no-gradient direction.
Light theme uses dark precision strokes; disabled icons lose chroma and use muted
ink. Material previews retain actual finish colors rather than the tool palette.

November 7 palette direction (owner): warm graphite replaces the cool steel/ice cast.
This supersedes the November 6 "steel secondary copy and ice-tinted values" wording.
Dark chrome is stone-toned graphite (bench #151412, docks #201e1b), text runs ink
#ece6dc / label #c4baa9 / stone secondary #aca395 / cream values #f0e2c8, and the grid is
warm (#36322c, sections #4d473e). Light theme keeps its warm bench with dark brown-ink
text (#2f2a23, muted #5e564b, ≥5.8:1). The icons keep their colored optical-glass finish,
but the sky role became warm stone and the neutral role warm grey; mint, amber and violet stay.
Orange stays the single accent for applying work. Material finishes (alloy, porcelain,
graphite) are model colors and were deliberately not retinted. Dark-mode error text uses
#ffa47d (8.8:1); #983300 failed at 2.19:1.

November 7 icon refinement (owner chose "richer glass" over disciplined glass and
quiet line): every view glyph is drawn on one true isometric cube (30° edges,
9.5-unit sides). Front, top and side colour the named face as the gem and leave the rest
clear. Hue now carries meaning: stone = camera views, mint = navigation, violet = display,
amber = workspace. Tool glyphs are faceted glass with a body gradient, a lit facet,
a shadow facet, a hard-edged reflection band and a soft offset shadow under 1.4-unit
precision linework. Interface chrome (search, close, check, arrow, eye) stays plain line.

November 7 layout direction (owner): Conversation desk replaces floating Browser/Inspector cards.
Studio is assistant-led: a resizable conversation column on the left (drag or arrow keys,
320 to 640 px, remembered per browser) holds the plain-language verdict, the thread and the
composer; the model fills the rest. Checks, versions and settings (parameters) live in a
drawer opened from a slim rail on the right edge. Bodies are chips on the viewport. No bento or
card panels; controls are 28 px on desktop and 40 px or more on touch. The assistant is named
"Drafter" (constant ASSISTANT in main.tsx). Verdicts read as "Ready to print", "Not ready to
print" or "Not checked yet", with each gate translated into maker language and the untested
real print always listed. Studio never shows .py filenames; Mission Control (the expert view)
still does. Selection tools (body, face, point) highlight in the accent colour and ride into
the next request as chips. A chip reads the feature's name when the harness face map names
the face ("Lid pocket · plate") and where the face points when it does not ("Face on plate ·
front"); the request carries both the name and the geometry. Keep (orange) stays the single accent for applying work.

November 7 polish (owner): no glowing status dots or coloured meters; state is said in words or
small check/cross line glyphs. The owner's custom optical-glass icon family stays everywhere in the
chrome (rail, drawer rail, trays, composer tools, body toggles); only icons inside solid filled
buttons (Keep, Propose, Open) render as plain strokes, where glass on a solid fill is unreadable.
Controls follow Watermelon's dense patterns: 24 px buttons grouped in one ringed tray
(ButtonGroup 12) instead of separate bordered boxes, selection tools inside the composer
(Contextual AI Bar), an icon-only drawer rail with hover labels (Vertical Tooltip Navbar).
Propose is a 28 px arrow button; no native validation bubbles anywhere.

November 7 selection model (owner): pointing happens on the model, not in the chat. Hover
pre-highlights the face under the cursor; click selects it (outlined in the accent), double-click
selects the whole body, Shift adds, a click on empty space clears, Escape clears. "Circle an area"
on the viewport rail draws a lasso that is laid onto the surface as a loop. A compact action bar
sits under the selection: Ask, Measure (with two selections), Note, Keep as is (shown in sage, sent
as "keep unchanged"). Measurements appear as a dimension on the model; clicking the number and
typing a new value writes the request. The composer only shows what is attached (chips).

November 7 brand (owner): the mark is the Magic box, a graphite box in true isometric (30° edges)
whose lid floats just above the base, with warm light spilling out of the gap: something magic
inside, and a nod to the enclosures the product makes. The wordmark is MAGIC CAD in wide capitals,
Archivo at width 125 and weight 700 with +0.03em tracking (SIL OFL 1.1), drawn as outlines in
src/Brand.tsx so the app loads no font. Header lockup: 22 px mark, 8 px gap, 9.5 px wordmark in the
text colour; on phones the wordmark drops and the mark stays. Light surfaces use the graphite finish;
dark surfaces use a lifted finish with brighter rims so the outline holds on the graphite header.
The app icon and favicon sit on a warm stone tile (#efe9df to #cfc6b6); the favicon widens the gap
and drops the bloom so the light survives 16 px. The glow is the one deliberate non-action use of
orange: it belongs to the mark only and never appears on controls. The isometric cube glyph is a
camera-view icon again, not the logo. Sources: public/brand/*.svg, public/favicon.svg.
