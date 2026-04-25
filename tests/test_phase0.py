"""Tests for Phase 0 of the IDE roadmap:

- `read_label_tree` (Tier 1) — typed structured tree of one label
- `read_canvas_positions` (Tier 1) + `set_canvas_positions` (Tier 2) —
  the GUI's editable Story Map sidecar at `.renpy-mcp/canvas.json`

The fixture project (`tests/fixtures/tiny_project/`) is small but covers
every shape `read_label_tree` needs to parse: a label with a `menu`
(`start`), one with a `$ setvar` plus `jump` (`cafe_scene`), one with a
plain say + `jump` (`park_scene`), and one with `if/else` + `return`
(`ending`).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.canvas import (
    SIDECAR_DIR,
    SIDECAR_FILENAME,
    CanvasError,
    read_positions,
    set_positions,
)
from renpy_mcp.project.label_tree import infer_label_kind, parse_label_body
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import tier1_read, tier2_write
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT, parse


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[ServerConfig, ToolRegistry, ProjectIndex]:
    """Per-test copy of the fixture so sidecar writes don't leak between tests."""
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier2_write.register(reg, cfg, idx)
    return cfg, reg, idx


# ---------- read_label_tree -----------------------------------------------------


async def test_read_label_tree_start_has_menu(registry):
    out = parse(await registry.call("read_label_tree", {"name": "start"}))
    assert out["label"]["name"] == "start"
    assert out["kind"] == "start"
    kinds = [n["kind"] for n in out["body"]]
    # start opens with scene + play music + 2 says + menu
    assert kinds[:2] == ["scene", "play"]
    assert kinds.count("say") == 2
    assert kinds[-1] == "menu"
    assert out["shorthand"]["background"] == "bg park"
    assert out["shorthand"]["music"] == "audio/spring_theme.ogg"
    assert out["shorthand"]["ends_with_return"] is False
    # The menu's two choices both reach a label — those are outgoing targets.
    assert set(out["shorthand"]["outgoing_targets"]) == {"cafe_scene", "park_scene"}

    menu = out["body"][-1]
    assert len(menu["choices"]) == 2
    cafe_choice = next(c for c in menu["choices"] if c["text"] == "Visit the cafe")
    cafe_kinds = [n["kind"] for n in cafe_choice["body"]]
    assert cafe_kinds == ["set", "jump"]
    assert cafe_choice["body"][0]["expression"] == "met_mei = True"
    assert cafe_choice["body"][1]["target"] == "cafe_scene"


async def test_read_label_tree_cafe_scene(registry):
    out = parse(await registry.call("read_label_tree", {"name": "cafe_scene"}))
    assert out["kind"] == "scene"
    kinds = [n["kind"] for n in out["body"]]
    assert kinds == ["scene", "say", "set", "jump"]
    assert out["shorthand"]["background"] == "bg cafe"
    assert out["shorthand"]["music"] is None
    assert out["shorthand"]["outgoing_targets"] == ["ending"]


async def test_read_label_tree_park_scene(registry):
    out = parse(await registry.call("read_label_tree", {"name": "park_scene"}))
    assert out["kind"] == "scene"
    kinds = [n["kind"] for n in out["body"]]
    assert kinds == ["say", "jump"]
    assert out["body"][0]["character"] == "e"
    assert out["body"][0]["text"].startswith("The park is quiet")


async def test_read_label_tree_ending_has_if_branches(registry):
    out = parse(await registry.call("read_label_tree", {"name": "ending"}))
    # ending terminates in `return` and has no jump/call → kind=ending
    assert out["kind"] == "ending"
    kinds = [n["kind"] for n in out["body"]]
    assert kinds == ["if", "return"]
    branches = out["body"][0]["branches"]
    assert [b["kind"] for b in branches] == ["if", "else"]
    assert branches[0]["condition"] == "met_mei"
    assert branches[1]["condition"] is None
    # Each branch has exactly one say.
    assert all(len(b["body"]) == 1 and b["body"][0]["kind"] == "say" for b in branches)
    assert out["shorthand"]["ends_with_return"] is True
    assert out["shorthand"]["outgoing_targets"] == []


async def test_read_label_tree_unknown(registry):
    out = parse(await registry.call("read_label_tree", {"name": "no_such_label"}))
    assert "error" in out
    assert "no such label" in out["error"]


# ---------- label_tree parser unit-level cases ---------------------------------


