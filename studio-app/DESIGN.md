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
