# Roadmap

Forward-looking notes for renpy-mcp's evolution from "MCP server with a
GUI client" toward a Ren'Py IDE with an MCP server inside. In-flight,
non-directional items live in [DESIGN.md §11](DESIGN.md). This file is
for the larger directional bets and the GUI-integration sequencing.

## Status as of 2026-04-24

| Phase | What | Status |
|---|---|---|
| 0  | `read_label_tree` + canvas-positions sidecar | **shipped** |
| 1a | Diagnostic foundation (invalid jumps, undefined/unused chars, refresh_project) | **shipped** |
| 1b | Asset/screen/reachability diagnostics + ignored-diagnostics suppression | **shipped** |
| 1c | Watcher self-write suppression (mark_self_write + response observer) | **shipped** |
| 2  | Themed shell (theme tokens, sidebar variants, Prefs modal, ⌘K palette) | **shipped** |
| 3a | View-only Story Map port (drop react-flow, native pointer events) | **shipped** |
| 3b | Editable Story Map (drag-to-rearrange, port-drag connect, toolbar + delete) | **shipped** |
| 4  | Inspector tree migration + 5 event tools (pause, setvar, show, with-effect, flash) | **shipped** |
| 5  | `warp_to` + `set_drafting_mode` (closes the iteration loop) | **shipped** |
| 6  | Choice View derived filter (`get_choice_graph` + panel) | **shipped** |
| 7  | Composers — Screen Layout, Stage, ImageMap, Menu | **shipped** |
| 8  | Translation surface + `build_distribution` | **shipped** |
| 9  | Monaco editor + semantic tokens | **tabled** (only worth it if the GUI becomes someone's primary surface) |

End-to-end validation lives at `scripts/integration_drive.py` (40-step
in-process drive) and `scripts/real_vn_drive.py` (drives a project that
ships real fal-generated assets all the way to a `<name>-<version>-pc.zip`
artifact with the assets baked in). 74 tools, 292 tests, no FAILs.

The phase descriptions below are kept verbatim as the "why we built it
this way" record. Detailed implementation notes have been transferred
into [README.md](README.md) (panel status table, tier breakdown) and
[DESIGN.md](DESIGN.md) (writer-pipeline exceptions, architecture).

The integration point is still the file system; the GUI grows from a
panel set into a visual development environment, but every IDE feature
that touches `.rpy` bytes still routes through `apply_write` (DESIGN.md
§3) and every reading feature still derives from `ProjectIndex`
(DESIGN.md §4). No invariant moves.

This project is **agent-driven first**. Surfaces, panels, and tool names
are sequenced and named so a model forms one coherent mental model of
the system without disambiguating overlapping concepts. When two tools
or two views would cover the same data, default to one canonical
surface plus a derived filter — not parallel views.

---

## Reference: Vangard / Ren'IDE

[bluemoonfoundry/bmf-vangard-renpy-ide](https://github.com/bluemoonfoundry/bmf-vangard-renpy-ide)
is an Electron + React/TS Ren'Py IDE at v0.8.0 Public Beta 4, licensed
AGPL-3.0. It treats AI as an afterthought (encrypted API key storage and
nothing else), but its analysis pipeline, editable graph, visual
composers, warp flow, and watcher discipline are exactly what an IDE
*with* a first-class MCP server wants under the hood.

**License note:** This project relicensed from MIT to AGPL-3.0-or-later
to make code-level adaptation from Vangard legally clean. Phase 1
onward can borrow translated implementations directly without a
separate license grant; attribution to upstream files in commit
messages is still expected.

What we're learning from it, filtered through our invariants:

- The same `ProjectIndex`-shaped data feeds the editable graph (label
  nodes with kind badges) and a player-facing menu walkthrough; we
  already index that data, we just need to render it two ways.
- Their validator (`lib/renpyValidator.ts`) enumerates the diagnostics
  agents trip over. Each one is a Phase 1 read for us.
- Warp + drafting mode + run-as-child-process is the AI-native iteration
  loop. We have lifecycle (`launch_preview`); warp closes the rest.
- Composer panels (Scene, ImageMap, Screen Layout, Menu) are typed-tree
  → code generators. They map onto Tier 3 intents that consume the tree
  and emit one Ren'Py construct.
- Their file watcher suppresses self-writes for 3 seconds; ours
  (`watcher.py`) should do the same so agent writes don't echo as
  external changes.

**Vangard has three canvases (project / flow / choices). We collapse to
two surfaces:** Story Map (one node per label, kind badges, editable,
positions persist) and Choice View (derived filter walked from `menu`
nodes outward, player perspective). One agent-facing concept for the
graph, one specialized derivation. A file-level zoom-out can land later
as a rendering mode of Story Map if anyone asks; it is not load-bearing.

---

## Polished UI integration: where we're heading

`/home/alex/gameshop/renpy-gui/` holds a self-contained mock-data
prototype showing the eventual editor: themed shell (light/cream/dark ×
six accents), Sidebar variants (icon/labeled/palette), Preferences
modal, fully editable Story Map with port-drag-to-connect, an Inspector
with typed events (`say`, `show`, `play`, `pause`, `with` effect,
`flash`, `$ setvar`), tabbed Character detail, Build panel with
per-platform distribute targets. The current shipping frontend
(`gui/frontend/`) is a Tailwind/React-Flow SPA wired to real MCP tools.

The polished design **is** the IDE surface; the Vangard bets below are
the backend plumbing that makes it load-bearing. The phases sequence
both at once.

### Final UI layout (target)

- **Shell** — left rail (variant: icon/labeled/palette), top header
  (project breadcrumbs, watcher pill, preview toggle, drafting toggle,
  appearance gear), center workspace, right-dock Scene Inspector when
  a node is selected. Overlays: Preferences modal, ⌘K command palette.
- **Story Map** (canonical graph) — one node per `label`, kind badge
  (start/scene/choice/ending) inferred from structure, draggable, ports
  editable, positions persist to `.renpy-mcp/canvas.json`. **Default
  workspace.**
- **Choice View** — derived filter of the same graph walked from
  `menu` nodes; renders choice pills + `if`-guard badges. Read-mostly.
- **Characters** — roster + tabbed detail (Identity · Voice · Sprites
  · Appearances).
- **Assets** — Backgrounds / Sprites / Music / SFX tabs with usage
  counts and an upload tile.
- **Variables** — table; inline-edit on `default`; new-default modal.
- **Music** — per-label music assignments + library list.
- **Mini-Games** — screen+label pair list; scaffold modal.
- **Build** — lint summary cards + Distribute (per-platform) + raw
  output pane.
- **Languages** (lands in Phase 8) — translation coverage + stale
  strings.

### Naming scrub (kept consistent across phases)

- The structured-tree read of a label is `read_label_tree` — pairs
  with existing `read_label` (raw source). Avoids overloading Ren'Py's
  `scene` keyword.
- New write primitives keep the `add_*` shape (`add_show`, `add_pause`,
  `add_with_effect`, `add_flash`, `add_setvar`).
- New diagnostics keep the `find_*` shape (Phase 1).
- Sidecar metadata uses `read_*_positions` / `set_*_positions` pairs
  so authors and agents see the read/write asymmetry without guessing.

---

## Phases

Each phase is independently shippable and split where the user agreed
multistep delivery makes sense. Phases that touch the same backend
surface stay clustered so an agent can land them serially without
context churn.

### Phase 0 — Foundation (load-bearing for Phases 3–7)

- **`read_label_tree(name)`** (Tier 1). Returns a typed tree:
  `background`, `music`, `shows[]`, `says[]`, `menus[]`, `jumps[]`,
  `calls[]`, `conditions[]`, `sets[]`, `plays[]`, `pauses[]`,
  `ends_with_return`, `unparsed[]` (with `{line, raw}` for anything
  the structured parser refused to interpret). Becomes the canonical
  shape the GUI Inspector consumes; the frontend's `parseLabel.ts`
  retires once the Inspector is wired.
- **`read_canvas_positions()`** (Tier 1) and
  **`set_canvas_positions(positions)`** (Tier 2). Backed by
  `.renpy-mcp/canvas.json` in the project root. Per-label `{x, y}`
  records. The sidecar is GUI metadata, not a `.rpy` change, so the
  set tool stays atomic + path-contained but does not route through
  `apply_write` (no diff, no `.rpyc` cleanup, no label-uniqueness
  check — there are no labels in the sidecar). Documented as the only
  exception alongside `new_project` in DESIGN §3.

### Phase 1 — Diagnostics-as-tools + watcher polish (Vangard §A + §G)

`get_lint_report` calls Ren'Py itself, which is authoritative but slow
and binary. Cheap in-process rules complement it.

- `find_invalid_jumps` — every `jump`/`call` whose target label
  doesn't exist in the index.
- `find_missing_assets` — `show`/`scene`/`play` references with no
  matching file under `game/images/` or `game/audio/`.
- `find_undefined_screens` — `show screen X` / `call screen X` where
  `X` is never `screen`-defined.
- `find_undefined_characters` — `c "..."` where `c` is never `define`d.
- `find_unused_characters` — defined but never spoken.
- `find_unreachable_labels` — labels with no incoming
  `jump`/`call`/fall-through edge.

Each returns `{file, line, message, severity, rule}` rows. The agent
loop becomes: write → re-snapshot → call diagnostics → self-correct.
Don't replace `get_lint_report`; complement it.

Suppression goes in `.renpy-mcp/ignored_diagnostics.json` keyed by
rule + scope, mirroring Vangard's `IgnoredDiagnosticRule`.

Watcher polish:

- **Self-write suppression window** — after `apply_write` writes a
  file, `watcher.py` ignores changes to that path for ~3 seconds.
  Stops agent writes from echoing back as "external file changed".
- **`refresh_project`** — explicit Tier 1 tool wrapping
  `ProjectIndex.refresh()` so harnesses can trigger it after
  out-of-band file changes.

### Phase 2 — Polished shell (pure frontend port, no backend changes)

Theming path: **Tailwind + CSS variables**. Don't rip out Tailwind —
use it for layout, CSS vars for theming. Theme tokens (cream/light/
dark, six accents) live in a single `theme.css` layer driven by
`document.documentElement.dataset.theme` / `data-rail`, ported from
`renpy-gui/styles.css`.

- Sidebar variants (`icon` / `labeled` / `palette`) + brand block.
- Preferences modal (theme, accent, density, rail).
- Header: watcher activity pill, preview toggle (already exists),
  drafting-mode toggle (placeholder until Phase 5), appearance gear.
- ⌘K command palette overlay — jumps between panels and labels.
- Persist preferences in `localStorage` under one key.

### Phase 3 — Story Map upgrade (Vangard §C, split per user direction)

#### 3a — View-only port

Replace react-flow + dagre with the renpy-gui port-based renderer,
ported to TypeScript and using **native pointer events** (not React
synthetics — Vangard's perf note: synthetic events kill drag
performance). Same data the current Story Map already pulls from
`/api/graph`; node positions come from `read_canvas_positions` with a
deterministic fallback layout for any label without a stored position.
Kind badges (start/scene/choice/ending) inferred from each label's
`read_label_tree` shape. No editing yet — clicks open the Inspector,
drag pans the canvas.

#### 3b — Editable port-drag

Wire the editor surfaces to real tools. Some are existing, some land
in this phase as new Tier 2 primitives:

- Add linear edge → `add_jump` (exists).
- Add menu branch → **`add_menu_branch`** (new Tier 2; appends a
  branch to an existing `menu:` block).
- Redirect edge → **`redirect_jump`** (new Tier 2; rewrites a
  specific `jump <old>` to `jump <new>` at a known source line).
- Add scene/choice/ending node → `add_label` (exists), then for
  choice nodes `add_menu` (exists), for endings the body is just
  `return`.
- Delete node → **`delete_label`** (new Tier 2; refuses if any
  diagnostic in Phase 1 still references it, surfaces those references
  in the error response so the agent can fix them first).
- Drag positions → batched `set_canvas_positions` with debounce.

Story Map nodes display Phase 1 diagnostic badges and a watcher-driven
recent-edit glow.

### Phase 4 — Scene Inspector upgrade (Vangard §D, ships per-event)

Per user direction, event tools land **one at a time** with their
Inspector wiring. Each is a separate, independently shippable PR-shape.
Order is "smallest body diff first" so the wiring pattern stabilizes
on simple cases:

1. `add_pause` (one line: `pause <dur>`).
2. `add_setvar` (one line: `$ name = value` inside a label;
   semantically distinct from existing `set_variable_default` which
   writes top-level `default x = …`).
3. `add_show` (covers move + emote: `show <tag> [expr] at <pos> with
   <transition>`).
4. `add_with_effect` (`with hpunch` / `vpunch` / named transition).
5. `add_flash` (color overlay for a duration; emits
   `show expression Solid("#xxx") with Dissolve(...)` then restores).
6. `say` (already shipped as `add_say`).
7. `play` (already shipped as `add_audio_play`).

Reordering events within a label is **not** a per-event tool. It lands
in Phase 4.5 as `reorder_label_block(name, source_line, target_line)`
or, if that proves too narrow, as a Tier 4 escape via
`apply_unified_diff`. Decide once Phases 4.1–4.5 have shaped the
typical reorder pattern.

### Phase 5 — Warp + drafting mode (Vangard §B)

- `warp_to(label, overrides?)` — spawns `renpy.sh --warp <label>`,
  writes a temp `_ide_after_warp.rpy` under `game/` that applies
  override values in the `after_warp` hook, removes the temp file
  when the preview stops. Refuses to overwrite an existing
  `_ide_after_warp.rpy`. Detects user-defined `label after_warp` and
  refuses rather than collide. Vangard's `lib/warpAfterWarp.ts` is
  the spec.
- `set_drafting_mode(on|off)` — toggles a project-local flag that
  injects fallback `image` / `audio` definitions for any reference
  whose file is missing, so the game runs while assets are still
  being generated. Lives under `game/_ide_drafting.rpy`, removed when
  off. Pairs naturally with the asset-generation flow described in
  DESIGN.md §10.

GUI wiring: per-node "Warp here" action; header drafting-mode toggle
goes live (replaces the Phase 2 placeholder).

### Phase 6 — Choice View (the second canvas — derived filter)

`ProjectIndex` extension to emit menu-pill data:
`{label, choices: [{text, condition?, target}]}`. The Choice View
panel walks the graph from `menu` nodes outward, sharing the canvas
positions and the Phase 3 node editor core. Read-mostly: clicking a
choice pill opens the target label in the Inspector; redirecting a
target uses Phase 3's `redirect_jump`.

### Phase 7 — Composers (Vangard §D)

Order, smallest/safest generator first:

1. **Screen Layout Composer** — drag widgets (`vbox`, `hbox`, `frame`,
   `text`, `button`, …) into a tree; emits a `screen` block. Vangard's
   `lib/screenCodeGenerator.ts` is small and self-contained.
2. **Scene Composer** — layered backgrounds + sprites with per-layer
   transforms; emits `scene` / `show` statements.
3. **ImageMap Composer** — draw rect hotspots over a ground image;
   emits `imagebutton` / `imagemap` screen code.
4. **Menu Composer** — choice tree with per-choice action types
   (`jump` / `call` / `pass` / `return` / inline `code`); subsumes
   the existing `add_menu` + `create_choice_node` for visual authoring.

Each composer ships as a Tier 3 tool that accepts the tree as JSON +
a GUI panel that builds the tree visually and calls that tool. Round-
trip parsing (existing `.rpy` → tree) is harder than generation and
only worth it where the syntax is rigid enough to be safe (screens
yes; arbitrary `scene`/`show` sequences inside a label, no — that's
where Vangard's "duplicate to edit" pattern shows up).

### Phase 8 — Translation surface + Build distribute

Vangard's `renpyTranslationParser.ts` produces simple data: per-
language coverage stats and per-string status. We mirror it as Tier 1
reads:

- `get_translation_coverage()` → per-language totals and percentages.
- `find_stale_translations(language)` → strings whose translation
  matches the source verbatim.
- `generate_translation_scaffolding(language)` — wraps Ren'Py's own
  translate generation; SDK-gated.

Plus the long-asked Build panel completion:

- `build_distribution(targets)` — wraps `renpy.sh distribute`.

Languages panel goes live; Build panel's Distribute tile gets wired.

### Phase 9 (tabled) — Monaco + semantic tokens (Vangard §E)

Only worth it if the GUI becomes someone's primary authoring surface.
Tabled until a user explicitly asks for it.

---

## Explicitly NOT copying from Vangard

Recording these here so the question doesn't get re-litigated:

- **API key storage / encrypted credentials in the IDE.** The server
  doesn't call LLMs (DESIGN.md §1, non-goal #5). The harness owns
  credentials.
- **In-GUI chat panel.** Already a non-goal (DESIGN.md §1, §8). Vangard
  doesn't have one either, but agents-meet-IDE products often grow one;
  we're committed to keeping the harness as the only authoring surface.
- **Authoritative Ren'Py parser.** Vangard's analysis is also a
  pragmatic scanner, not a true parse — we're aligned. If a feature
  needs real syntactic reasoning, route it through `get_lint_report`.
- **Three parallel canvases (project / flow / choices).** Collapsed to
  Story Map + Choice View per the consistent-understanding rule above.
- **Cosmetic surface area** — 11 themes, custom audio player with EQ
  visualization, first-run tutorial with SVG spotlights, sticky notes
  in 6 colors. Pick up as time allows; don't sequence work around them.

---

## Sequencing summary (as delivered)

Phases shipped in this order:

1. **Phase 0** — `read_label_tree` + canvas-positions sidecar.
2. **Phase 1a/1b/1c** — diagnostics, suppression sidecar, watcher
   self-write suppression.
3. **Phase 2** — polished shell (theme tokens + Sidebar variants +
   Prefs modal + ⌘K palette).
4. **Phase 5** — warp + drafting (closes the AI iteration loop).
5. **Phase 3a** — view-only Story Map port.
6. **Phase 3b** — editable Story Map (`add_menu_branch`,
   `redirect_jump`, `delete_label`).
7. **Phase 4** — Inspector tree migration + 5 event tools (`add_pause`,
   `add_setvar`, `add_show`, `add_with_effect`, `add_flash`).
8. **Phase 6** — Choice View derived filter (`get_choice_graph`).
9. **Phase 8** — translation surface + `build_distribution`.
10. **Phase 7** — Screen Layout composer, then Stage / ImageMap / Menu
    composers in one push.

Two integration tests caught all the bugs that surface only end-to-end
(`build_distribution` argv shape, scaffold leaving `build.name = "gui"`,
slug-safe `build.directory_name`). They live at
`scripts/integration_drive.py` and `scripts/real_vn_drive.py`.

**Phase 9 (Monaco editor)** stays tabled. Pick up when there's a real
authoring user who treats the GUI as their primary surface.
