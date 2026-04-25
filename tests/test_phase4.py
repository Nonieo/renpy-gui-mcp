"""Phase 4 — event-stream tools (`add_pause`, `add_setvar`, `add_show`,
`add_with_effect`, `add_flash`).

Each tool appends one line to a label's body via
`insert_into_label_body`, so the tests exercise the line-emission shape
plus the input validation; the apply_write pipeline already has its own
test coverage in `test_tier2.py`.
"""

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


# ---------- add_pause ----------------------------------------------------------


async def test_add_pause_emits_line(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("add_pause", {"label": "park_scene", "duration": 0.5}))
    assert "summary" in out
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    park_block = text.split("label park_scene:")[1].split("label ")[0]
    assert "    pause 0.5" in park_block


async def test_add_pause_renders_integer_duration_without_dot(workspace):
    cfg, reg, _ = workspace
    await reg.call("add_pause", {"label": "park_scene", "duration": 2})
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert "pause 2" in text
    assert "pause 2.0" not in text


async def test_add_pause_rejects_negative(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_pause", {"label": "park_scene", "duration": -1}))
    assert "error" in out


# ---------- add_setvar ---------------------------------------------------------


async def test_add_setvar_string_quoted(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_setvar",
            {"label": "park_scene", "name": "innkeeper_alibi", "value": "sleeping"},
        )
    )
    assert "summary" in out
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert '$ innkeeper_alibi = "sleeping"' in text


async def test_add_setvar_bool_int_float_null(workspace):
    cfg, reg, _ = workspace
    await reg.call("add_setvar", {"label": "park_scene", "name": "knows_diary", "value": True})
    await reg.call("add_setvar", {"label": "park_scene", "name": "trust_mei", "value": 1})
    await reg.call("add_setvar", {"label": "park_scene", "name": "weight", "value": 1.5})
    await reg.call("add_setvar", {"label": "park_scene", "name": "ghost", "value": None})
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert "$ knows_diary = True" in text
    assert "$ trust_mei = 1" in text
    assert "$ weight = 1.5" in text
    assert "$ ghost = None" in text


async def test_add_setvar_rejects_invalid_identifier(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call("add_setvar", {"label": "park_scene", "name": "not a name!", "value": 1})
    )
    assert "error" in out


async def test_add_setvar_rejects_unsupported_value_type(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_setvar",
            {"label": "park_scene", "name": "tags", "value": ["a", "b"]},
        )
    )
    assert "error" in out


# ---------- add_show -----------------------------------------------------------


async def test_add_show_minimal(workspace):
    cfg, reg, _ = workspace
    await reg.call("add_show", {"label": "park_scene", "tag": "eileen"})
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert "    show eileen" in text


async def test_add_show_full(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_show",
        {
            "label": "park_scene",
            "tag": "eileen",
            "expression": "happy",
            "position": "left",
            "transition": "dissolve",
        },
    )
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert "show eileen happy at left with dissolve" in text


async def test_add_show_rejects_bad_tag(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_show", {"label": "park_scene", "tag": "not a tag"}))
    assert "error" in out


# ---------- add_with_effect ----------------------------------------------------


async def test_add_with_effect_atom(workspace):
    cfg, reg, _ = workspace
    await reg.call("add_with_effect", {"label": "park_scene", "expression": "hpunch"})
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert "    with hpunch" in text


async def test_add_with_effect_callable(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_with_effect", {"label": "park_scene", "expression": "Dissolve(0.5)"}
    )
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert "with Dissolve(0.5)" in text


async def test_add_with_effect_rejects_empty(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_with_effect", {"label": "park_scene", "expression": ""}))
    assert "error" in out


# ---------- add_flash ----------------------------------------------------------


async def test_add_flash_default_duration(workspace):
    cfg, reg, _ = workspace
    await reg.call("add_flash", {"label": "park_scene", "color": "#ffffff"})
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    # Default duration 0.25 splits half-half: 0.125 + 0 + 0.125.
    assert 'with Fade(0.125, 0.0, 0.125, color="#ffffff")' in text


async def test_add_flash_explicit_duration(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_flash", {"label": "park_scene", "color": "#a04a6b", "duration": 1}
    )
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert 'with Fade(0.5, 0.0, 0.5, color="#a04a6b")' in text


async def test_add_flash_short_hex(workspace):
    cfg, reg, _ = workspace
    await reg.call("add_flash", {"label": "park_scene", "color": "#fff"})
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert 'color="#fff"' in text


async def test_add_flash_rejects_non_hex(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_flash", {"label": "park_scene", "color": "white"}))
    assert "error" in out
