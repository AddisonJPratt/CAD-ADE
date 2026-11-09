# magic-cad MCP server

Wraps this project's harness and data over stdio. Makes no LLM calls, uses no network and no
shell. Built on the `mcp` 2.x SDK already in `.venv` (`mcp.server.mcpserver.MCPServer`;
`mcp.server.fastmcp` no longer exists in 2.x).

## Register

Registration is done by you, outside any build session. Run it from the project root after
creating `.venv` (see `MAC_SETUP.md`); `$PWD` expands there, so the absolute paths are right
wherever the repo is cloned (on macOS, e.g. `~/Documents/Repositories/CAD-ADE`):

```bash
claude mcp add magic-cad --scope user -- "$PWD/.venv/bin/python" "$PWD/mcp/magic_cad_server.py"
```

The build123d server the project guide also relies on comes from the same venv:

```bash
claude mcp add build123d --scope user -- "$PWD/.venv/bin/build123d-mcp"
```

Check with `claude mcp list`: both should show `✓ Connected`. If you move the repo, remove and
re-add them (`claude mcp remove magic-cad --scope user`).

`run_check` takes minutes. If your client cuts it off, raise its tool timeout; for Claude Code
that is the `MCP_TOOL_TIMEOUT` environment variable, in milliseconds.

## Tools

Every tool returns a dict. Failures are `{"error": {"code", "message"}}`, not exceptions.

| Tool | Returns |
|---|---|
| `list_designs()` | Each design in `designs/`, with `has_brief` and `brief_path` |
| `list_eval_briefs()` | Each eval brief, with `design_present`; `total` and `designs_present` |
| `run_check(design)` | `{pass, gates: [{name, status}], report_path, brief, exit_code, seconds, error, artefacts}`, plus the artefact images inline |
| `measure_file(path)` | `volume_mm3`, `bbox_mm`; STL adds `watertight`, `components`, `faces`; STEP adds `solids`, `valid` |
| `min_gap(path_a, path_b)` | `gap_mm`, `overlap_volume_mm3`, `search_length_mm`. STL only |
| `library_lookup(query)` | Matching `library/standard_parts.json` entries |
| `eval_status()` | Summary of the newest eval run, or `status: "no_eval_run"` |

Notes on what the numbers mean:

- **`run_check`** runs `magic.py check`, sweep included. A design name resolves to
  `designs/<name>.py`. The brief comes from `briefs/`, then `evals/briefs/`; `magic.py` alone
  only looks in `briefs/`, so an eval design would skip its hard dimensions. With no brief the
  result carries a `warning`. A pass is a gate result: only `magic.py run` verifies a design,
  and a critique still follows.
- **`run_check` artefacts** (#79, the agent's eyes): whenever the build reached Gate 4, pass or
  fail, `artefacts` holds project-relative paths to the iso/top/front/side views, the overhang
  heatmap (seen from below, downward faces coloured by angle; red needs support), the design's
  own section, sections at the thinnest wall and at each named feature, each part's face map,
  and `eyes.json`, plus per-part metrics: `bbox`, `volume_mm3`, `overhang_brief_pct`,
  `support_risk_pct`, `unsupported_area_mm2`, `bed_contact_mm2`, `min_wall_mm`, `min_wall_where`.
  Every PNG also comes back as an inline image with a caption, so the agent sees the part
  without a second call. They are instruments: nothing in them changes a gate. The harness
  writes them to `<out>/eyes/` (`harness/eyes.py`); `artefacts` is null when it stopped earlier.
- **`measure_file`** reloads from disk. STL volume only means something when `watertight` is
  true. STEP runs in a subprocess, so a kernel crash can't take the server down; expect
  several seconds for the build123d import.
- **`min_gap`** is exact on the meshes, so curved surfaces carry facet error. It reads 0 when
  parts touch or overlap, including one nested inside the other; `overlap_volume_mm3` tells
  those apart.
- **`eval_status`** reports `summary.mode`. A `quick` run skipped the sweep.

## Safety

Every path argument is resolved, symlinks included, and must stay inside the project root;
anything else returns `path_outside_project`. Subprocesses use the project `.venv` python, run
with no shell and with stdin closed, and on timeout the whole process group is killed.

`run_check` executes the design file it is given, so it can run any `.py` inside the project.

## Do not add `mcp/__init__.py`

As a plain folder this directory can't shadow the installed `mcp` package, because Python
prefers a regular package over a namespace folder. An `__init__.py` here would break every
`import mcp` with the project root on `sys.path`.

## Test

```bash
.venv/bin/python tests/test_mcp_server.py   # about 30 s; ends with a real stdio client session
```
