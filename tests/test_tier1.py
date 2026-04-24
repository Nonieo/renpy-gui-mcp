from __future__ import annotations

import pytest

from .conftest import parse


async def test_overview(registry):
    out = parse(await registry.call("get_project_overview", {}))
    assert out["counts"]["labels"] == 4
    assert out["counts"]["characters"] == 2
    assert out["counts"]["screens"] == 1
    assert "start" in out["labels"]
    assert out["warnings"] == []


async def test_overview_flags_missing_start(tmp_path, monkeypatch):
    # Build a one-file project with no `start` label and confirm the overview warns.
    from renpy_mcp.config import ServerConfig
    from renpy_mcp.project.scanner import ProjectIndex
    from renpy_mcp.tools import tier1_read
    from renpy_mcp.tools.registry import ToolRegistry

    (tmp_path / "game").mkdir()
    (tmp_path / "game" / "script.rpy").write_text("label nope:\n    return\n")
    cfg = ServerConfig(project_root=tmp_path, sdk_root=tmp_path)  # sdk unused here
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, ProjectIndex(cfg))
    out = parse(await reg.call("get_project_overview", {}))
    assert any("no `label start:`" in w for w in out["warnings"])


async def test_list_labels_all_and_filtered(registry):
    out = parse(await registry.call("list_labels", {}))
    assert out["count"] == 4
    out = parse(await registry.call("list_labels", {"file": "game/script.rpy"}))
    assert out["count"] == 4
    out = parse(await registry.call("list_labels", {"file": "game/options.rpy"}))
    assert out["count"] == 0


async def test_read_label_happy(registry):
    out = parse(await registry.call("read_label", {"name": "cafe_scene"}))
    assert out["label"]["name"] == "cafe_scene"
    assert "label cafe_scene:" in out["source"]
    assert "Mei" in out["source"]


async def test_read_label_missing(registry):
    out = parse(await registry.call("read_label", {"name": "no_such_label"}))
    assert "error" in out


async def test_list_and_read_character(registry):
    out = parse(await registry.call("list_characters", {}))
    assert {c["var"] for c in out["characters"]} == {"e", "m"}

    out = parse(await registry.call("read_character", {"var": "m"}))
    assert out["character"]["display_name"] == "Mei"

    out = parse(await registry.call("read_character", {"var": "ghost"}))
    assert "error" in out


async def test_list_variables_filters(registry):
    all_vars = parse(await registry.call("list_variables", {}))
    defaults = parse(await registry.call("list_variables", {"kind": "default"}))
    defines = parse(await registry.call("list_variables", {"kind": "define"}))
    assert all_vars["count"] == defaults["count"] + defines["count"]
    assert {v["name"] for v in defaults["variables"]} == {"met_mei", "affection_mei"}


async def test_list_and_read_screen(registry):
    out = parse(await registry.call("list_screens", {}))
    assert out["count"] == 1
    assert out["screens"][0]["name"] == "affection_meter"

    out = parse(await registry.call("read_screen", {"name": "affection_meter"}))
    assert "screen affection_meter():" in out["source"]


async def test_list_images_combines_aliases_and_auto(registry):
    out = parse(await registry.call("list_images", {}))
    kinds = {img["kind"] for img in out["images"]}
    # Fixture has both `image bg park = ...` aliases and PNGs in game/images/.
    assert {"alias", "auto"} <= kinds
    names = {img["name"] for img in out["images"]}
    assert "bg park" in names  # alias
    assert "eileen happy" in names  # auto


async def test_list_audio_lists_files_and_plays(registry):
    out = parse(await registry.call("list_audio", {}))
    paths = {f["asset_path"] for f in out["files"]}
    assert "game/audio/spring_theme.ogg" in paths
    assert any(p["asset"] == "audio/spring_theme.ogg" for p in out["plays"])


async def test_find_references_finds_label_jumps(registry):
    out = parse(await registry.call("find_references", {"needle": "ending"}))
    # `label ending:` plus two `jump ending` calls = 3.
    assert out["count"] >= 3
    files = {m["file"] for m in out["matches"]}
    assert "game/script.rpy" in files


async def test_find_references_word_boundary(registry):
    out = parse(await registry.call("find_references", {"needle": "e", "word_boundary": True}))
    # `e` is the character var; bounded matches should hit only its uses, not
    # every occurrence of the letter.
    bare_e_count = sum(1 for m in out["matches"] if " e " in f" {m['context']} ")
    assert bare_e_count >= 1


async def test_read_raw_file_happy_and_traversal(registry):
    out = parse(await registry.call("read_raw_file", {"path": "game/options.rpy"}))
    assert "config.name" in out["content"]

    out = parse(await registry.call("read_raw_file", {"path": "../../../etc/passwd"}))
    assert "error" in out


@pytest.mark.skipif(
    not (__import__("pathlib").Path(__import__("os").environ.get("RENPY_SDK", str(__import__("pathlib").Path.home() / "renpy-sdk"))) / "renpy.sh").is_file(),
    reason="Ren'Py SDK not present (set RENPY_SDK to enable)",
)
async def test_get_lint_report_runs(registry):
    out = parse(await registry.call("get_lint_report", {}))
    assert "stdout" in out
    assert "returncode" in out
