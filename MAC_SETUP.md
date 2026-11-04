# Magic CAD on your Mac — setup

The project is plain files (Python + YAML + a static web UI). No database,
no cloud services, no API keys. Everything runs locally.

## 1. Unpack and install

```bash
cd ~/magic-cad            # wherever you unpacked it
python3 --version         # need 3.11+ (built/tested on 3.12)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` is a full pinned freeze from the working environment
(build123d 0.13.0, trimesh, manifold3d, the MCP SDK, build123d-mcp).

## 2. Smoke tests (each should pass in ~1–2 min)

```bash
.venv/bin/python magic.py run designs/wall_bracket.py   # exit 0 = harness works
.venv/bin/python ui/server.py                            # then open http://localhost:8765
```

The Studio is the default view (`#/studio`); Mission Control is linked
top-right. If the 3D view is blank, it's a WebGL issue in that browser —
Safari/Chrome on macOS are fine.

## 3. Model choice (checked Nov 4, 2026)

Current Codex lineup for ChatGPT sign-in — the GPT-5.x Codex models are
retired there (GPT-5.5 left Oct 14, 2026), so don't pin an old name:

- **Default: GPT-6.1 Sol** (`gpt-6.1-sol`) — OpenAI's recommended default
  for complex agentic coding and long-running work; near-flagship at a
  fraction of the top tier's cost. Reasoning effort **high** for the
  brief builds.
- **Hardest pushes: GPT-6 Astra** (`gpt-6-astra`) — the top tier, if your
  plan's picker offers it.
- **Grunt work: GPT-6 Luna** (`gpt-6-luna`) — searches, summaries, quick
  checks; far larger message allowance.

Set the default in `~/.codex/config.toml` (same file as the MCP servers
below):

```toml
model = "gpt-6.1-sol"
model_reasoning_effort = "high"
```

## 4. Building with Codex

Codex reads `AGENTS.md` in the project root automatically — the house
rules, QA discipline, current state, and the queued briefs are all there.
Work brief by brief:

- `BRIEF_STUDIO2.md` — Studio enrichment (grid/axes), `ui/` only.
- `BRIEF_FIRST_PROOF.md` — the First Proof loop. The big one.

To give Codex the same two MCP tool servers Claude used, add to
`~/.codex/config.toml`:

```toml
[mcp_servers.build123d]
command = "/Users/YOU/magic-cad/.venv/bin/build123d-mcp"

[mcp_servers.magic-cad]
command = "/Users/YOU/magic-cad/.venv/bin/python"
args = ["/Users/YOU/magic-cad/mcp/magic_cad_server.py"]
```

(Adjust the paths to where you unpacked it. The MCP servers are optional —
the harness CLI is the ground truth either way.)

## 5. Claude Code instead / as well

Same folder works unchanged: Claude Code reads `CLAUDE.md`, and the
project skills under `.claude/skills/` (cad-code, Impeccable, the four
magic-* skills) come along in the package.

## Notes

- `.venv` from the old machine is NOT in the package — always recreate it
  (step 1). Never copy a venv between machines.
- `runs/` and `evals/results/` are included on purpose: they're the
  evidence trail for every verdict the harness has given.
