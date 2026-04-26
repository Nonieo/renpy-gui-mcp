"""Tests for the `get_scaffold_status` Tier 1 tool.

Goal: confirm the heuristic correctly classifies the four common
scaffold states an agent passes through:

1. Fresh `new_project` output — empty `label start: return`.
2. Authored an opening, but forgot `set_start_target` — the high-impact
   gap the test in 9cf035d was meant to catch.
3. Wired correctly — start jumps to an existing label.
4. SDK placeholder dialogue still present (older project that pre-dates
   the script.rpy overwrite).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import tier1_read, tier2_write, tier3_intents
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT, parse


@pytest.fixture
def workspace(tmp_path: Path):
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(
        project_root=proj.resolve(),
        sdk_root=SDK_ROOT,
        games_root=tmp_path.resolve(),
    )
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier2_write.register(reg, cfg, idx)
    tier3_intents.register(reg, cfg, idx)
    return cfg, reg, idx


async def test_fresh_scaffold_flags_empty_start(workspace):
    """new_project with no follow-up authoring — start is empty."""
    _, reg, _ = workspace
    await reg.call("new_project", {"name": "fresh_status"})
    out = parse(await reg.call("get_scaffold_status", {}))
    assert out["fresh"] is False
    rules = {f["rule"] for f in out["findings"]}
    assert "empty_start_label" in rules
    assert out["start_label"]["wired"] is False


async def test_authored_but_unwired_start_flags_finding(workspace):
    """Author an opening label but skip set_start_target — the report
    should call out that the player won't actually see your scene."""
    _, reg, _ = workspace
    await reg.call("new_project", {"name": "unwired_status"})
    await reg.call(
        "create_scene",
        {
            "name": "opening",
            "background": "bg cafe",
            "ends_with": "return",
        },
    )
    out = parse(await reg.call("get_scaffold_status", {}))
    rules = {f["rule"] for f in out["findings"]}
    assert "empty_start_label" in rules
    # The fix_hint must point the agent at the right tool.
    finding = next(f for f in out["findings"] if f["rule"] == "empty_start_label")
    assert "set_start_target" in finding["fix_hint"]


async def test_wired_start_clears_findings(workspace):
    """Author + wire = clean status (modulo template noise that may
    still ship with the fixture-shaped scaffold)."""
    _, reg, _ = workspace
    await reg.call("new_project", {"name": "wired_status"})
    await reg.call(
        "create_scene",
        {
            "name": "opening",
            "background": "bg cafe",
            "ends_with": "return",
        },
    )
    await reg.call("set_start_target", {"target": "opening"})
    out = parse(await reg.call("get_scaffold_status", {}))
    assert out["start_label"]["wired"] is True
    assert out["start_label"]["jumps_to"] == "opening"
    rules = {f["rule"] for f in out["findings"]}
    assert "empty_start_label" not in rules
    assert "start_jumps_to_unknown_label" not in rules


async def test_start_pointed_at_missing_label(workspace):
    """Forward refs are allowed at write time — but flagged here so
    the agent knows lint will complain too."""
    _, reg, _ = workspace
    await reg.call("new_project", {"name": "forward_status"})
    await reg.call("set_start_target", {"target": "future_label"})
    out = parse(await reg.call("get_scaffold_status", {}))
    rules = {f["rule"] for f in out["findings"]}
    assert "start_jumps_to_unknown_label" in rules


async def test_sdk_placeholder_phrases_get_flagged(workspace):
    """Synthesize the SDK template's classic placeholder dialogue and
    confirm we catch it."""
    cfg, reg, idx = workspace
    await reg.call("new_project", {"name": "leftover_status"})
    proj = cfg.project_root
    (proj / "game" / "script.rpy").write_text(
        '# Hand-poisoned to look like an old SDK scaffold.\n'
        'define e = Character("Eileen")\n'
        '\n'
        'label start:\n'
        '    e "You\'ve created a new Ren\'Py game."\n'
        '    return\n',
        encoding="utf-8",
    )
    # Direct file write bypasses apply_write — refresh the index manually.
    idx.refresh()
    out = parse(await reg.call("get_scaffold_status", {}))
    rules = {f["rule"] for f in out["findings"]}
    assert "sdk_placeholder_content" in rules
    assert "placeholder_character_eileen" in rules


async def test_default_project_flag(workspace, tmp_path):
    """Sessions bound to `games/default/` carry an info finding so the
    agent knows to call new_project."""
    _, reg, idx = workspace
    # Manually rebind to a default-named project to mimic the auto-scaffold.
    default_root = tmp_path / "default"
    default_root.mkdir()
    (default_root / "game").mkdir()
    (default_root / "game" / "script.rpy").write_text(
        "label start:\n    return\n", encoding="utf-8"
    )
    cfg, _, _ = workspace
    cfg.bind_project(default_root)
    idx.refresh()
    out = parse(await reg.call("get_scaffold_status", {}))
    assert out["is_default_project"] is True
    rules = {f["rule"] for f in out["findings"]}
    assert "auto_scaffolded_default_project" in rules


async def test_todo_route_bodies_get_flagged(workspace):
    """create_route emits TODO-only bodies — the agent forgetting to
    fill them is a real failure mode."""
    _, reg, _ = workspace
    await reg.call("new_project", {"name": "route_status"})
    await reg.call(
        "create_route",
        {
            "prefix": "side",
            "nodes": ["intro", "middle", "end"],
        },
    )
    out = parse(await reg.call("get_scaffold_status", {}))
    todos = [f for f in out["findings"] if f["rule"] == "todo_label_body"]
    # All three nodes' bodies are TODO comments only.
    assert len(todos) >= 3
