"""Phase 6 — `get_choice_graph` Tier 1 read."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import tier1_read, tier2_write
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT, parse


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[ServerConfig, ToolRegistry, ProjectIndex]:
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier2_write.register(reg, cfg, idx)
    return cfg, reg, idx


# ---------- happy path on the fixture ------------------------------------------


async def test_get_choice_graph_finds_fixture_menu(registry):
    out = parse(await registry.call("get_choice_graph", {}))
    assert out["count"] == 1
    choice = out["choices"][0]
    assert choice["label"] == "start"
    assert choice["file"] == "game/script.rpy"
    targets = {b["target"] for b in choice["branches"]}
    assert targets == {"cafe_scene", "park_scene"}


async def test_get_choice_graph_carries_branch_text(registry):
    out = parse(await registry.call("get_choice_graph", {}))
    choice = out["choices"][0]
    texts = {b["text"] for b in choice["branches"]}
    assert texts == {"Visit the cafe", "Stay in the park"}


async def test_get_choice_graph_target_kind_and_line(registry):
    out = parse(await registry.call("get_choice_graph", {}))
    branches = out["choices"][0]["branches"]
    for b in branches:
        assert b["target_kind"] == "jump"
        assert isinstance(b["target_line"], int) and b["target_line"] > 0


# ---------- conditional branches ------------------------------------------------


async def test_get_choice_graph_carries_condition(workspace):
    """Add a conditional branch via add_menu_branch and verify the condition
    survives the round-trip."""
    _, reg, _ = workspace
    add = parse(
        await reg.call(
            "add_menu_branch",
            {
                "label": "start",
                "text": "Take a third path",
                "condition": "met_mei",
                "body": ["jump ending"],
            },
        )
    )
    assert "summary" in add
    out = parse(await reg.call("get_choice_graph", {}))
    third = next(
        b for b in out["choices"][0]["branches"] if b["text"] == "Take a third path"
    )
    assert third["condition"] == "met_mei"
    assert third["target"] == "ending"


# ---------- branches without a clear target -----------------------------------


async def test_get_choice_graph_handles_branch_without_jump(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label fork:\n"
        "    menu:\n"
        '        "Do nothing":\n'
        "            pass\n"
    )
    idx.refresh()
    out = parse(await reg.call("get_choice_graph", {}))
    fork = next(c for c in out["choices"] if c["label"] == "fork")
    assert fork["branches"][0]["target"] is None
    assert fork["branches"][0]["target_kind"] is None


# ---------- empty project -----------------------------------------------------


async def test_get_choice_graph_empty(tmp_path):
    """A project with no menus returns an empty choice graph."""
    proj = tmp_path / "empty_project"
    (proj / "game").mkdir(parents=True)
    (proj / "game" / "script.rpy").write_text("label start:\n    return\n")

    cfg = ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, ProjectIndex(cfg))
    out = parse(await reg.call("get_choice_graph", {}))
    assert out["count"] == 0
    assert out["choices"] == []
