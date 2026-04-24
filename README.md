# renpy-mcp

MCP server that exposes Ren'Py visual novel development as a tiered set of
structured tools, designed for agent harnesses (hermes-agent, Claude Code).

## Status

Pre-alpha. Milestone 1 (scaffold + Tier 1 read tools) in progress.

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

- **Tier 1** — read-only project introspection.
- **Tier 2** — guarded write primitives (one statement per tool).
- **Tier 3** — high-level intents (one creator action per tool).
- **Tier 4** — escape hatches (raw diff apply, init-python exec) — opt-in.

Configure which tiers load via `--tiers 1,2,3` (default: all but Tier 4).
