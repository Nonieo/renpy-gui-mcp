# PLAN — MCP spec-fluency review for renpy-mcp

Spec revision used throughout: **2025-11-25** (the current latest;
canonical at `https://modelcontextprotocol.io/specification/2025-11-25/`).
The TS schema lives at
`https://github.com/modelcontextprotocol/specification/blob/main/schema/2025-11-25/schema.ts`.

The repo currently pins `mcp>=1.2.0` (`pyproject.toml:24`) but the active
venv has `mcp==1.27.0`, whose `LATEST_PROTOCOL_VERSION` is `2025-11-25`.
That gap (pin vs. installed) is itself worth tightening — see Gap 12.

The repo's `build_server` (`src/renpy_mcp/server.py:23-44`) registers
only `@server.list_tools` and `@server.call_tool`, with
`NotificationOptions()` defaulting every `*_changed` flag to False. So
the negotiated `ServerCapabilities` advertises **only**
`tools: { listChanged: false }`. Every other capability discussed below
is currently absent from this server.

---

## 1. SPEC_DELTA

| Capability | Current state in repo | Spec revision (last changed) | Spec section |
|---|---|---|---|
| **tools** | **used.** 80 tools registered in `tools/registry.py`; advertised with `listChanged: false`. Each tool ships `name`, `description`, `inputSchema` (`additionalProperties: false`, explicit `required`). Returns one `TextContent` of pretty-printed JSON. | 2024-11-05 (introduced); 2025-06-18 (structuredContent, outputSchema, annotations, resource_link); 2025-11-25 (`title`, `icons`, `execution.taskSupport`, tool-name guidance, input-validation-as-tool-error clarification). | https://modelcontextprotocol.io/specification/2025-11-25/server/tools |
| **tool annotations** (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`) | **absent.** No tool sets `annotations`. `ToolDef` (`tools/registry.py:21`) has no annotations field. Tier 1 reads vs. Tier 2/3/4 mutations are conveyed by name + description only. | 2025-06-18 (introduced); 2025-11-25 (`title` field promoted to top-level Tool). | https://modelcontextprotocol.io/specification/2025-11-25/server/tools#tool |
| **structured tool output** (`outputSchema` + `structuredContent`) | **absent.** Every handler returns a single TextContent containing JSON.dumps; no `outputSchema` declared, no `structuredContent` field set. Helper is `ok()` in `tools/_shared.py:27`. | 2025-06-18 (introduced). Stable in 2025-11-25. | https://modelcontextprotocol.io/specification/2025-11-25/server/tools#structured-content |
| **resources** | **absent.** No `@server.list_resources` / `read_resources` handlers; no `ResourcesCapability` advertised. Reads happen exclusively via tools (`read_label`, `read_label_tree`, `read_raw_file`, `get_lint_report`, etc.). | 2024-11-05 (introduced); 2025-06-18 (resource_link tool content); 2025-11-25 (`icons`). | https://modelcontextprotocol.io/specification/2025-11-25/server/resources |
| **resource subscriptions** (`resources/subscribe`, `notifications/resources/updated`) | **absent.** The GUI implements its own equivalent — watchdog → asyncio queue → WebSocket fanout in `gui/backend/.../watcher.py`, with 3 s self-write suppression. Other MCP clients have no such channel. | 2024-11-05 (introduced); unchanged in 2025-11-25. | https://modelcontextprotocol.io/specification/2025-11-25/server/resources#subscriptions |
| **prompts** | **absent.** No `@server.list_prompts` / `get_prompt` handlers. The AGENTS.md happy-path is documentation only — clients can't surface it as a slash command. | 2024-11-05 (introduced); 2025-11-25 (`title`, `icons`). | https://modelcontextprotocol.io/specification/2025-11-25/server/prompts |
| **sampling** (`sampling/createMessage`, server → client LLM call) | **absent and forbidden by Invariant #2** (DESIGN.md §1: "the server never calls an LLM itself"). Spec-blessed escape hatch exists but requires owner sign-off. 2025-11-25 added `tools` + `toolChoice` to sampling, enabling multi-turn agentic loops. | 2024-11-05 (introduced); 2025-11-25 (tool-use in sampling, `sampling.tools` capability). | https://modelcontextprotocol.io/specification/2025-11-25/client/sampling |
| **elicitation** (`elicitation/create`, server → client structured input request) | **absent.** Tools that need missing input (e.g., `new_project` without a name, `add_image_alias` against a missing asset) return `err(...)` and rely on the harness/user to retry. URL mode (new in 2025-11-25) opens a non-MCP UI for sensitive flows like SDK-fetch consent. | 2025-06-18 (form mode introduced); 2025-11-25 (URL mode, default values, titled enums via SEP-1330). | https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation |
| **completions** (`completion/complete`) | **absent.** Capability requires prompts or resource templates to be useful; both absent. | 2024-11-05 (introduced); 2025-06-18 (`context.arguments` field added). | https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/completion |
| **roots** (client → server filesystem-boundary discovery) | **absent.** `ServerConfig.project_root` comes from `--project` CLI arg (or default `<cwd>/games/default/`) and is rebound by `new_project` only. Server never calls `roots/list` even though `bind_project` would be the natural reaction. | 2025-03-26 (introduced); minor edits since. Reference filesystem server uses roots to replace its `--allowed-dirs` flag at runtime (modelcontextprotocol/servers/src/filesystem). | https://modelcontextprotocol.io/specification/2025-11-25/client/roots |
| **logging** (`logging/setLevel`, `notifications/message`) | **partial.** Server uses Python `logging` (`tools/registry.py:18`, `mcp_client.py:20`, etc.) writing to stderr — clients can capture stderr per spec, but no MCP `LoggingCapability` is advertised and no structured `notifications/message` is emitted. | 2024-11-05 (introduced); 2025-11-25 clarified stderr is acceptable for any log severity (PR #670). | https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/logging |
| **progress notifications** (`notifications/progress` + request `_meta.progressToken`) | **absent.** Long-running tools — `get_lint_report`, `build_distribution`, `launch_preview`, `generate_translation_scaffolding` (all in `tools/lifecycle.py`) — block until completion and return one final response. | 2024-11-05 (introduced); 2025-11-25 added the optional `message` string field and tightened token-uniqueness rules. | https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress |
| **cancellation** (`notifications/cancelled`) | **partial / latently broken.** The low-level SDK propagates JSON-RPC cancellation to the asyncio task automatically, but `lifecycle.py` spawns subprocesses (renpy.sh for lint / build / preview) via `asyncio.create_subprocess_exec`. Cancelling the parent task does **not** kill the child unless the handler installs an explicit cleanup. So `tools/cancel` on a build leaves an orphan SDK process. | 2024-11-05 (introduced); 2025-11-25 added the `tasks/cancel` carve-out for task-augmented requests. | https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation |
| **transports — stdio** | **used.** `run_stdio()` in `server.py:48` is the only entrypoint. Spec compliant — UTF-8 messages, newline-delimited, stderr free for logging. | 2024-11-05 (introduced); 2025-11-25 clarified stderr usage. | https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#stdio |
| **transports — Streamable HTTP** | **absent.** No HTTP entrypoint. The GUI's FastAPI process talks to a *spawned* stdio renpy-mcp; it does not expose MCP over HTTP. Adding this transport opens AGPL §13 territory (see Risk 6). | 2025-03-26 (replaces deprecated HTTP+SSE); 2025-11-25 added `MCP-Protocol-Version` header MUST, Origin-403 clarification, GET-stream polling. | https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#streamable-http |
| **tasks** (experimental — `tasks/list`, `tasks/cancel`, `Tool.execution.taskSupport`) | **absent.** New in 2025-11-25, marked experimental. Would naturally fit `build_distribution` and `launch_preview`. SDK support is nascent. | 2025-11-25 (introduced, SEP-1686). | https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks |
| **authorization** (OAuth 2.1 PRM, RFC 8707) | **n/a for stdio.** Only relevant if Streamable HTTP is added. | 2025-06-18 (PRM, Resource Indicators); 2025-11-25 (OIDC discovery, incremental scope, OAuth Client ID Metadata). | https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization |
| **JSON Schema 2020-12 default** (input/output schemas) | **compatible.** Hand-written schemas use `additionalProperties: false`, `required: [...]`, `type: object` — all valid in 2020-12. None declare `$schema`, so they pick up the new default automatically. | 2025-11-25 (default dialect set to 2020-12, SEP-1613). | https://modelcontextprotocol.io/specification/2025-11-25/server/tools#data-types |

**Conflict with prior recollection.** If you've previously seen the entry
URL `https://modelcontextprotocol.io/specification` (no trailing
revision), note that during this review it returned 503; the canonical
current entry is `/specification/latest` which redirects to the
`2025-11-25` tree. Use the dated URL in code/docs to avoid silent drift.

---

## 2. GAP_INVENTORY

<!-- SECTION_2_PLACEHOLDER -->

---

## 3. PRIORITIZATION

<!-- SECTION_3_PLACEHOLDER -->

---

## 4. PROPOSED_ROADMAP_DELTA

<!-- SECTION_4_PLACEHOLDER -->

---

## 5. NON_OBVIOUS_RISKS

<!-- SECTION_5_PLACEHOLDER -->

---

## 6. OPEN_QUESTIONS_FOR_OWNER

<!-- SECTION_6_PLACEHOLDER -->
