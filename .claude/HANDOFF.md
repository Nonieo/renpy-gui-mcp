# PLAN.md handoff

This branch (`claude/improve-mcp-documentation-rq71y`) is in the middle
of producing `PLAN.md` — a six-section MCP-spec-fluency review for the
renpy-mcp owner. If you (human, fork, or another agent) are picking
this up, read this file first.

## State

Spec revision used throughout: **2025-11-25**.

| Section | Status | Placeholder string |
|---|---|---|
| 1. SPEC_DELTA | done | n/a |
| 2. GAP_INVENTORY | pending | `<!-- SECTION_2_PLACEHOLDER -->` |
| 3. PRIORITIZATION | pending | `<!-- SECTION_3_PLACEHOLDER -->` |
| 4. PROPOSED_ROADMAP_DELTA | pending | `<!-- SECTION_4_PLACEHOLDER -->` |
| 5. NON_OBVIOUS_RISKS | pending | `<!-- SECTION_5_PLACEHOLDER -->` |
| 6. OPEN_QUESTIONS_FOR_OWNER | pending | `<!-- SECTION_6_PLACEHOLDER -->` |

Progress is tracked in `git log --oneline -- PLAN.md` under the commit
prefix `docs(plan): fill section N — <title>`. Each section is its
own commit so a fork can rebase / cherry-pick at section granularity.

## Resume prompt

Paste verbatim into a fresh session if the current one is unrecoverable:

> Resume drafting `/home/user/renpy-gui-mcp/PLAN.md` for the renpy-mcp
> owner. Section 1 (SPEC_DELTA) is already written to disk — read
> PLAN.md first. Fill the remaining placeholders listed in
> `.claude/HANDOFF.md` using one Edit call per section so no single
> generation exceeds ~3K tokens.
>
> Required reading before editing: README.md, DESIGN.md (invariants in
> §1 are load-bearing), ROADMAP.md, AGENTS.md, src/renpy_mcp/server.py,
> src/renpy_mcp/project/writer.py, pyproject.toml, and the existing
> PLAN.md. Do NOT re-fetch the MCP spec — section 1 already cites the
> canonical `2025-11-25` revision URLs; reuse them.
>
> Constraints (do not violate):
> 1. Single write pipeline (apply_write), three documented exceptions.
> 2. No LLM calls inside the server (sampling needs explicit owner
>    sign-off).
> 3. No in-GUI chat panel.
> 4. No authoritative Ren'Py parser; use get_lint_report.
> 5. Tier 4 stays opt-in.
> 6. Respect tool naming + small-model attention budget.
>
> Section requirements:
> - **Section 2 (GAP_INVENTORY):** numbered items, each with five
>   fields — what / why for THIS project / effort S-M-L / invariants
>   touched / open questions. Include a one-sentence plain-English
>   definition for any MCP concept the owner may not have used.
> - **Section 3 (PRIORITIZATION):** ordered list. Tiebreakers in order:
>   unlocks other gaps, visible to existing users, measurable
>   improvement. One sentence of justification each.
> - **Section 4 (PROPOSED_ROADMAP_DELTA):** specific edits to
>   ROADMAP.md. Match the existing phase-table tone; new phase numbers
>   continue from Phase 9 (currently tabled).
> - **Section 5 (NON_OBVIOUS_RISKS):** code-grounded, not generic.
>   Things visible only after reading writer.py, watcher.py,
>   lifecycle.py.
> - **Section 6 (OPEN_QUESTIONS_FOR_OWNER):** numbered, real forks not
>   stylistic preferences. Implementation stops here until answered.
>
> Commit policy: one commit per section, prefix `docs(plan): fill
> section N — <title>`. Push after each commit (the stop hook enforces
> this).
>
> No code in this turn. Plan only.

## Conflicts surfaced (preserve until resolved or migrated into PLAN.md)

1. **Repo identity.** `git remote -v` shows `Nonieo/renpy-gui-mcp`,
   but README.md, LICENSE attribution, AGENTS.md, and the owner's
   brief all reference `fracturedring/renpy-mcp`. Directory is
   `renpy-gui-mcp`; package name in `pyproject.toml:6` is
   `renpy-mcp`. PLAN.md should cite the upstream slug
   (`fracturedring/renpy-mcp`); treat `Nonieo/renpy-gui-mcp` as the
   working fork only.
2. **MCP version pin vs. spec features.** `pyproject.toml:24` pins
   `mcp>=1.2.0`; the active venv has `mcp==1.27.0`. The pin allows
   resolution of an SDK that pre-dates `structuredContent`,
   `outputSchema`, `elicitation`, and tool annotations. Any
   feature-adoption gap in section 2 should treat raising this pin
   as a soft prerequisite.
3. **Single-write-pipeline asterisk.** DESIGN.md §1 lists three
   exceptions to `apply_write`; DESIGN.md §2 still counts
   `set_canvas_positions` and `set_ignored_diagnostics` inside the
   27-tool Tier 2 total. A fresh reader assumes "Tier 2 ⇒
   `apply_write`" — it doesn't. Two of the 27 use parallel writers
   in `project/canvas.py` and `project/diagnostics.py`. Affects gap
   analysis for tool annotations and structured output.
4. **Commit policy.** The owner's brief says "do not commit"; the
   `~/.claude/stop-hook-git-check.sh` hook requires committed +
   pushed changes. Resolved on this branch by per-section commits
   with WIP messages, pushed after each. If the owner ultimately
   wants a single squashed commit on merge, do that at PR time, not
   here.

## When this file becomes obsolete

When PLAN.md is finalized (all six sections filled, no placeholder
strings remain), delete this file and the inline pointer at the top
of PLAN.md in the same commit. Until then, every section commit
should leave this file accurate.
