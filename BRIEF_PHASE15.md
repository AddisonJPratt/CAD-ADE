# Phase 1.5 build brief — eval runner + in-house MCP wrapper

Read CLAUDE.md, README.md, BUILD_LOG.md and evals/EVALS.md first. Work only in this
folder. Python is `.venv/bin/python`. Hard rule carried over from Phase 1: the harness
makes NO LLM calls — neither deliverable below may call an LLM, the network, or a shell
with `shell=True`. Never weaken an existing gate. All geometry claims come from files
reloaded from disk.

## Deliverable 1 — eval runner

- New file `evals/run_evals.py`, runnable as
  `.venv/bin/python evals/run_evals.py [--quick] [--out DIR]`.
  If it is clean to do, also expose it as a `magic.py evals` subcommand; if not, leave
  magic.py untouched and say why.
- For each brief in `evals/briefs/*.yaml` (note: the wall_bracket eval brief is a symlink
  to `../briefs/wall_bracket.yaml` — handle it), find the design `designs/<stem>.py`:
  - No design file → status `NO_DESIGN`, counted separately. This is a coverage gap,
    not a design failure.
  - Design exists → run the harness on it in a subprocess (full `run` semantics
    including sweep; `--quick` uses `check` semantics and skips the sweep), capture the
    run's `report.json`, and record per-gate status plus the EVALS.md metrics:
    runs, dimensional x/y, printable, parametric (sweep share), wall-clock time.
- Outputs go to `evals/results/<timestamp>/`: `eval_report.json` and `eval_report.md`
  (a per-brief table + summary). The summary must state BOTH numbers separately and
  never blend them: pass rate over designs present, and coverage (designs present /
  total briefs).
- Exit code: 0 when every present design passes, 1 when any present design fails.
  NO_DESIGN never fails the run, but must be prominent in both reports.
- Update `evals/EVALS.md`: refresh the Results table with this run's real numbers and
  note the runner now exists (keep the file's existing structure and honesty — the
  other four briefs still have no designs).
- Tests: unit tests for the aggregation logic using fabricated report dicts (pass,
  fail, no-design, malformed report) that run in seconds with no CAD. Put them where
  they fit the existing tests/ layout.
- Smoke proof: run the runner against the current repo. Expected: wall_bracket PASS,
  4 × NO_DESIGN, exit 0. Include the actual summary numbers in your final message.

## Deliverable 2 — in-house MCP wrapper ("magic-cad")

Our own MCP server that wraps this project's harness and data, instead of depending
only on the third-party build123d-mcp.

- Location: `mcp/magic_cad_server.py` (+ `mcp/README.md`). Stdio transport.
- Use the mcp SDK version ALREADY installed in `.venv`. Caution: it is SDK 2.x —
  `mcp.server.fastmcp` does not exist (FastMCP was renamed; see the migration note the
  import error prints). Discover the installed API from the package itself. Do not pip
  install anything without flagging it in your summary as a proposed change instead.
- Tools — typed inputs, structured dict outputs (never prose strings):
  1. `list_designs()` → each design in designs/ with whether a matching brief exists.
  2. `list_eval_briefs()` → each eval brief with design presence.
  3. `run_check(design)` → subprocess harness check; returns
     `{pass, gates: [{name, status}], report_path}` parsed from report.json. Generous
     timeout (harness runs take minutes); on timeout/crash return a structured error,
     never an unhandled exception.
  4. `measure_file(path)` → for an STL (and STEP if the installed stack makes it
     clean): volume_mm3, bbox_mm, and for STL via trimesh reload: watertight,
     component count.
  5. `min_gap(path_a, path_b)` → exact clearance via manifold3d on reloaded STLs
     (STL only — say so in the tool description).
  6. `library_lookup(query)` → case-insensitive substring search over
     library/standard_parts.json keys/values; returns the matching entries.
  7. `eval_status()` → summary of the newest evals/results/*/eval_report.json, or a
     clear "no eval run yet" result.
- Safety: every path argument is resolved and must stay inside the project root —
  reject escapes. Subprocesses use the project `.venv` python. No network.
- Tests: function-level tests (e.g. measure_file on runs/wall_bracket/bracket.stl
  expects volume ≈ 78,220 mm³ ±1%; library_lookup("608") finds the bearing; a `../`
  path is rejected). Plus a protocol-level smoke test if the SDK makes it practical:
  spawn the server, list tools, call one.
- Registration: put the exact command in mcp/README.md:
  `claude mcp add magic-cad --scope user -- <abs .venv python> <abs mcp/magic_cad_server.py>`
  Do NOT edit ~/.claude.json or ~/.claude/settings.json yourself — registration is done
  outside this session.
- Prove it works: list the server's tools through a real MCP client call and call
  measure_file + library_lookup; quote the results in your final message.

## Final message

Files built, tests run and their results, the eval runner smoke numbers, the MCP tool
list with two sample call results, and any flagged assumptions or proposed changes.
