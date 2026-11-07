# Magic CAD studio UI

These pages are the internal Mission Control view; the customer holder workflow lives in `proof/`.

Read-only workbench over the harness's output. No new Python dependencies: a stdlib server
plus plain HTML, CSS and JS, with Three.js vendored for the Studio view. It reads files
live, never writes to the project, and works fully offline.

## Run

From the project root:

```
.venv/bin/python ui/server.py
```

Then open <http://localhost:8765>. The server binds to 127.0.0.1 only.

## Studio, the home view

`#/` or `#/studio` opens the design with the newest exported model; `#/studio/<stem>` opens
a named one. The part fills the screen and you can move it: drag to orbit, wheel or pinch to
zoom, right-drag to pan, arrow keys and plus or minus when the canvas has focus. The chips
set Iso, Front, Top or Side, and `?cam=iso|front|top|side` sets the opening camera and turns
auto-rotate off, which keeps screenshots repeatable.

**Build** plays the replay: parts grow upward one at a time while the gates light in order
with their real status and detail from `report.json`, ending on the verdict in plain words.

**The replay is a visualisation of the verification run, and it says so on screen.** No
geometry is built or checked when you press it. The order and results are real; the timing
is not (1.2 s per part).

**Which model is shown:** the newest run whose `report.json` names the design and whose
folder holds `.stl` files, by report file time. `_` folders are fixtures and are skipped.
Every STL in that folder loads as its own mesh, in its exported coordinates. If the newest
run has no STLs, the panel says the model is the last exported one. If a run did not write
the STLs beside it, or inputs changed since, the panel says that too. A design with no STL
anywhere is disabled in the switcher.

**Three.js** is 0.160.0, vendored unmodified in `vendor/` (`vendor/VERSION.txt` has the
tarball hash and file list) and imported through an import map. The page has no CDN links.
The map is the page's one inline script, allowed by a CSP hash that the server computes
from `index.html`. Mission Control doesn't download Three.js.

To change the look, edit the `LOOK` block at the top of `studio.js`.

Tests: `node --test ui/tests/studio-core.test.mjs` from the project root. They read real
files under `runs/`.

## Mission Control views

One quiet link joins the two surfaces in each direction.

| View | Route | Shows |
|---|---|---|
| Overview | `#/overview` | Eval pass rate and coverage as two separate figures, every design and eval brief with its status and the scope of its latest run, the latest run's gates, and what the gates do not cover |
| Design | `#/design/wall_bracket` | Gate checklist with detail, dimensions (brief target, measured, delta, tolerance), sweep summary, parameters, the five renders with alt text, run history, and what the gates do not cover. Older runs open at `#/design/wall_bracket/<run folder>` |
| Brief | `#/brief/wall_bracket` | Function, hard dimensions with their measures, interfaces, soft preferences, assumptions, and parameters with draft sliders. Also works for every brief in `evals/briefs/` |
| Evals | `#/evals` | Summary figures and a per-brief table (PASS, FAIL, ERROR, NO_DESIGN) from the newest eval report |
| Library | `#/library` | Standard parts and purchased components with their dimensions; enter a project folder to include its user-measured catalogue |

## Endpoints

| Endpoint | Returns |
|---|---|
| `/api/overview` | Designs with brief presence, latest eval summary, latest run, prints logged |
| `/api/design/<stem>` | The newest `runs/*/report.json` whose `design` field is `<stem>.py`, plus `_`-prefixed provenance fields. `?run=<folder>` selects an older run. `_` folders are fixtures and are skipped |
| `/api/brief/<stem>` | The brief YAML parsed, from `briefs/` then `evals/briefs/` |
| `/api/evals` | The newest `evals/results/*/eval_report.json` |
| `/api/library` | `library/standard_parts.json` and the shared component catalogue; optional `project` query adds that project’s components |
| `/api/studio` | Every design with its status and whether it has a model, plus the default design |
| `/api/studio/<stem>` | The design's function line, its newest run, and the model run: gates, sizes, volume, parts, staleness |
| `/runs/<path>.png`, `/runs/<path>.stl` | Render PNGs and model STLs under `runs/`; nothing else there is served |

Missing data answers 404 with a status word (`NO_DESIGN`, `NO_RUN`, `NO_BRIEF`) that the
UI shows as is.

## Draft and unfinished

- **Sliders are a draft.** They move and show values on the page only. They do not rebuild
  anything, change the brief, or alter a result.
- **Run check is disabled** until rebuild wiring lands in a later phase.
- **"Newest" means newest file time.** The newest `wall_bracket` report can be a check-mode
  run with no exports. The Design view labels the scope, flags it, and links the last full run.
- **No design verdict or slicer data.** The UI reports gates only and shows both as NO DATA.
- **Not yet seen in a browser.** Layout, focus rings, sliders under touch, and the CSP have
  only been checked from code, headers, and a fake DOM. Check them at 390 px and on desktop.
- **Studio has not been seen in a browser either.** Headless Chrome is policy-blocked here.
  Its logic ran against a fake WebGL context, so no pixel has been judged. Material, light,
  exposure and the cut face were set from calculation and need a look.

## Design context

`PRODUCT.md` holds the product context and `DESIGN.md` holds the design system. Neither is
served to the browser.
