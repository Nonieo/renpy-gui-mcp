# renpy-mcp

MCP server that exposes Ren'Py visual novel development as a tiered set of
structured tools, designed for agent harnesses (hermes-agent, Claude Code).

## Status

Alpha. **43 MCP tools** across four tiers, **123 tests** passing. The
RPBuilder GUI ships five working panels (Story Map with editable Scene
Inspector, Characters, Assets, Variables, Build) plus a working Preview
button.

## Quickstart

```bash
git clone <this-repo> renpy-mcp
cd renpy-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# point it at the fixture project for development
renpy-mcp --project tests/fixtures/tiny_project --sdk /path/to/renpy-sdk
```

The server speaks MCP over stdio. After install, run the smoke test to confirm
the wiring is sound:

```bash
python scripts/smoke_test.py --project tests/fixtures/tiny_project --sdk /path/to/renpy-sdk
```

## Wiring it into Claude Code

Drop a `.mcp.json` into any directory you open Claude Code from. Claude auto-
loads it on session start and exposes the tools as `mcp__renpy__<tool_name>`
(e.g. `mcp__renpy__list_labels`).

```json
{
  "mcpServers": {
    "renpy": {
      "type": "stdio",
      "command": "/path/to/renpy-mcp/.venv/bin/python",
      "args": [
        "-m", "renpy_mcp",
        "--project", "/path/to/your/renpy/project",
        "--sdk", "/path/to/renpy-sdk"
      ]
    }
  }
}
```

A `.mcp.example.json` ships in this repo as a starting point.

## Wiring it into hermes-agent

Hermes-agent reads MCP servers from its own config (typically
`~/.config/hermes-agent/mcp.json` or a project-local override). Use the
same shape as `.mcp.json` above; hermes will prefix tools as
`mcp_renpy_<tool_name>`. Filter tiers via the harness's
`tools.include` / `tools.exclude` if you want to load only the high-level
intents:

```json
"tools": {
  "include": [
    "mcp_renpy_get_project_overview",
    "mcp_renpy_list_labels",
    "mcp_renpy_create_scene",
    "mcp_renpy_create_choice_node",
    "mcp_renpy_add_dialogue_block",
    "mcp_renpy_swap_background",
    "mcp_renpy_set_scene_music",
    "mcp_renpy_get_lint_report"
  ]
}
```

Or load only specific tiers at the server level: `--tiers 1,3` excludes
the Tier 2 primitives entirely.

## Tool naming convention

- `snake_case`, action-first for writes (`add_say`, `swap_background`),
  noun-first for reads (`list_labels`, `read_label`).
- No `renpy_` prefix — the harness already namespaces tools as
  `mcp_<server>_<tool>`. Doubling up wastes characters in tool names that
  small models have to attend to.
- Names stay <=25 chars where possible.

## Tiers

- **Tier 1** — 13 read-only introspection tools + 3 lifecycle tools
  (`launch_preview`, `stop_preview`, `get_preview_status`) + `get_lint_report`.
- **Tier 2** — 15 guarded write primitives (one statement per tool).
- **Tier 3** — 10 high-level intents (one creator action per tool).
- **Tier 4** — 2 escape hatches: `apply_unified_diff` (strict context-match
  patcher; supports creation via `--- /dev/null`, refuses deletion) and
  `exec_python_in_init` (ast-validated `init python:` block appender).

Configure which tiers load via `--tiers 1,2,3,4` (default: 1,2,3; Tier 4
is opt-in because the escape hatches can touch arbitrary file content).
Tool descriptions are written for small-model accuracy; the convention is
documented above.

## RPBuilder GUI

A browser-based visual VN editor (`gui/`) sits on top of the same MCP
server. **No chat panel** — agent interaction happens in your existing LLM
harness pointed at the same `renpy-mcp` server. The GUI is one MCP client
among many; the file system is the integration point.

### Run

```bash
pip install -e ".[gui]"

# production: serves the built frontend from the same Python process
gui/run.sh /path/to/your/renpy/project /path/to/renpy-sdk

# dev: hot-reload backend + Vite dev server
gui/dev.sh /path/to/your/renpy/project /path/to/renpy-sdk
```

`run.sh` builds the frontend on first run if `gui/frontend/dist/` is missing.
After startup it opens `http://127.0.0.1:8765/` in your browser.

### Panel status

| Panel | State | Notes |
|---|---|---|
| Story Map | Working | ReactFlow graph from `list_labels` + `read_label`; click a node to open the Scene Inspector |
| Scene Inspector | Working | Side panel; edits background (`swap_background`), music (`set_scene_music`), and dialogue (`add_say`); flags unparsed lines |
| Characters | Working | Card grid + edit drawer (`add_character` / `update_character`) |
| Assets | Working | Tabbed Backgrounds / Sprites / Music / SFX from `list_images` + `list_audio`; usage-count badges |
| Variables | Working | Table view; inline edit on `default` rows (`set_variable_default`); "+ New default" modal |
| Build | Working | `get_lint_report` runner; severity-coded findings + summary cards; raw output viewer |
| Preview button | Working | Header; toggles `launch_preview` / `stop_preview`; polls every 2s so external state changes (LLM-triggered) sync without refresh |
| Animations | Stub | Ren'Py's ATL doesn't fit a multi-track timeline cleanly |
| Mini-Games | Working | Lists scaffolded minigames (screen+label pairs); "+ New scaffold" modal calls `add_minigame_screen_scaffold` |
| Music | Working | Per-scene music table (joined from `list_audio` plays); inline edit via `set_scene_music`; music-library list; mixer stub noted |

### Two demo scenarios

**Solo authoring (no LLM):** Open the GUI, build a scene visually in the
Story Map's Inspector, hit Preview to play it. Every edit goes through
`renpy-mcp` so the underlying `.rpy` is always lint-clean and writer-guarded.

**LLM-assisted:** Run the GUI in one window and Claude Code (or
hermes-agent / Cursor) in another, both pointed at the same project + the
same `renpy-mcp` server config. Ask the LLM to "make Mei more sympathetic
in the cafe scene"; the file watcher pushes the change to the GUI's
WebSocket; the Story Map and Inspector refresh live without you touching
the browser. Conversely, character edits you make in the GUI become
visible to the LLM on its next `read_character` call.

### Architecture

```
  Browser
    │ HTTP + WebSocket
  FastAPI (gui/backend) ──── watchdog ── game/*.rpy *.png *.ogg
    │ stdio + MCP                           ▲
  renpy-mcp subprocess  ───────────────────┐│
    │ subprocess.run                       ││
  renpy.sh / renpy.exe                     ││
                                            │
  Other MCP clients (Claude Code, hermes-agent, Cursor)
   ─── their own renpy-mcp subprocess ────┘
```

The GUI's backend spawns its own `renpy-mcp`; LLM harnesses spawn theirs.
Both clients see the same files — coordination is implicit through the
file system, watcher, and writer guardrails.

### Wireframe roots

The panel layout follows the RPBuilder wireframes (left rail with eight
sections, right-docked Scene Inspector, top bar with Preview + Export).
The wireframes' Animations panel was deliberately not built — Ren'Py's
ATL is procedural enough that a multi-track timeline misrepresents how
animations are actually authored.
