#!/usr/bin/env python3
"""End-to-end integration drive for the renpy-mcp tool surface.

Goal: exercise the full stack the way an LLM agent would, surface UX
friction / API surprises / unfilled corners, and confirm that an
agent-authored VN actually runs through Ren'Py's lint cleanly.

Bypasses the MCP wire and uses the in-process `ToolRegistry`. The wire
is well-covered by `test_gui_backend.py`; this script is about tool
LOGIC end-to-end.

Outputs a sectioned PASS / FINDING / FAIL report. FINDINGs are agent
ergonomics issues worth recording; FAILs are bugs.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Allow `python scripts/integration_drive.py` from project root without install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from renpy_mcp.config import ServerConfig  # noqa: E402
from renpy_mcp.project.scanner import ProjectIndex  # noqa: E402
from renpy_mcp.tools import lifecycle, tier1_read, tier2_write, tier3_intents  # noqa: E402
from renpy_mcp.tools.registry import ToolRegistry  # noqa: E402


@dataclass
class Report:
    sections: list[tuple[str, list[tuple[str, str]]]] = field(default_factory=list)

    def section(self, title: str) -> None:
        self.sections.append((title, []))

    def record(self, kind: str, msg: str) -> None:
        self.sections[-1][1].append((kind, msg))

    def total(self, kind: str) -> int:
        return sum(1 for _, items in self.sections for k, _ in items if k == kind)

    def render(self) -> str:
        lines = []
        for title, items in self.sections:
            lines.append(f"\n=== {title} ===")
            for kind, msg in items:
                lines.append(f"  {kind:8} {msg}")
        lines.append("")
        lines.append(
            f"PASS={self.total('PASS')}  "
            f"FINDING={self.total('FINDING')}  "
            f"FAIL={self.total('FAIL')}"
        )
        return "\n".join(lines)


async def call(reg: ToolRegistry, name: str, args: dict | None = None) -> dict:
    """Invoke a tool and return the parsed JSON payload."""
    contents = await reg.call(name, args or {})
    assert len(contents) == 1
    return json.loads(contents[0].text)


def make_registry(project: Path, sdk: Path) -> tuple[ServerConfig, ProjectIndex, ToolRegistry]:
    cfg = ServerConfig(project_root=project.resolve(), sdk_root=sdk.resolve())
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier2_write.register(reg, cfg, idx)
    tier3_intents.register(reg, cfg, idx)
    lifecycle.register(reg, cfg, idx)
    return cfg, idx, reg


async def step_bootstrap(reg: ToolRegistry, report: Report) -> None:
    """1) Scaffold a fresh project and verify lint."""
    report.section("1. Bootstrap (new_project + scaffold + lint)")
    # FINDING: there's no `premise` arg; agents reading the description
    # ("Scaffold a new Ren'Py project") might assume one. Stick to the
    # documented schema: just `name` (and optional display_name).
    out = await call(reg, "new_project", {"name": "test_vn"})
    if "error" in out:
        report.record("FAIL", f"new_project: {out['error']}")
        return
    report.record("PASS", f"new_project scaffolded — {out.get('summary', '<no summary>')}")

    overview = await call(reg, "get_project_overview", {})
    if overview["counts"]["labels"] >= 1:
        report.record("PASS", f"overview shows {overview['counts']['labels']} labels post-scaffold")
    else:
        report.record("FAIL", "overview shows 0 labels after new_project")

    lint = await call(reg, "get_lint_report", {})
    if lint.get("returncode") == 0:
        report.record("PASS", f"lint clean on scaffold — {lint.get('summary')}")
    else:
        report.record(
            "FINDING",
            f"lint returncode={lint.get('returncode')} on scaffold; summary={lint.get('summary')!r}",
        )


async def step_author(reg: ToolRegistry, report: Report) -> None:
    """2) Build a 3-scene branching VN using only the shipped tools."""
    report.section("2. Author 3-scene branching VN")

    # Add a character.
    out = await call(
        reg,
        "add_character",
        {"var": "alex", "display_name": "Alex", "color": "#cc6699"},
    )
    if "error" in out:
        report.record("FAIL", f"add_character: {out['error']}")
    else:
        report.record("PASS", "add_character → Alex")

    # FINDING: create_scene's `background` description claims it "must
    # already be defined or auto-named", but the handler doesn't enforce
    # this — the missing image surfaces as a lint warning later. Worth
    # tightening the description or adding the validation to match.
    # We deliberately leave `bg placeholder` undefined here so drafting
    # mode (step 4) has something to fix up.

    # Three scenes via Tier 3 create_scene. The scaffold ships a `start`
    # label already, so we author downstream scenes and rewire the start.
    # NOTE: the field is `dialogue` (not `intro_say`).
    for label in ("intro_scene", "left_path", "right_path", "merge_ending"):
        out = await call(
            reg,
            "create_scene",
            {
                "name": label,
                "background": "bg placeholder",
                "dialogue": [{"character": "alex", "text": f"You are now in {label}."}],
            },
        )
        if "error" in out:
            report.record("FAIL", f"create_scene {label}: {out['error']}")
        else:
            report.record("PASS", f"create_scene → {label}")

    # Polish intro_scene with Phase 4 events (pause, setvar, with-effect).
    for tool, args in [
        ("add_pause", {"label": "intro_scene", "duration": 0.3}),
        ("add_setvar", {"label": "intro_scene", "name": "trust", "value": 0}),
        ("add_with_effect", {"label": "intro_scene", "expression": "dissolve"}),
    ]:
        out = await call(reg, tool, args)
        if "error" in out:
            report.record("FINDING", f"{tool} on intro_scene: {out['error']}")
        else:
            report.record("PASS", f"{tool} appended")

    # Wire the intro to a menu with two branches.
    out = await call(
        reg,
        "add_menu",
        {
            "label": "intro_scene",
            "choices": [
                {"text": "Take the left path", "body": ["jump left_path"]},
                {"text": "Take the right path", "body": ["jump right_path"]},
            ],
        },
    )
    if "error" in out:
        report.record("FAIL", f"add_menu on intro_scene: {out['error']}")
    else:
        report.record("PASS", "add_menu (2 branches) → intro_scene")

    # Both paths jump to the merge ending. create_scene defaulted them to
    # `ends_with: return`, so we must pass `replace_terminator: true` to
    # rewire — exactly the friction noted in the previous run's findings.
    for src in ("left_path", "right_path"):
        out = await call(
            reg,
            "add_jump",
            {"label": src, "target": "merge_ending", "replace_terminator": True},
        )
        if "error" in out:
            report.record("FAIL", f"add_jump {src}→merge_ending: {out['error']}")
        else:
            report.record("PASS", f"add_jump {src} → merge_ending (replaced terminator)")

    # Wire the scaffold start to jump into intro_scene. The scaffold's start
    # ends with `return`, so the same replace_terminator flag is needed.
    out = await call(
        reg,
        "add_jump",
        {"label": "start", "target": "intro_scene", "replace_terminator": True},
    )
    if "error" in out:
        report.record("FAIL", f"add_jump start→intro_scene: {out['error']}")
    else:
        report.record("PASS", "add_jump start → intro_scene (replaced terminator)")

    # Verify graph reflects the wiring.
    overview = await call(reg, "get_project_overview", {})
    expected = {"start", "intro_scene", "left_path", "right_path", "merge_ending"}
    have = set(overview["labels"])
    missing = expected - have
    if missing:
        report.record("FAIL", f"graph missing labels: {missing}")
    else:
        report.record("PASS", f"all 5 expected labels present; total={len(have)}")

    choices = await call(reg, "get_choice_graph", {})
    if choices["count"] == 1 and len(choices["choices"][0]["branches"]) == 2:
        report.record("PASS", "choice graph: 1 menu × 2 branches as authored")
    else:
        report.record(
            "FINDING",
            f"choice graph mismatch: count={choices['count']}, "
            f"branches={[len(c['branches']) for c in choices['choices']]}",
        )

    # Lint after authoring.
    lint = await call(reg, "get_lint_report", {})
    if lint.get("returncode") == 0:
        report.record("PASS", f"lint clean post-authoring — {lint.get('summary')}")
    else:
        report.record(
            "FINDING",
            f"lint after authoring rc={lint.get('returncode')}; "
            f"summary={lint.get('summary')!r}",
        )


async def step_diagnose(reg: ToolRegistry, report: Report) -> None:
    """3) Force breakages and confirm find_* surfaces them."""
    report.section("3. Force diagnostics breakage")

    # Try to delete `intro_scene` — it's referenced by both `start`
    # (replaced jump) and the menu's `jump intro_scene`-style branches
    # don't exist (menu branches go to left_path/right_path). Only `start`
    # references it. Should refuse with one reference.
    out = await call(reg, "delete_label", {"label": "intro_scene"})
    if "error" in out and "still referenced" in out["error"]:
        refs = out.get("references", [])
        report.record("PASS", f"delete_label refused (good): {len(refs)} reference(s) cited")
    else:
        report.record("FAIL", f"delete_label should have refused — got: {out}")

    # Add a label with a bad jump and a bad character ref to seed diagnostics.
    out = await call(reg, "add_label", {"name": "broken_branch", "body": ["pass"]})
    if "error" in out:
        report.record("FAIL", f"add_label broken_branch: {out['error']}")
    else:
        report.record("PASS", "add_label broken_branch")

    # Add a jump with validate disabled so we can deliberately leave a dangling target.
    j = await call(
        reg,
        "add_jump",
        {
            "label": "broken_branch",
            "target": "ghost_target",
            "validate_target": False,
            "replace_terminator": True,
        },
    )
    if "error" in j:
        report.record("FAIL", f"seed dangling jump: {j['error']}")

    # NOTE: add_say validates characters at write-time (parallel to
    # add_jump's validate_target). To seed an undefined-character say
    # we'd need to bypass the writer — Tier 4's apply_unified_diff is
    # opt-in and not registered by default. We confirm the negative case
    # (no bad data → no diagnostic) below.

    diag = await call(reg, "find_invalid_jumps", {})
    if diag["count"] >= 1 and any(d["label"] == "broken_branch" for d in diag["diagnostics"]):
        report.record("PASS", f"find_invalid_jumps caught dangling jump → {diag['count']} diag(s)")
    else:
        report.record("FAIL", f"find_invalid_jumps missed broken_branch jump: {diag}")

    # find_undefined_characters can only see what made it to disk. add_say
    # validates at write-time so the natural agent path can't seed bad
    # data. Confirm the diagnostic returns clean on this project.
    diag = await call(reg, "find_undefined_characters", {})
    if diag["count"] == 0:
        report.record(
            "PASS",
            "find_undefined_characters reports clean — add_say's write-time "
            "validation prevented bad data from landing (defense in depth)",
        )
    else:
        report.record(
            "FINDING",
            f"unexpected undefined-character diagnostics: {diag['diagnostics']}",
        )

    diag = await call(reg, "find_unreachable_labels", {})
    # broken_branch isn't reached from start — should appear.
    if any(d["label"] == "broken_branch" for d in diag["diagnostics"]):
        report.record("PASS", "find_unreachable_labels caught broken_branch")
    else:
        report.record(
            "FINDING",
            f"find_unreachable_labels didn't flag broken_branch: {diag}",
        )

    # Suppress one diagnostic, confirm filter works.
    await call(
        reg,
        "set_ignored_diagnostics",
        {"entries": [{"rule": "unreachable_label", "label": "broken_branch"}]},
    )
    diag = await call(reg, "find_unreachable_labels", {})
    if not any(d["label"] == "broken_branch" for d in diag["diagnostics"]):
        report.record("PASS", f"suppression filtered broken_branch ({diag['suppressed_count']} muted)")
    else:
        report.record("FAIL", "suppression didn't filter broken_branch")

    # Now actually delete the broken label after rewiring (we'll just delete the whole thing —
    # broken_branch isn't referenced from anywhere).
    out = await call(reg, "delete_label", {"label": "broken_branch"})
    if "error" in out:
        report.record("FAIL", f"delete_label broken_branch (unreferenced): {out['error']}")
    else:
        report.record("PASS", "delete_label broken_branch (unreferenced)")


async def step_iterate(reg: ToolRegistry, report: Report, project: Path) -> None:
    """4) warp_to + set_drafting_mode iteration helpers."""
    report.section("4. Iterate (warp_to + drafting mode)")

    # Drafting mode: every reference to bg placeholder is missing in the
    # scaffold project, so flipping drafting on should produce fallbacks.
    out = await call(reg, "set_drafting_mode", {"on": True})
    if "error" in out:
        report.record("FAIL", f"set_drafting_mode on: {out['error']}")
    else:
        fallbacks = out.get("fallbacks", [])
        report.record(
            "PASS" if fallbacks else "FINDING",
            f"set_drafting_mode on → {len(fallbacks)} fallback(s): {fallbacks[:5]}",
        )

    # Verify lint stays clean with the drafting file present.
    lint = await call(reg, "get_lint_report", {})
    if lint.get("returncode") == 0:
        report.record("PASS", "lint clean with drafting fallbacks present")
    else:
        report.record(
            "FINDING",
            f"lint rc={lint.get('returncode')} after drafting on; summary={lint.get('summary')!r}",
        )

    # warp_to: dry-test by checking the temp file gets written and the
    # subprocess gets spawned. We mock the spawn by stopping immediately.
    out = await call(
        reg,
        "warp_to",
        {"label": "merge_ending", "overrides": {"trust": 5}},
    )
    if "error" in out:
        report.record("FAIL", f"warp_to merge_ending: {out['error']}")
    else:
        report.record(
            "PASS",
            f"warp_to spawned (pid={out.get('pid')}); temp_file={out.get('temp_file')}",
        )
        warp_path = project / "game" / "_ide_after_warp.rpy"
        if warp_path.is_file():
            body = warp_path.read_text()
            if "$ trust = 5" in body:
                report.record("PASS", "warp temp contains override `$ trust = 5`")
            else:
                report.record("FINDING", f"warp temp missing override; body=\n{body}")

        # Stop preview should clean the warp temp.
        stop = await call(reg, "stop_preview", {})
        if stop.get("warp_temp_removed"):
            report.record("PASS", "stop_preview removed warp temp")
        else:
            report.record(
                "FINDING",
                f"stop_preview didn't report warp_temp_removed: {stop}",
            )

    # Drafting off.
    out = await call(reg, "set_drafting_mode", {"on": False})
    if out.get("removed") and "error" not in out:
        report.record("PASS", "set_drafting_mode off → drafting file removed")
    else:
        report.record("FINDING", f"set_drafting_mode off response: {out}")


async def step_localize(reg: ToolRegistry, report: Report, project: Path) -> None:
    """5) Translation scaffold + coverage."""
    report.section("5. Localize (translation scaffolding)")

    # Generate scaffolding for spanish.
    out = await call(reg, "generate_translation_scaffolding", {"language": "spanish"})
    if "error" in out:
        report.record("FAIL", f"generate_translation_scaffolding: {out['error']}")
        return
    if out.get("returncode") != 0:
        report.record(
            "FINDING",
            f"renpy translate exit={out.get('returncode')}; stderr head: "
            f"{(out.get('stderr') or '')[:200]!r}",
        )
    else:
        report.record("PASS", "renpy translate spanish completed")

    # Coverage should now show spanish.
    cov = await call(reg, "get_translation_coverage", {})
    spanish = next((r for r in cov["languages"] if r["language"] == "spanish"), None)
    if spanish:
        report.record(
            "PASS",
            f"spanish coverage: {spanish['translated']}/{spanish['total']} ({spanish['percent']}%)",
        )
        if spanish["percent"] == 100.0:
            report.record(
                "FINDING",
                "spanish at 100% from scaffolding alone — find_stale_translations may be lenient",
            )
    else:
        report.record("FAIL", "coverage didn't show spanish after scaffolding")

    # Stale list should match the stale count in coverage.
    stale = await call(reg, "find_stale_translations", {"language": "spanish"})
    if spanish and stale["count"] == spanish["stale"]:
        report.record("PASS", f"stale count matches coverage ({stale['count']} entries)")
    elif spanish:
        report.record(
            "FINDING",
            f"stale count mismatch: stale={stale['count']} vs coverage.stale={spanish['stale']}",
        )


async def step_ship(reg: ToolRegistry, report: Report, project: Path) -> None:
    """6) build_distribution → real artifact on disk."""
    report.section("6. Ship (build_distribution)")

    out = await call(reg, "build_distribution", {"targets": ["pc"]})
    if "error" in out:
        report.record("FAIL", f"build_distribution: {out['error']}")
        return
    if out.get("returncode") != 0:
        stderr_head = (out.get("stderr") or "")[:300]
        report.record(
            "FINDING",
            f"distribute exit={out.get('returncode')}; stderr head: {stderr_head!r}",
        )
    else:
        report.record("PASS", "renpy distribute --packages=pc completed")

    # Ren'Py's distribute writes to `<project.parent>/<project>-<version>-dists/`.
    # Walk that pattern and any other reasonable spot.
    found: list[Path] = []
    for candidate in project.parent.iterdir() if project.parent.is_dir() else []:
        if candidate.is_dir() and candidate.name.endswith("-dists"):
            for child in candidate.iterdir():
                if child.suffix.lower() in (".zip", ".bz2"):
                    found.append(child)
    if found:
        report.record("PASS", f"distribute artifact(s): {[p.name for p in found]}")
    else:
        report.record(
            "FINDING",
            "distribute produced no artifact in expected dirs "
            "(<project.parent>/<name>-<version>-dists/); worth confirming.",
        )


async def step_gui_sanity(reg: ToolRegistry, report: Report) -> None:
    """7) Read-tool sanity: confirm the data the GUI panels would render."""
    report.section("7. GUI-side data sanity")

    overview = await call(reg, "get_project_overview", {})
    report.record(
        "PASS",
        f"overview: {overview['counts']['labels']} labels, "
        f"{overview['counts']['characters']} chars, "
        f"{overview['counts']['screens']} screens",
    )

    # Tree read for the inspector.
    tree = await call(reg, "read_label_tree", {"name": "intro_scene"})
    body = tree.get("body", [])
    if body:
        kinds = [n["kind"] for n in body]
        report.record("PASS", f"intro_scene tree body kinds: {kinds}")
    else:
        report.record("FINDING", f"intro_scene tree empty body: {tree}")

    # Choice graph for Choice View.
    choices = await call(reg, "get_choice_graph", {})
    report.record("PASS", f"choice graph: {choices['count']} menu(s)")

    # Canvas positions should be empty on a fresh project.
    pos = await call(reg, "read_canvas_positions", {})
    report.record(
        "PASS" if pos["count"] == 0 else "FINDING",
        f"canvas positions: {pos['count']} entries (expected 0 on fresh project)",
    )


async def main() -> int:
    sdk_root = Path(os.environ.get("RENPY_SDK", str(Path.home() / "renpy-sdk")))
    if not (sdk_root / "renpy.sh").is_file():
        print(f"FATAL: no renpy.sh at {sdk_root}/renpy.sh — set RENPY_SDK.")
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="renpy_mcp_drive_"))
    print(f"working dir: {workdir}\n")
    try:
        # Pre-scaffold a parent dir; new_project will create test_vn/ inside.
        # ServerConfig needs a valid project root at construction time, so
        # we point it at a placeholder we'll immediately rebind via new_project.
        placeholder = workdir / "placeholder"
        (placeholder / "game").mkdir(parents=True)
        (placeholder / "game" / "script.rpy").write_text("label start:\n    return\n")

        cfg, idx, reg = make_registry(placeholder, sdk_root)
        # new_project will rebind cfg.project_root to <workdir>/games/test_vn/

        report = Report()
        await step_bootstrap(reg, report)
        await step_author(reg, report)
        await step_diagnose(reg, report)
        await step_iterate(reg, report, cfg.project_root)
        await step_localize(reg, report, cfg.project_root)
        await step_ship(reg, report, cfg.project_root)
        await step_gui_sanity(reg, report)

        print(report.render())
        print(f"\nproject left at: {cfg.project_root}")
        print(f"workdir:         {workdir}")
        return 0 if report.total("FAIL") == 0 else 1
    except Exception as exc:
        import traceback

        print("UNHANDLED EXCEPTION:")
        traceback.print_exc()
        print(f"\nworkdir: {workdir}")
        return 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
