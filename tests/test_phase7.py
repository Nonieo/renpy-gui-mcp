"""Phase 7 — Screen Layout composer."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.composers import (
    CompositionError,
    generate_imagemap,
    generate_screen_layout,
    generate_stage,
)
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import tier1_read, tier2_write, tier3_intents
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
    tier3_intents.register(reg, cfg, idx)
    return cfg, reg, idx


# ---------- generator unit tests ----------------------------------------------


def test_generate_screen_layout_simple_vbox():
    out = generate_screen_layout(
        "splash",
        {
            "kind": "vbox",
            "props": {"xalign": 0.5, "spacing": 10},
            "children": [
                {"kind": "text", "text": "Hello"},
                {"kind": "textbutton", "text": "Start", "action": "Start()"},
            ],
        },
    )
    expected = (
        "screen splash():\n"
        "    vbox:\n"
        "        xalign 0.5\n"
        "        spacing 10\n"
        '        text "Hello"\n'
        '        textbutton "Start" action Start()\n'
    )
    assert out == expected


def test_generate_screen_layout_button_with_children():
    out = generate_screen_layout(
        "panel",
        {
            "kind": "button",
            "action": "Return()",
            "children": [{"kind": "text", "text": "OK"}],
        },
    )
    assert "button:" in out
    assert "        action Return()" in out
    assert '        text "OK"' in out


def test_generate_screen_layout_spacer():
    out = generate_screen_layout(
        "stack",
        {
            "kind": "vbox",
            "children": [
                {"kind": "spacer", "height": 20},
                {"kind": "spacer", "width": 50, "height": 50},
            ],
        },
    )
    assert "add Null(height=20)" in out
    assert "add Null(height=50, width=50)" in out


def test_generate_screen_layout_empty_container_keeps_block_valid():
    """Empty containers must emit `null` so Ren'Py parses the block."""
    out = generate_screen_layout("blank", {"kind": "frame"})
    assert "frame:" in out
    assert "null" in out


def test_generate_screen_layout_nested_containers():
    out = generate_screen_layout(
        "menu_screen",
        {
            "kind": "frame",
            "children": [
                {
                    "kind": "vbox",
                    "props": {"spacing": 6},
                    "children": [
                        {"kind": "hbox", "children": [{"kind": "text", "text": "Score"}]}
                    ],
                }
            ],
        },
    )
    # Indentation: frame at depth 1 (4 spaces), vbox at 2 (8), hbox at 3 (12),
    # text at 4 (16).
    assert "    frame:" in out
    assert "        vbox:" in out
    assert "            hbox:" in out
    assert '                text "Score"' in out


def test_generate_screen_layout_text_with_props():
    out = generate_screen_layout(
        "labeled",
        {"kind": "text", "text": "Title", "props": {"size": 36, "color": "#fff"}},
    )
    assert 'text "Title":' in out
    assert "        size 36" in out
    assert '        color "#fff"' in out  # string props are quoted


def test_generate_screen_layout_text_escape():
    out = generate_screen_layout(
        "msg",
        {"kind": "text", "text": 'has "quotes"'},
    )
    assert 'text "has \\"quotes\\""' in out


def test_generate_screen_layout_rejects_unknown_kind():
    with pytest.raises(CompositionError, match="unknown widget kind"):
        generate_screen_layout("x", {"kind": "definitely_not_a_widget"})


def test_generate_screen_layout_rejects_invalid_screen_name():
    with pytest.raises(CompositionError, match="not a valid identifier"):
        generate_screen_layout("not a name", {"kind": "frame"})


def test_generate_screen_layout_rejects_bad_button_without_action():
    with pytest.raises(CompositionError, match="`button` needs"):
        generate_screen_layout("x", {"kind": "button", "children": []})


def test_generate_screen_layout_rejects_spacer_without_dimensions():
    with pytest.raises(CompositionError, match="`spacer` needs"):
        generate_screen_layout("x", {"kind": "spacer"})


# ---------- add_screen_layout tool tests --------------------------------------


async def test_add_screen_layout_appends_to_screens_rpy(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_screen_layout",
            {
                "name": "title_card",
                "root": {
                    "kind": "vbox",
                    "props": {"xalign": 0.5},
                    "children": [{"kind": "text", "text": "The Hollow Lighthouse"}],
                },
            },
        )
    )
    assert "summary" in out
    text = (cfg.project_root / "game" / "screens.rpy").read_text()
    assert "screen title_card():" in text
    assert "    vbox:" in text
    assert '        text "The Hollow Lighthouse"' in text


async def test_add_screen_layout_rejects_existing_name(workspace):
    cfg, reg, _ = workspace
    # The fixture already defines `screen affection_meter():`.
    out = parse(
        await reg.call(
            "add_screen_layout",
            {
                "name": "affection_meter",
                "root": {"kind": "frame"},
            },
        )
    )
    assert "error" in out
    assert "already exists" in out["error"]


async def test_add_screen_layout_rejects_reserved_name(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_screen_layout",
            {"name": "if", "root": {"kind": "frame"}},
        )
    )
    assert "error" in out


async def test_add_screen_layout_writes_to_custom_file(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_screen_layout",
            {
                "name": "hud",
                "root": {"kind": "frame"},
                "file": "game/hud.rpy",
            },
        )
    )
    assert "summary" in out
    text = (cfg.project_root / "game" / "hud.rpy").read_text()
    assert "screen hud():" in text


