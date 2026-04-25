# Roadmap

Forward-looking notes for renpy-mcp's evolution from "MCP server with a
GUI client" toward a Ren'Py IDE with an MCP server inside. Existing
in-flight items live in [DESIGN.md §11](DESIGN.md). This file is for the
larger directional bets.

The integration point is still the file system; the GUI grows from a
panel set into a visual development environment, but every IDE feature
that touches `.rpy` bytes still routes through `apply_write` (DESIGN.md
§3) and every reading feature still derives from `ProjectIndex`
(DESIGN.md §4). No invariant moves.

---

## Reference: Vangard / Ren'IDE

[bluemoonfoundry/bmf-vangard-renpy-ide](https://github.com/bluemoonfoundry/bmf-vangard-renpy-ide)
is an Electron + React/TS Ren'Py IDE at v0.8.0 Public Beta 4, licensed
AGPL-3.0. It treats AI as an afterthought (encrypted API key storage and
nothing else), but its analysis pipeline, three-canvas concept, visual
composers, warp flow, and watcher discipline are exactly what an IDE
*with* a first-class MCP server wants under the hood.

**License note:** This project relicensed from MIT to AGPL-3.0-or-later
to make code-level adaptation from Vangard legally clean. Track A
onward can borrow translated implementations directly without a
separate license grant; attribution to upstream files in commit
messages is still expected.

What we're learning from it, filtered through our invariants:

- The same `ProjectIndex`-shaped data feeds three different canvas views
  (file-level, label-level, player-facing); we already index that data,
  we just need to render it three ways.
- Their validator (`lib/renpyValidator.ts`) enumerates the diagnostics
  agents trip over. Each one is a Tier 1 read for us.
- Warp + drafting mode + run-as-child-process is the AI-native iteration
  loop. We have lifecycle (`launch_preview`); warp closes the rest.
- Composer panels (Scene, ImageMap, Screen Layout, Menu) are typed-tree
  → code generators. They map onto Tier 3 intents that consume the tree
  and emit one Ren'Py construct.
- Their file watcher suppresses self-writes for 3 seconds; ours
  (`watcher.py`) should do the same so agent writes don't echo as
  external changes.

---

## A. Diagnostics-as-tools (Tier 1)

`get_lint_report` calls Ren'Py itself, which is authoritative but slow
and binary (pass/fail). Vangard's canvases stay useful at zoom-out
because they surface *specific* problems via cheap, in-process rules.

Candidates, all pure reads over `ProjectIndex`:

- `find_invalid_jumps` — every `jump`/`call` whose target label doesn't
  exist in the index.
- `find_missing_assets` — `show`/`scene`/`play` references with no
  matching file under `game/images/` or `game/audio/`.
- `find_undefined_screens` — `show screen X` / `call screen X` where
  `X` is never `screen`-defined.
- `find_undefined_characters` — `c "..."` where `c` is never `define`d.
- `find_unused_characters` — defined but never spoken.
- `find_unreachable_labels` — labels with no incoming `jump`/`call`/
  fall-through edge in the route graph.

Each returns `{file, line, message, severity, rule}` rows. The agent
loop becomes: write → re-snapshot → call diagnostics → self-correct.
Don't replace `get_lint_report`; complement it. Lint is the truth, these
are the hints that get fixed before lint runs.

Suppression goes in a sidecar (`.renpy-mcp/ignored_diagnostics.json` or
similar) keyed by rule + scope, mirroring Vangard's
`IgnoredDiagnosticRule`.

## B. Warp tool + drafting mode (Tier 1 lifecycle)

`warp_to(label, overrides?)` — spawns `renpy.sh --warp <label>`, writes
a temp `_ide_after_warp.rpy` under `game/` that applies override values
in the `after_warp` hook, removes the temp file when the preview stops.
Refuses to overwrite an existing `_ide_after_warp.rpy` and detects a
user-defined `label after_warp` to avoid conflicts (Vangard's
`lib/warpAfterWarp.ts` is the spec).

This is the iteration loop's missing piece: agent writes a scene mid-
project, calls `warp_to("ch3_meet_mira", {mc_name: "Alex"})`, sees the
result without playing through.

`set_drafting_mode(on|off)` — toggles a project-local flag that injects
a fallback `image` / `audio` definition for any reference whose file is
missing, so the game runs while assets are still being generated. Lives
under `game/_ide_drafting.rpy`, removed when the flag is off. Pairs
naturally with the asset-generation harness flow described in DESIGN.md
§10.

## C. The three canvases (GUI)

Vangard's strongest UX bet. Same `ProjectIndex` data, three views:

- **Project Canvas** — `.rpy` files as draggable blocks. Edges from
  cross-file `jump`/`call`. We already have everything indexed; this is
  rendering work.
- **Flow Canvas** — every `label` is a node. Adds a graph-layer to the
  index (label-to-label edges including fall-through). Surfaces
  unreachable labels via the diagnostic above.
- **Choices Canvas** — menu nodes fan out via choice pills showing
  player-visible text + `if` guard badges.

Implementation notes:

- Native pointer events for drag (no React synthetics) — Vangard's
  performance only works because synthetic events don't run during
  drag. We should match.
- Layout off the main thread. The shape of `RenpyAnalysisResult.label
  Nodes[]` / `routeLinks[]` / `identifiedRoutes[]` from Vangard is a
  good target for what `ProjectIndex.snapshot()` could expose.
- Block positions persist to `.renpy-mcp/canvas.json`. Same sidecar
  pattern Vangard uses (`.renide/project.json`).

## D. Visual composers (Tier 3 + GUI)

Composers are typed-tree editors that generate one Ren'Py construct.
They fit Tier 3 cleanly — the existing `add_minigame_screen_scaffold`
and `create_choice_node` are the same shape.

- **Scene Composer** — layered backgrounds + sprites with per-layer
  transforms; emits `scene` / `show` statements.
- **Screen Layout Composer** — drag widgets (`vbox`, `hbox`, `frame`,
  `text`, `button`, etc.) into a tree; emits a `screen` block. The
  generator (`lib/screenCodeGenerator.ts` in Vangard) is small and
  self-contained.
- **ImageMap Composer** — draw rect hotspots over a ground image; emits
  `imagebutton` / `imagemap` screen code.
- **Menu Constructor** — choice tree with per-choice action types
  (`jump` / `call` / `pass` / `return` / inline `code`); already
  partially covered by `add_menu` + `create_choice_node`.

Each composer has two surfaces:

1. The Tier 3 tool, which accepts the tree as JSON and routes through
   `apply_write`. Agents can call this directly.
2. A GUI panel that builds the tree visually and calls the same tool.

Round-trip parsing (existing `.rpy` → tree) is harder than generation
and only worth it where the syntax is rigid enough to be safe (screens
yes; arbitrary `scene`/`show` sequences inside a label, no — that's
where Vangard's "duplicate to edit" pattern shows up).

## E. Editor-grade niceties (GUI)

The GUI currently has no Monaco. If we add one:

- Monaco with TextMate tokenization via `renpy.tmLanguage.json`
  (Vangard ships one we could borrow under license review).
- Semantic-token overlay driven by `ProjectIndex` — known/unknown
  variants for labels, characters, images, screens, variables. Unknown
  tokens are diagnostics-as-highlighting and reuse the rules from §A.
- Context-aware completions: `jump`/`call` targets, `show`/`scene`
  image tags, character tags, `screen` names, `default`/`define`
  variables.
- Inline dialogue preview — a mock textbox that updates with cursor
  position. Cheap; lots of perceived value.

This is a big lift and competes with "the harness has its own editor."
Worth it only if the GUI becomes someone's primary surface.

## F. Translation surface (Tier 1)

Vangard's `renpyTranslationParser.ts` is ~17KB but the data it produces
is simple: per-language coverage stats and per-string status (translated
/ untranslated / stale-identical-to-source).

- `get_translation_coverage()` → per-language totals and percentages.
- `find_stale_translations(language)` → strings whose translation
  matches the source verbatim.
- `generate_translation_scaffolding(language)` → wraps Ren'Py's own
  translate generation; SDK-gated.

Powers a Translation Dashboard panel in the GUI. Genuinely useful for
multi-language VN authors; cheap to ship.

## G. Watcher polish

`watcher.py` already exists. Two upgrades from Vangard's playbook:

- **Self-write suppression window** — after `apply_write` writes a
  file, the watcher ignores changes to that path for ~3 seconds. Stops
  agent writes from echoing back as "external file changed" events.
- **Reload / Keep prompt for dirty buffers** — when the GUI has a
  dirty editor on a file that changed externally, surface a persistent
  warning bar instead of clobbering. Today this matters less because
  the GUI doesn't have an editor; matters a lot once §E lands.

A `project:refresh` equivalent — manual reconcile of project state with
disk — already exists in spirit via `ProjectIndex.refresh()` but should
get an explicit Tier 1 tool (`refresh_project`) so harnesses can
trigger it after out-of-band file changes.

---

## Explicitly NOT copying from Vangard

These are tempting but break our invariants. Recording them here so the
question doesn't get re-litigated:

- **API key storage / encrypted credentials in the IDE.** The server
  doesn't call LLMs (DESIGN.md §1, non-goal #5). The harness owns
  credentials.
- **In-GUI chat panel.** Already a non-goal (DESIGN.md §1, §8). Vangard
  doesn't have one either, but agents-meet-IDE products often grow one;
  we're committed to keeping the harness as the only authoring surface.
- **Authoritative Ren'Py parser.** Vangard's analysis is also a
  pragmatic scanner, not a true parse — we're aligned. If a feature
  needs real syntactic reasoning, route it through `get_lint_report`.
- **Cosmetic surface area** — 11 themes, custom audio player with EQ
  visualization, first-run tutorial with SVG spotlights, sticky notes
  in 6 colors. All nice; none load-bearing. Pick up as time allows,
  don't sequence work around them.

---

## Rough sequencing

Ordered by ratio of agent-loop value to implementation cost:

1. **§A diagnostics tools** — pure reads, immediate harness value, no
   lifecycle changes. Each is a small Tier 1 file.
2. **§G watcher self-write suppression** — one-line config change in
   `watcher.py`, prevents a class of bugs that gets worse as the IDE
   grows.
3. **§B warp tool** — closes the iteration loop; biggest single feature
   for AI-driven authoring.
4. **§F translation reads** — small, parallelizable, useful even
   without GUI.
5. **§C Project Canvas** — uses data we already have; the simplest of
   the three canvases to land first.
6. **§C Flow + Choices Canvases** — require extending `ProjectIndex` to
   produce the label-graph + choice-pill shapes.
7. **§D composers** — start with Screen Layout (smallest generator,
   safest round-trip), then Scene, ImageMap, Menu.
8. **§E Monaco + semantic tokens** — only if the GUI becomes someone's
   primary surface.
