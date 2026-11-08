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
- Every exposed control must operate a supported function. Assembly authoring, motion and
  sketch authoring remain engine roadmap capabilities and must not appear as working tools.
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
whose lid floats above the base and swings open 20° on its back edge, so the lit inside shows:
something magic inside, and a nod to the enclosures the product makes. The open lid is deliberate:
with a level lid the mark shrank to a dark cube with a gold band at 16 to 22 px, which reads as the
Kaaba; never return to a closed or level lid. The wordmark is MAGIC CAD in wide capitals,
Archivo at width 125 and weight 700 with +0.03em tracking (SIL OFL 1.1), drawn as outlines in
src/Brand.tsx so the app loads no font. Header lockup: 22 px mark, 8 px gap, 9.5 px wordmark in the
text colour; on phones the wordmark drops and the mark stays. The logo is a plain image named
"Magic CAD" (role img), not a link, and the product name is "Magic CAD" everywhere (Studio is a
mode). Both surfaces use the same graphite; on dark surfaces a 1 px pearl outline that does not
scale keeps the box readable instead of lightening it. The app icon and favicon sit on a warm stone
tile (#efe9df to #cfc6b6); the favicon box fills about 80% of the tile in flat colours with no bloom
so it reads at 16 px. The glow is the one deliberate non-action use of orange: it belongs to the
mark only and never appears on controls. The isometric cube glyph is a camera-view icon again, not
the logo. Sources: public/brand/*.svg, public/favicon.svg.

November 8 type direction (owner): the interface read too bold and too generic. Text is now
Atkinson Hyperlegible Next (Braille Institute, SIL OFL 1.1), self-hosted from src/fonts/ (latin
subset; the app still loads nothing from the network), chosen for unambiguous letterforms in
measurements and part names (I l 1, O 0). src/fonts.css declares the family "Magic Text" with
weight ranges mapped one step lighter: requested weights up to 549 use Regular, 550 to 699 use
Medium, 700 and up use SemiBold. Stylesheets keep their numbers; headings at 600/650 now render
as Medium and 500 labels as Regular. No synthesized bold. The wordmark stays Archivo outlines.

November 8 assembly view (#21): a project whose version has an assembly manifest opens in an
Assembly view, switched with Parts from a tray in the stage bar. The tree is a compact panel docked
top-right on the viewport (not a drawer, so the model and the tree are read together): one row per
instance, children indented under the part they hang off with a hairline guide, the kind in the
parts list's words. Hide, ghost (see-through) and isolate are 24 px line-glyph toggles that appear
on row hover, focus or selection and stay shown while on. Selection tints the instance with the
selection accent in 3D; hardware renders as steel, purchased components as a dark housing, printed
parts in the chosen finish. The explode slider scales the manifest's derived offsets; a one-line
note says it is not a collision check. The tree is a treegrid: arrow keys move between rows, Tab
reaches that row's toggles, Escape clears the selection.

November 8 tools (#26): the viewport rail gains "Pin a note" and "Measure distance and angle" after
"Circle an area", each a toggle that Escape leaves. A pin is a numbered ink marker on a short stem
(the dimension label's ink, never orange: notes inform, they do not apply work); clicking it opens a
small card with the note, where it sits, and Edit / Delete. A new pin asks for its note inline at
the clicked spot. Measuring takes two clicks without Shift and says the reading in the status hint
("Gap between parallel faces 13.50 mm · angle 0.0°") as well as on the model; the dimension label
adds the angle only when the faces are not parallel; non-parallel pairs say so ("Faces at 90.0° ·
centres 12.9 mm apart"). Measure picks highlight in stone, not orange, while the tool is on, and the
dimension line is ink with end dots. The selection action bar steps aside while a tool is aiming; its
"Note" became "Pin note" (a version pin at the selection, the one note system) and its "Measure"
enters the measure tool with the same rule glyph. A lasso chip counts what it caught ("Circled area on
riser · 2 faces, 8 corners", no "0 corners"); a loop that catches nothing says so and stays in the tool.
Pins, the dimension and the selection bar sit beside the canvas's role=img, not inside it. Deleting a
pin shows "Note deleted · Undo" for ten seconds. In the dark theme the marker is graphite in a cream
ring so it reads on the light model finishes. The note draft flips to the marker's left near the
stage's right edge and docks along the stage bottom on phones. The rule glyph (measure) is a
faceted-glass rule with ticks on its measuring edge, mint like the other pointing tools.
