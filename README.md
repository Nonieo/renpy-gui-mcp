# renpy-mcp

**MCP server + browser-based VN editor for Ren'Py, designed to be driven by
agent harnesses (Claude Code, hermes-agent, Cursor) without ever touching a
`.rpy` file directly.**

Every edit flows through a single guarded write pipeline — path containment,
label uniqueness, indent normalization, atomic writes, `.rpyc` cleanup, and a
returned unified diff apply uniformly across all tools. The RPBuilder GUI is
one MCP client among many; run it alongside your LLM harness, both pointed
at the same project, and the file watcher keeps both views in sync.

> **LLM agents and fresh contributors:** start with [llms.txt](llms.txt) for
> an indexed source map, then [DESIGN.md](DESIGN.md) for the architecture,
> tier model, writer pipeline, and how to add a tool or panel safely.

---

## Install

**MCP server only** (the common case — wire it into Claude Code,
hermes-agent, Cursor, or any MCP client):

```bash
pip install git+https://github.com/fracturedring/renpy-mcp
renpy-mcp --sdk /path/to/renpy-sdk
```

`--project` is optional. When omitted, the server works against
`<cwd>/games/default/` and auto-scaffolds it on first run, so a fresh
conversation drops into a runnable starting state. Set `$RENPY_SDK`
instead of `--sdk` if you prefer. Agents should call `new_project` at
the start of a conversation to get their own named subfolder — see
[AGENTS.md](AGENTS.md) for the happy-path flow.

**With the RPBuilder GUI** (requires a repo checkout until the frontend
build ships with the wheel):

```bash
git clone https://github.com/fracturedring/renpy-mcp && cd renpy-mcp
pip install -e ".[gui]"
gui/run.sh /path/to/your/renpy/project /path/to/renpy-sdk
```

`gui/run.sh` builds the frontend on first run, then serves the SPA +
API on `http://127.0.0.1:8765/` from one FastAPI process.

---

## Features

- **44 MCP tools across 4 tiers** — read/introspection, guarded write
  primitives, high-level authoring intents (including `new_project`
  which scaffolds a runnable game in one call), and opt-in escape
  hatches. Every tool description is tuned for small-model accuracy.
- **One-sentence-prompt friendly** — `new_project` + the Tier 3 intents
  are written so a low-tier model driving this server through a harness
  (hermes-agent, Claude Code) can turn a one-line premise into a
  runnable VN. See [AGENTS.md](AGENTS.md) for the playbook.
- **Single guarded write pipeline** — every mutation (agent-driven or GUI-
  driven) routes through `apply_write`: path containment, cross-file label
  uniqueness, tab → 4-space normalization, atomic writes, `.rpyc` cleanup,
  unified diff in the response.
- **RPBuilder browser GUI** — Story Map (clickable branch graph with editable
  Scene Inspector), Characters, Assets, Variables, Build (lint runner),
  Mini-Games, Music (per-scene music picker), plus a Preview button that
  toggles `launch_preview` / `stop_preview` and polls every 2s so external
  changes from an LLM harness show up without a refresh.
- **No chat panel in the GUI** — agent interaction happens in your existing
  LLM harness pointed at the same `renpy-mcp`. The file system is the
  integration point; the watcher fans filesystem events out to every
  connected WebSocket so the GUI stays live while the LLM edits.
- **Opt-in tiers** — `--tiers 1,2,3` is the default (reads + writes +
  intents); add `4` to unlock the escape hatches when the structured tools
  can't express what you need.

---

## Wiring it into an agent harness

### Claude Code

Drop a `.mcp.json` into any directory you open Claude Code from. Claude
auto-loads it on session start and exposes the tools as
`mcp__renpy__<tool_name>` (e.g. `mcp__renpy__list_labels`). A
[`.mcp.example.json`](.mcp.example.json) ships in this repo as a starting
point:

