"""Tests for Phase 1a diagnostics + refresh_project.

The fixture is intentionally lint-clean for jump targets and characters,
so every diagnostic test that needs a positive case mutates a per-test
copy of the fixture before calling the tool. This mirrors the per-test-
fixture pattern used by `test_tier2.py` and `test_phase0.py`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.label_tree import iter_statements, parse_label_body
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import tier1_read
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT, parse


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[ServerConfig, ToolRegistry, ProjectIndex]:
    """Per-test copy of the fixture so .rpy mutations don't leak."""
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    return cfg, reg, idx


# ---------- iter_statements walker ---------------------------------------------


def test_iter_statements_recurses_into_menus_and_ifs():
    body = (
        "    if x:\n"
        "        e \"in if\"\n"
        "    menu:\n"
        "        \"option\":\n"
        "            jump elsewhere\n"
        "    return\n"
    )
    tree = parse_label_body(body, body_start_line=1)
    kinds = [s["kind"] for s in iter_statements(tree["body"])]
    # Order: depth-first preorder. if → say in if → menu → jump in option → return.
    assert kinds == ["if", "say", "menu", "jump", "return"]


# ---------- find_invalid_jumps -------------------------------------------------


async def test_find_invalid_jumps_clean_fixture(registry):
    out = parse(await registry.call("find_invalid_jumps", {}))
    assert out["rule"] == "invalid_jump"
    assert out["count"] == 0
    assert out["diagnostics"] == []


async def test_find_invalid_jumps_flags_missing_target(workspace):
    cfg, reg, idx = workspace
    script = cfg.project_root / "game" / "script.rpy"
    text = script.read_text()
    # Replace the existing `jump cafe_scene` with a target that doesn't exist.
    new_text = text.replace("jump cafe_scene", "jump doesnt_exist", 1)
    script.write_text(new_text)
    idx.refresh()
    out = parse(await reg.call("find_invalid_jumps", {}))
    assert out["count"] == 1
    diag = out["diagnostics"][0]
    assert diag["rule"] == "invalid_jump"
    assert diag["severity"] == "error"
    assert diag["file"] == "game/script.rpy"
    assert diag["label"] == "start"
    assert "doesnt_exist" in diag["message"]


async def test_find_invalid_jumps_inside_if_branch(workspace):
    cfg, reg, idx = workspace
    # Add a label whose `if/else` body contains a bad jump in one branch.
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label branchy:\n"
        "    if True:\n"
        "        jump nowhere_in_particular\n"
        "    else:\n"
        "        return\n"
    )
    idx.refresh()
    out = parse(await reg.call("find_invalid_jumps", {}))
    assert out["count"] == 1
    assert out["diagnostics"][0]["label"] == "branchy"


# ---------- find_undefined_characters ------------------------------------------


async def test_find_undefined_characters_clean_fixture(registry):
    out = parse(await registry.call("find_undefined_characters", {}))
    assert out["rule"] == "undefined_character"
    assert out["count"] == 0


async def test_find_undefined_characters_flags_missing_define(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        'label ghost:\n'
        '    g "Boo, I have no define."\n'
        '    return\n'
    )
    idx.refresh()
    out = parse(await reg.call("find_undefined_characters", {}))
    assert out["count"] == 1
    diag = out["diagnostics"][0]
    assert diag["rule"] == "undefined_character"
    assert diag["severity"] == "error"
    assert diag["label"] == "ghost"
    assert "`g`" in diag["message"]


async def test_find_undefined_characters_ignores_narration(workspace):
    """Narration (no character tag) should NOT count as an undefined ref."""
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        'label narrative:\n'
        '    "Just narration here, no speaker."\n'
        '    return\n'
    )
    idx.refresh()
    out = parse(await reg.call("find_undefined_characters", {}))
    assert out["count"] == 0


# ---------- find_unused_characters ---------------------------------------------


async def test_find_unused_characters_clean_fixture(registry):
    """Both fixture characters speak, so nothing should be flagged."""
    out = parse(await registry.call("find_unused_characters", {}))
    assert out["count"] == 0


async def test_find_unused_characters_flags_silent_define(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text('define silent_one = Character("Quiet")\n')
    idx.refresh()
    out = parse(await reg.call("find_unused_characters", {}))
    names = {d["message"].split("`")[1] for d in out["diagnostics"]}
    assert "silent_one" in names
    diag = next(d for d in out["diagnostics"] if "silent_one" in d["message"])
    assert diag["severity"] == "warning"
    assert diag["file"] == "game/extra.rpy"
    assert diag["line"] == 1


# ---------- refresh_project ----------------------------------------------------


async def test_refresh_project_picks_up_external_changes(workspace):
    cfg, reg, idx = workspace
    # Take a snapshot via the index's pre-refresh count.
    before = parse(await reg.call("get_project_overview", {}))
    # Drop a new file out of band — without refreshing.
    (cfg.project_root / "game" / "extra.rpy").write_text(
        "label brand_new:\n    return\n"
    )
    # The cached snapshot still hides it.
    mid = parse(await reg.call("get_project_overview", {}))
    assert mid["counts"]["labels"] == before["counts"]["labels"]
    # refresh_project forces a re-scan.
    out = parse(await reg.call("refresh_project", {}))
    assert out["counts"]["labels"] == before["counts"]["labels"] + 1
    after = parse(await reg.call("get_project_overview", {}))
    assert "brand_new" in after["labels"]
