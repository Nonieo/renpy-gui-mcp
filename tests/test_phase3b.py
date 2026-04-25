"""Phase 3b backend tests — `add_menu_branch`, `redirect_jump`, `delete_label`."""

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


# ---------- add_menu_branch ----------------------------------------------------


async def test_add_menu_branch_appends_choice_to_start(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_menu_branch",
            {
                "label": "start",
                "text": "Take a third path",
                "body": ["jump ending"],
            },
        )
    )
    assert "summary" in out
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    # The new choice header lands at 8 spaces (one level under `menu:` at 4).
    assert '        "Take a third path":' in text
    assert "            jump ending" in text
    # Must appear BEFORE the next top-level statement / next label.
    start_block = text.split("label start:")[1].split("label ")[0]
    assert "Take a third path" in start_block


async def test_add_menu_branch_with_condition(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_menu_branch",
            {
                "label": "start",
                "text": "If you trust her",
                "condition": "met_mei",
                "body": ["jump cafe_scene"],
            },
        )
    )
    assert "summary" in out
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    assert '"If you trust her" if met_mei:' in text


async def test_add_menu_branch_rejects_label_without_menu(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_menu_branch",
            {"label": "cafe_scene", "text": "no menu here"},
        )
    )
    assert "error" in out
    assert "no top-level `menu:`" in out["error"]


async def test_add_menu_branch_rejects_unknown_label(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_menu_branch",
            {"label": "ghost_label", "text": "anything"},
        )
    )
    assert "error" in out
    assert "no such label" in out["error"]


async def test_add_menu_branch_default_body_is_pass(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_menu_branch",
        {"label": "start", "text": "stub branch"},
    )
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    # Look for the choice followed by `pass` at body indent (12 spaces).
    block = text.split('"stub branch":', 1)[1]
    first_body_line = block.splitlines()[1] if "\n" in block else ""
    assert first_body_line.lstrip() == "pass"


# ---------- redirect_jump ------------------------------------------------------


async def test_redirect_jump_rewrites_target(workspace):
    cfg, reg, _ = workspace
    # cafe_scene's body ends with `jump ending`. Redirect to park_scene.
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    lines = text.splitlines()
    cafe_jump_line = next(
        (i + 1 for i, ln in enumerate(lines) if ln.strip() == "jump ending" and "label cafe_scene:" in "".join(lines[max(0, i - 5) : i])),
        None,
    )
    assert cafe_jump_line is not None
    out = parse(
        await reg.call(
            "redirect_jump",
            {"file": "game/script.rpy", "line": cafe_jump_line, "new_target": "park_scene"},
        )
    )
    assert "summary" in out
    assert "park_scene" in out["summary"]
    new_text = (cfg.project_root / "game" / "script.rpy").read_text()
    new_lines = new_text.splitlines()
    assert new_lines[cafe_jump_line - 1].strip() == "jump park_scene"


async def test_redirect_jump_rejects_non_jump_line(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "redirect_jump",
            # line 6 of fixture script.rpy is a `define` line, not a jump.
            {"file": "game/script.rpy", "line": 6, "new_target": "ending"},
        )
    )
    assert "error" in out
    assert "not a `jump" in out["error"]


async def test_redirect_jump_rejects_unknown_target(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "redirect_jump",
            {"file": "game/script.rpy", "line": 1, "new_target": "no_such_label"},
        )
    )
    assert "error" in out
    assert "no such label" in out["error"]


async def test_redirect_jump_rejects_invalid_identifier(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "redirect_jump",
            {"file": "game/script.rpy", "line": 1, "new_target": "not a name!"},
        )
    )
    assert "error" in out


async def test_redirect_jump_no_op_when_same_target(workspace):
    cfg, reg, _ = workspace
    text = (cfg.project_root / "game" / "script.rpy").read_text()
    lines = text.splitlines()
    # park_scene's `jump ending` is the last jump in the file structure.
    park_jump_line = next(
        (i + 1 for i, ln in enumerate(lines) if ln.strip() == "jump ending"),
        None,
    )
    assert park_jump_line is not None
    out = parse(
        await reg.call(
            "redirect_jump",
            {"file": "game/script.rpy", "line": park_jump_line, "new_target": "ending"},
        )
    )
    assert out["no_op"] is True


# ---------- delete_label -------------------------------------------------------


async def test_delete_label_removes_unreferenced_target(workspace):
    """ending is referenced from cafe_scene/park_scene; deleting cafe_scene
    should be allowed once we clear its references; but for an isolated
    target we use a freshly added orphan label."""
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text("label orphan_draft:\n    return\n")
    idx.refresh()
    out = parse(await reg.call("delete_label", {"label": "orphan_draft"}))
    assert "summary" in out
    assert "deleted label `orphan_draft`" in out["summary"]
    text = extra.read_text()
    assert "orphan_draft" not in text


async def test_delete_label_refuses_with_incoming_references(workspace):
    _, reg, _ = workspace
    # cafe_scene is jumped to from `start`. Should refuse.
    out = parse(await reg.call("delete_label", {"label": "cafe_scene"}))
    assert "error" in out
    assert "still referenced" in out["error"]
    # References record the label that contained the jump/call; the target
    # is implicit (it's `cafe_scene`, which we just tried to delete).
    refs = out.get("references", [])
    assert any(r["label"] == "start" for r in refs)
    assert all(r["kind"] in ("jump", "call") for r in refs)


async def test_delete_label_unknown_target(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("delete_label", {"label": "no_such_label"}))
    assert "error" in out


async def test_delete_label_warns_when_deleting_start(workspace, monkeypatch):
    """Deleting `start` is allowed but emits a warning. We need to first
    rewrite all the jumps that target labels other than start; for the
    fixture, `start` itself has no incoming references — it's the engine
    entry point. So this test covers the soft-warn path directly."""
    cfg, reg, _ = workspace
    out = parse(await reg.call("delete_label", {"label": "start"}))
    # `start` isn't referenced via jump/call (it's the entry point), so the
    # delete proceeds. The response carries the warning.
    assert "summary" in out
    assert any("project will not run" in w for w in out.get("warnings", []))
