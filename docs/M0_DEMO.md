# Local Claude M0 demo (#8)

Install Claude Code and log in with `claude auth login` yourself. The app invokes
the installed CLI; it does not collect, copy or store credentials. Both local CAD
MCP executables must be installed in this checkout's `.venv`.

Start the engine with `.venv/bin/python magic.py serve`, then start the Studio with
`npm --prefix studio-app run dev`. Create a fresh project:

```sh
.venv/bin/python magic.py new /tmp/my-m0-bracket --from wall_bracket
```

Open that folder in Studio, request “make the bracket wall 1 mm thicker”, inspect
the proposal and preview, then accept. Watch the gate progress and confirm a new
saved version. The bracket's `thickness` parameter controls both its wall and shelf;
the proposal should explain this. Try another request and interrupt it before
accepting; source and saved versions should remain unchanged. Resume starts the
same request again from its original context rather than restoring a CLI session.

M0 supports one bounded existing PARAMS default change. New geometry, multiple
parameter edits and general file generation remain future work. Claude reads local
skills and can use the strict CAD MCP configuration. These are trusted local CAD
tools, not an OS sandbox. Application source acceptance still validates the scalar
and never allows changing hard requirements or ranges. Accepting also synchronizes
that parameter's editable brief default so sweep checks use the new default.

Opt-in real-runtime evaluations (not ordinary tests):

```sh
.venv/bin/python evals/run_m0.py --project /tmp/fresh-m0-eval
.venv/bin/python evals/run_m0.py --project /tmp/fresh-m0-eval --interrupt
```

Recorded on November 6: real Claude proposal 8→9 mm, both CAD services connected,
skill reads and hardware library lookup observed, acceptance passed all gates and
sweep and saved version 2. Real interruption left source/brief/version IDs unchanged.
Build123d connected; its tools were not called in that recorded request.

**Owner acceptance remains:** Addison must perform the live Studio walkthrough.
Automated evaluation does not close that acceptance requirement. Geometry gate
results do not establish physical fit, strength, or print validation.