async def test_add_screen_layout_surfaces_composer_error(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_screen_layout",
            {"name": "bad", "root": {"kind": "spacer"}},  # no dimensions
        )
    )
    assert "error" in out
    assert "spacer" in out["error"]


# ---------- Stage generator unit tests ----------------------------------------


def test_generate_stage_full():
    lines = generate_stage(
        background="bg park",
        sprites=[
            {"tag": "eileen", "expression": "happy", "position": "left"},
            {"tag": "mei", "position": "right"},
        ],
        transition="dissolve",
    )
    assert lines == [
        "scene bg park",
        "show eileen happy at left",
        "show mei at right",
        "with dissolve",
    ]


def test_generate_stage_background_only():
    assert generate_stage(background="bg cafe") == ["scene bg cafe"]


def test_generate_stage_sprites_only():
    lines = generate_stage(sprites=[{"tag": "eileen"}])
    assert lines == ["show eileen"]


def test_generate_stage_rejects_empty_input():
    with pytest.raises(CompositionError, match="background or one sprite"):
        generate_stage()


def test_generate_stage_rejects_invalid_tag():
    with pytest.raises(CompositionError, match="`tag` must"):
        generate_stage(sprites=[{"tag": "not a tag"}])


def test_generate_stage_rejects_multiline_position():
    with pytest.raises(CompositionError, match="single-line"):
        generate_stage(
            background="bg cafe",
            sprites=[{"tag": "e", "position": "left\nbroken"}],
        )


# ---------- ImageMap generator unit tests -------------------------------------


def test_generate_imagemap_basic():
    out = generate_imagemap(
        name="title_select",
        ground="gui/title_idle.png",
        hover="gui/title_hover.png",
        hotspots=[
            {"x": 100, "y": 200, "w": 300, "h": 80, "action": 'Jump("start")'},
            {"x": 100, "y": 320, "w": 300, "h": 80, "action": "Quit()"},
        ],
    )
    assert "screen title_select():" in out
    assert "    imagemap:" in out
    assert '        ground "gui/title_idle.png"' in out
    assert '        hover "gui/title_hover.png"' in out
    assert '        hotspot (100 200 300 80) action Jump("start")' in out
    assert "        hotspot (100 320 300 80) action Quit()" in out


def test_generate_imagemap_rejects_empty_hotspots():
    with pytest.raises(CompositionError, match="`hotspots` must"):
        generate_imagemap("x", "g.png", "h.png", [])


def test_generate_imagemap_rejects_non_numeric_rect():
    with pytest.raises(CompositionError, match="must be numeric"):
        generate_imagemap(
            "x", "g.png", "h.png",
            [{"x": "left", "y": 0, "w": 10, "h": 10, "action": "Return()"}],
        )


def test_generate_imagemap_rejects_invalid_screen_name():
    with pytest.raises(CompositionError, match="not a valid identifier"):
        generate_imagemap(
            "not a name", "g.png", "h.png",
            [{"x": 0, "y": 0, "w": 1, "h": 1, "action": "Return()"}],
        )


# ---------- add_stage Tier 3 tool ---------------------------------------------


async def test_add_stage_appends_to_existing_label(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_stage",
            {
                "label": "park_scene",
                "background": "bg cafe",
                "sprites": [{"tag": "eileen", "expression": "happy", "position": "left"}],
                "transition": "dissolve",
            },
        )
    )
    assert "summary" in out, out
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    park_block = text.split("label park_scene:")[1].split("label ")[0]
    assert "scene bg cafe" in park_block
    assert "show eileen happy at left" in park_block
    assert "with dissolve" in park_block


async def test_add_stage_rejects_unknown_label(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_stage",
            {"label": "no_such_label", "background": "bg park"},
        )
    )
    assert "error" in out
    assert "no such label" in out["error"]


async def test_add_stage_surfaces_composer_error(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_stage",
            {"label": "park_scene"},  # no bg, no sprites
        )
    )
    assert "error" in out
    assert "background or one sprite" in out["error"]


# ---------- add_imagemap Tier 3 tool ------------------------------------------


async def test_add_imagemap_appends_screen_block(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_imagemap",
            {
                "name": "title_pick",
                "ground": "gui/title_idle.png",
                "hover": "gui/title_hover.png",
                "hotspots": [
                    {"x": 0, "y": 0, "w": 100, "h": 50, "action": "Return()"}
                ],
            },
        )
    )
    assert "summary" in out, out
    text = (cfg.project_root / "game" / "screens.rpy").read_text()
    assert "screen title_pick():" in text
    assert "    imagemap:" in text
    assert "        hotspot (0 0 100 50) action Return()" in text


async def test_add_imagemap_rejects_existing_screen(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_imagemap",
            {
                "name": "affection_meter",  # already in the fixture
                "ground": "g.png",
                "hover": "h.png",
                "hotspots": [{"x": 0, "y": 0, "w": 1, "h": 1, "action": "Return()"}],
            },
        )
    )
    assert "error" in out
    assert "already exists" in out["error"]


async def test_add_imagemap_writes_to_custom_file(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_imagemap",
            {
                "name": "custom_map",
                "ground": "g.png",
                "hover": "h.png",
                "hotspots": [{"x": 0, "y": 0, "w": 1, "h": 1, "action": "Return()"}],
                "file": "game/custom_screens.rpy",
            },
        )
    )
    assert "summary" in out, out
    text = (cfg.project_root / "game" / "custom_screens.rpy").read_text()
    assert "screen custom_map():" in text