def test_parse_label_body_recognises_compound_constructs():
    body = (
        "    scene bg park\n"
        "    e \"hi\"\n"
        "    if affection_mei > 0:\n"
        "        e \"You like Mei.\"\n"
        "    elif affection_mei < 0:\n"
        "        e \"You dislike Mei.\"\n"
        "    else:\n"
        "        e \"Neutral.\"\n"
        "    pause 0.5\n"
        "    with hpunch\n"
        "    stop music fadeout 1.0\n"
        "    return\n"
    )
    tree = parse_label_body(body, body_start_line=10)
    kinds = [n["kind"] for n in tree["body"]]
    assert kinds == ["scene", "say", "if", "pause", "with", "stop", "return"]
    branches = tree["body"][2]["branches"]
    assert [b["kind"] for b in branches] == ["if", "elif", "else"]
    assert tree["shorthand"]["ends_with_return"] is True
    assert tree["shorthand"]["background"] == "bg park"


def test_parse_label_body_surfaces_unparsed_lines():
    body = "    scene bg cafe\n    not_a_real_statement foo bar\n    return\n"
    tree = parse_label_body(body, body_start_line=1)
    kinds = [n["kind"] for n in tree["body"]]
    assert kinds == ["scene", "return"]
    assert len(tree["unparsed"]) == 1
    assert tree["unparsed"][0]["raw"] == "not_a_real_statement foo bar"


def test_infer_label_kind_choice_when_body_ends_in_menu():
    body = [
        {"kind": "say", "line": 1, "character": "e", "text": "Choose."},
        {"kind": "menu", "line": 2, "menu_label": None, "choices": []},
    ]
    shorthand = {"background": None, "music": None, "outgoing_targets": [], "ends_with_return": False}
    assert infer_label_kind("intro", body, shorthand) == "choice"


# ---------- canvas-positions sidecar -------------------------------------------


async def test_read_canvas_positions_empty_when_no_sidecar(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("read_canvas_positions", {}))
    assert out["count"] == 0
    assert out["labels"] == {}
    assert out["version"] == 1


async def test_set_canvas_positions_round_trip(workspace):
    cfg, reg, _ = workspace
    payload = {"start": {"x": 10.0, "y": 20.0}, "ending": {"x": 200, "y": 50}}
    out = parse(await reg.call("set_canvas_positions", {"positions": payload}))
    assert out["count"] == 2
    # Sidecar landed at the documented path.
    sidecar = cfg.project_root / SIDECAR_DIR / SIDECAR_FILENAME
    assert sidecar.is_file()
    on_disk = json.loads(sidecar.read_text())
    assert on_disk["version"] == 1
    assert on_disk["labels"]["start"] == {"x": 10.0, "y": 20.0}
    assert on_disk["labels"]["ending"]["x"] == 200.0  # int coerced to float
    # Read tool sees the same data.
    read_back = parse(await reg.call("read_canvas_positions", {}))
    assert read_back["labels"] == on_disk["labels"]


async def test_set_canvas_positions_merges_by_default(workspace):
    _, reg, _ = workspace
    await reg.call("set_canvas_positions", {"positions": {"start": {"x": 1, "y": 2}}})
    await reg.call("set_canvas_positions", {"positions": {"ending": {"x": 3, "y": 4}}})
    out = parse(await reg.call("read_canvas_positions", {}))
    assert set(out["labels"]) == {"start", "ending"}


async def test_set_canvas_positions_replace_drops_others(workspace):
    _, reg, _ = workspace
    await reg.call("set_canvas_positions", {"positions": {"start": {"x": 1, "y": 2}}})
    await reg.call(
        "set_canvas_positions",
        {"positions": {"ending": {"x": 9, "y": 9}}, "replace": True},
    )
    out = parse(await reg.call("read_canvas_positions", {}))
    assert set(out["labels"]) == {"ending"}


async def test_set_canvas_positions_rejects_non_numeric(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "set_canvas_positions",
            {"positions": {"start": {"x": "not-a-number", "y": 0}}},
        )
    )
    assert "error" in out


async def test_read_canvas_positions_rejects_malformed_sidecar(workspace):
    cfg, reg, _ = workspace
    sidecar_dir = cfg.project_root / SIDECAR_DIR
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    (sidecar_dir / SIDECAR_FILENAME).write_text("{ not json")
    out = parse(await reg.call("read_canvas_positions", {}))
    assert "error" in out
    assert "malformed" in out["error"]


def test_set_positions_no_op_skips_disk_write(workspace):
    """Direct call to the I/O layer: identical payload should not bump mtime."""
    cfg, _, _ = workspace
    payload = {"start": {"x": 1.0, "y": 2.0}}
    set_positions(cfg, payload)
    sidecar = cfg.project_root / SIDECAR_DIR / SIDECAR_FILENAME
    first_mtime = sidecar.stat().st_mtime_ns
    set_positions(cfg, payload)  # identical → no rewrite
    assert sidecar.stat().st_mtime_ns == first_mtime


def test_canvas_error_on_missing_x_y(workspace):
    cfg, _, _ = workspace
    with pytest.raises(CanvasError):
        set_positions(cfg, {"start": {"x": 1.0}})  # missing y