```json
{
  "mcpServers": {
    "renpy": {
      "type": "stdio",
      "command": "/path/to/renpy-mcp/.venv/bin/python",
      "args": [
        "-m", "renpy_mcp",
        "--sdk", "/path/to/renpy-sdk"
      ]
    }
  }
}
```

Add `"--project", "/path/to/specific/project"` if you want to pin the
session to an existing project; otherwise the server scaffolds
`<cwd>/games/default/` and the agent can call `new_project` to branch
into a named subfolder.

### hermes-agent

Uses the same `.mcp.json` shape; the harness reads it from
`~/.config/hermes-agent/mcp.json` or a project-local override. Tools show
up as `mcp_renpy_<tool_name>`. If you only want the high-level authoring
surface, filter to Tier 3 via harness-level include/exclude:

```json
"tools": {
  "include": [
    "mcp_renpy_new_project",
    "mcp_renpy_get_project_overview",
    "mcp_renpy_create_scene",
    "mcp_renpy_create_choice_node",
    "mcp_renpy_create_route",
    "mcp_renpy_add_dialogue_block",
    "mcp_renpy_add_character",
    "mcp_renpy_add_image_alias",
    "mcp_renpy_swap_background",
    "mcp_renpy_set_scene_music",
    "mcp_renpy_get_lint_report",
    "mcp_renpy_launch_preview"
  ]
}
```

Or load only specific tiers at the server level: `--tiers 1,3` excludes
Tier 2 entirely so small models see fewer overlapping options.

Image generation is **not** part of this server — hermes ships a fal
image tool built in. The flow is: hermes generates the PNG and writes
it to `<project>/game/images/<name>.png`, then calls
`mcp_renpy_add_image_alias` to register it. Same pattern for audio
(drop the file into `<project>/game/audio/`; music is referenced
directly by path in `play music` / `set_scene_music`).

### Cursor and other MCP clients

Anything that speaks MCP over stdio works — point it at
`renpy-mcp --project <p> --sdk <s>` and the tools register automatically.

---

## The RPBuilder GUI

