# UI brief — Magic CAD studio, first draft

Read CLAUDE.md first, especially "Design quality: no AI slop". This is the project's
first UI surface, so the Impeccable rules there are mandatory, not advisory. Work only
in this folder. Python is `.venv/bin/python`.

## Process (use the skills properly)

1. Use the **impeccable** skill (`.claude/skills/impeccable/`): read its SKILL.md and
   follow its workflow. First create the context files it expects in `ui/`:
   `PRODUCT.md` (what this is, who it's for — a one-person engineering studio driving
   agent-built CAD) and `DESIGN.md` (the design system you commit to below).
2. Build the app.
3. Before calling it done: run an Impeccable **critique** (scored) and **audit**
   (P0–P3) on the UI, run the deterministic detector
   (`.claude/skills/impeccable/scripts/impeccable detect ui/` or its documented
   equivalent), fix every P0/P1 and every slop tell it flags, and report the scores,
   the top findings, and what you changed in your final message.

## Stack constraints

- Zero new dependencies. A tiny Python **stdlib** server (`ui/server.py`,
  http.server based) + plain HTML/CSS/JS in `ui/` (index.html, styles.css, app.js).
  No frameworks, no CDN, no webfonts — system font stacks only.
- Server runs from the project root: `.venv/bin/python ui/server.py`, port 8765.
- The UI reads REAL project data live through JSON endpoints — no hard-coded results:
  - `/api/overview` — designs + brief presence, latest eval summary, latest run info
  - `/api/design/<stem>` — that design's newest `runs/*/report.json`
  - `/api/brief/<stem>` — the brief YAML parsed (pyyaml is in the venv)
  - `/api/evals` — newest `evals/results/*/eval_report.json`
  - `/api/library` — `library/standard_parts.json`
  - renders served from `runs/` (the wall_bracket PNGs)
- Missing data renders as an honest state (NO_DESIGN, "—"), never invented numbers.

## Views (single-page app, left rail navigation)

1. **Overview** — studio state: eval pass rate AND coverage as two separate labelled
   figures, designs with status, latest run gates at a glance.
2. **Design — wall_bracket** — gate checklist with status + detail, dimensions table
   (brief target vs measured vs delta, from report.json), sweep summary, parameter
   table, renders gallery (iso / front / top / side / section) with alt text.
3. **Brief** — the brief card rendered properly: function statement, hard dimensions
   with their measures, interfaces, params with min–max sliders. The sliders are a
   DRAFT affordance: they move and show values, and the view must honestly label that
   rebuild wiring lands in a later phase. A "Run check" button exists but disabled
   with that explanation — no fake interactivity pretending to work.
4. **Evals** — per-brief table from the latest eval report (PASS / FAIL / NO_DESIGN),
   summary numbers up top, both rates labelled.
5. **Library** — standard parts grouped by category with key dimensions.

## Design language — commit to it in DESIGN.md

"Drafting table at night": near-black blue-charcoal surfaces, off-white text, ONE
signal accent (safety orange), monospace for all numbers/measurements, hairline rules
instead of boxes-in-boxes. Dense and tabular where data is dense. This is a workbench
for an engineer, not a marketing page.

Hard bans (Impeccable craft floor + project rules): no gradients (especially
purple/blue), no gradient text, no nested cards, no kicker/eyebrow labels above
headings, no hero-metric template, no icon+heading+text card grids as page structure,
no emoji as icons, no glass/blur decoration, no gray text on colored backgrounds.

Responsive: usable at 390 px wide (rail collapses to a top bar) and at desktop.
Accessibility: semantic landmarks, visible focus states, contrast that passes audit,
keyboard-reachable navigation.

## Verification you must do

- Server starts; every endpoint returns 200 with sane JSON (show curl output in your
  summary); the page loads with no console errors you can detect from the code path.
- Impeccable detector output on `ui/` is clean or every remaining hit is explained.
- `ui/README.md` with the exact run command and what each view shows.

## Final message

Files built, endpoint proof, critique score + audit headline findings + what you
fixed, detector result, and anything you flagged as draft/unfinished.