Use `gui/run.sh <project> <sdk>` for production (builds the frontend on
first run and serves the SPA + API from a single FastAPI process on port
8765) or `gui/dev.sh <project> <sdk>` for a hot-reload backend + Vite dev
server. Both require a repo checkout — see the [Install](#install)
section above.

### Two demo scenarios

**Solo authoring (no LLM).** Open the GUI, build a scene visually in the
Story Map Inspector, hit Preview to play it. Every edit goes through
`renpy-mcp` so the underlying `.rpy` stays lint-clean and writer-guarded.

**LLM-assisted.** Run the GUI in one window and your LLM harness in another,
both pointed at the same project. Ask the LLM to "make Mei more sympathetic
in the cafe scene"; the file watcher pushes the change to the GUI's
WebSocket and the Story Map plus Inspector refresh live. Conversely, edits
made in the GUI become visible to the LLM on its next `read_character`
call. No explicit coordination — the file system is the integration point.

### Panel status

| Panel | State | What it does |
|---|---|---|
| Story Map | Working | ReactFlow graph from `list_labels` + `read_label`; click a node to open the Scene Inspector |
| Scene Inspector | Working | Right-docked panel; edits background (`swap_background`), music (`set_scene_music`), and dialogue (`add_say`); flags unparsed lines so a write never silently overwrites |
| Characters | Working | Card grid + edit drawer (`add_character` / `update_character`) |
| Assets | Working | Tabbed Backgrounds / Sprites / Music / SFX from `list_images` + `list_audio`; usage-count badges |
| Variables | Working | Table view; inline edit on `default` rows (`set_variable_default`); "+ New default" modal |
| Build | Working | `get_lint_report` runner; severity-coded findings + summary cards; raw output viewer |
| Preview button | Working | Header; toggles `launch_preview` / `stop_preview`; polls every 2s so external state changes (LLM-triggered) sync without refresh |
| Mini-Games | Working | Lists scaffolded minigames (screen + label pairs); "+ New scaffold" modal calls `add_minigame_screen_scaffold` |
| Music | Working | Per-scene music table (joined from `list_audio` plays); inline edit via `set_scene_music`; music-library list; mixer stub noted |
| Animations | Stub | Deliberate — Ren'Py's ATL doesn't fit a multi-track timeline cleanly |

---

# For contributors

Everything below is for people extending this codebase — either the MCP
server, a GUI panel, or the tests. If that's not you, stop reading here;
the sections above are the complete user surface.

## Status

Alpha. **44 MCP tools**, **136 tests** passing in ~9 seconds. Nothing below
the top layer is frozen yet — the tier model, writer pipeline, and GUI
architecture are stable, but tool schemas may shift.

## Architecture at a glance

- **MCP server** (`src/renpy_mcp/`) — tiered tool registry + one guarded
  write pipeline (`apply_write` in `project/writer.py`). Every mutation
  routes through it regardless of tier.
- **Project index** (`project/scanner.py`) — pragmatic regex scanner that
  surfaces labels, characters, images, audio, screens, variables,
  transforms. Refreshed after every write.
- **Guardrails** (`guardrails/`) — indent normalization, reserved-name
  checks, label-uniqueness checks, dialogue escaping. Pure functions;
  reused across tiers.
- **RPBuilder GUI** (`gui/`) — single FastAPI process spawns its own
  `renpy-mcp` stdio subprocess plus a watchdog observer that fans
  filesystem events out to WebSocket clients. REST endpoints are thin
  wrappers around MCP tool calls.

Deep dive in [DESIGN.md](DESIGN.md).

## Tier breakdown

- **Tier 1** (default on) — 12 read-only introspection tools +
  `get_lint_report` + 3 lifecycle tools (`launch_preview`, `stop_preview`,
  `get_preview_status`). Never writes.
- **Tier 2** (default on) — 15 guarded write primitives. One Ren'Py
  construct per tool. Right layer for precise diffs.
- **Tier 3** (default on) — 11 high-level authoring intents, including
  `new_project` which scaffolds a runnable skeleton and rebinds the
  session. Composes multiple Tier 2 writes. The primary surface for agents.
- **Tier 4** (opt-in) — 2 escape hatches: `apply_unified_diff` (strict
  context-match diff applier; supports creation, refuses deletion) and
  `exec_python_in_init` (ast-validated `init python:` block appender).
  Can touch arbitrary file content — that's the point.

Configure with `--tiers 1,2,3,4` (default `1,2,3`). See §2 of
[DESIGN.md](DESIGN.md#2-the-tiered-tool-model) for how to pick a tier
when adding a tool.

## Tool naming convention

- `snake_case`; action-first for writes (`add_say`, `swap_background`),
  noun-first for reads (`list_labels`, `read_label`).
- No `renpy_` prefix — the harness already namespaces tools as
  `mcp_<server>_<tool>`. Doubling up wastes characters in tool names
  that small models have to attend to.
- Stay <=25 chars where possible.
- Descriptions are written for small-model accuracy: terse, exact,
  one-line where feasible, extra paragraphs only for non-obvious
  constraints.

## Development

```bash
git clone https://github.com/fracturedring/renpy-mcp
cd renpy-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,gui]"

# MCP server tests
pytest -q

# Frontend production build
cd gui/frontend && npm install && npm run build
```

The test suite takes ~9 seconds. Some tests (`test_gui_backend.py`,
anything calling `get_lint_report`) are module-skipped when `RENPY_SDK`
is not set — that's expected locally without the SDK; they run in full
when `RENPY_SDK` points at a Ren'Py install.

Smoke test against the fixture project:

```bash
python scripts/smoke_test.py \
  --project tests/fixtures/tiny_project \
  --sdk $RENPY_SDK
```

## Directory layout

```
src/renpy_mcp/               # the MCP server
  tools/
    tier1_read.py            # reads + lifecycle + lint (17 tools)
    tier2_write.py           # guarded write primitives (15 tools)
    tier3_intents.py         # high-level intents (10 tools)
    tier4_escape.py          # escape hatches (2 tools, opt-in)
    _shared.py               # helpers reused across tiers
    registry.py              # single dispatch point
  project/
    writer.py                # THE write pipeline — every mutation passes through
    scanner.py               # project index (labels, chars, images, …)
  guardrails/                # pure defensive helpers
  server.py                  # MCP server + tier registration
  config.py                  # ServerConfig + DEFAULT_TIERS

gui/                         # browser-based editor
  backend/src/renpy_mcp_gui/
    app.py                   # FastAPI REST + WebSocket
    mcp_client.py            # stdio MCP subprocess client
    watcher.py               # watchdog observer → WebSocket fan-out
  frontend/src/
    panels/                  # one component per left-rail panel
    api/                     # fetch wrapper + shared types
    layout/                  # Sidebar, Header
  run.sh                     # production entrypoint (builds on first run)
  dev.sh                     # hot-reload: backend + Vite dev server

tests/
  fixtures/tiny_project/     # canonical fixture — copied into tmp_path per test
  conftest.py                # FIXTURE_ROOT, SDK_ROOT, parse(), default fixtures
  test_tier1.py … test_tier4.py
  test_gui_backend.py        # SDK-gated; FastAPI TestClient end-to-end
  test_lifecycle.py          # preview spawn / stop with subprocess mocked

scripts/
  smoke_test.py              # end-to-end sanity probe

llms.txt                     # indexed source map for LLM agents
DESIGN.md                    # architecture deep-dive
README.md                    # this file
```

## Adding a new tool

Short version:

1. Pick a tier (see [DESIGN §2](DESIGN.md#2-the-tiered-tool-model)).
2. Add a `_my_tool(config, index) -> ToolDef` factory to
   `tools/tierN_*.py` with a JSON-schema `input_schema`
   (`additionalProperties: False`, explicit `required` list).
3. Build new content in the handler, then call `apply_write` via
   `write_response` from `_shared.py`. Catch `WriteRejected` and return
   `err(...)`.
4. Register the tool in the tier's `register()` function.
5. Add happy-path + rejection tests in `tests/test_tierN.py`, using the
   `workspace` fixture (copies the fixture project into `tmp_path`).
6. If the GUI should expose it, add a thin FastAPI endpoint in
   `gui/backend/src/renpy_mcp_gui/app.py` (module-scope Pydantic body
   model) and wire it into a panel.

Longer version with rationale: [DESIGN §6](DESIGN.md#6-adding-a-new-tool-step-by-step).

## Non-goals (what this repo explicitly does NOT do)

- Animations panel — Ren'Py's ATL doesn't fit a multi-track timeline.
- Chat panel inside the GUI — adding one breaks the single-integration-
  point model (the file system).
- Authoritative Ren'Py parse — `ProjectIndex` is a pragmatic scanner,
  not a parser. For true syntactic reasoning, call Ren'Py via
  `get_lint_report`.
- File deletion via `apply_unified_diff` — out of scope; will land as
  its own tool when needed.

Full rationale in [DESIGN §10](DESIGN.md#10-non-goals-what-this-repo-explicitly-does-not-do).

## License

AGPL-3.0-or-later — see [LICENSE](LICENSE).

The project relicensed from MIT to AGPL-3.0 in commit-after-`c728830` to
enable code-level adaptation from AGPL-licensed Ren'Py IDEs (notably
[bluemoonfoundry/bmf-vangard-renpy-ide](https://github.com/bluemoonfoundry/bmf-vangard-renpy-ide)).
Snapshots taken before that commit remain MIT-licensed.

**What AGPL means in practice for users:**

- Forks and modifications must stay AGPL-3.0-or-later.
- The §13 network clause applies to the GUI: anyone who runs the GUI as
  a hosted service for users beyond themselves must offer the
  corresponding source to those users.
- MCP harnesses (Claude Code, hermes-agent, Cursor) communicate with the
  server over stdio as separate processes. They are not derivative
  works of the server merely by calling its tools.
