"""Phase 8 — translation surface + build distribute."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.project.translations import (
    coverage_summary,
    list_languages,
    parse_language,
)
from renpy_mcp.tools import lifecycle, tier1_read
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
    lifecycle.register(reg, cfg, idx)
    # Reset module state across tests in this module.
    lifecycle._preview_proc = None  # type: ignore[attr-defined]
    lifecycle._warp_temp_active = False  # type: ignore[attr-defined]
    return cfg, reg, idx


# ---------- parser unit tests --------------------------------------------------


def test_parser_no_tl_directory(workspace):
    cfg, _, _ = workspace
    assert list_languages(cfg) == []
    assert parse_language(cfg, "spanish") == []
    assert coverage_summary(cfg) == []


def test_parser_say_block(workspace):
    cfg, _, _ = workspace
    tl_dir = cfg.project_root / "game" / "tl" / "spanish"
    tl_dir.mkdir(parents=True)
    (tl_dir / "script.rpy").write_text(
        "translate spanish hello_5a8d:\n"
        '    # e "Hello"\n'
        '    e "Hola"\n'
        "\n"
        "translate spanish goodbye_3c2f:\n"
        '    # e "Goodbye"\n'
        '    e ""\n'
    )
    entries = parse_language(cfg, "spanish")
    assert len(entries) == 2
    by_id = {e.block_id: e for e in entries}
    assert by_id["hello_5a8d"].source == "Hello"
    assert by_id["hello_5a8d"].target == "Hola"
    assert by_id["hello_5a8d"].is_stale is False
    assert by_id["goodbye_3c2f"].target == ""
    assert by_id["goodbye_3c2f"].is_stale is True


def test_parser_strings_block(workspace):
    cfg, _, _ = workspace
    tl_dir = cfg.project_root / "game" / "tl" / "spanish"
    tl_dir.mkdir(parents=True)
    (tl_dir / "screens.rpy").write_text(
        "translate spanish strings:\n"
        '    old "Welcome"\n'
        '    new "Bienvenido"\n'
        "\n"
        '    old "Goodbye"\n'
        '    new ""\n'
        "\n"
        '    old "Identical"\n'
        '    new "Identical"\n'
    )
    entries = parse_language(cfg, "spanish")
    assert len(entries) == 3
    by_source = {e.source: e for e in entries}
    assert by_source["Welcome"].is_stale is False
    assert by_source["Goodbye"].is_stale is True  # empty
    assert by_source["Identical"].is_stale is True  # equals source


def test_coverage_summary_multilang(workspace):
    cfg, _, _ = workspace
    es = cfg.project_root / "game" / "tl" / "spanish"
    fr = cfg.project_root / "game" / "tl" / "french"
    es.mkdir(parents=True)
    fr.mkdir(parents=True)
    (es / "script.rpy").write_text(
        "translate spanish a_1:\n    # e \"x\"\n    e \"X\"\n"
        "translate spanish b_2:\n    # e \"y\"\n    e \"\"\n"
    )
    (fr / "script.rpy").write_text(
        "translate french a_1:\n    # e \"x\"\n    e \"X\"\n"
    )
    rows = {r["language"]: r for r in coverage_summary(cfg)}
    assert rows["spanish"]["total"] == 2
    assert rows["spanish"]["translated"] == 1
    assert rows["spanish"]["stale"] == 1
    assert rows["spanish"]["percent"] == 50.0
    assert rows["french"]["total"] == 1
    assert rows["french"]["percent"] == 100.0


# ---------- get_translation_coverage ------------------------------------------


async def test_get_translation_coverage_empty(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("get_translation_coverage", {}))
    assert out["count"] == 0
    assert out["languages"] == []


async def test_get_translation_coverage_after_seed(workspace):
    cfg, reg, _ = workspace
    es = cfg.project_root / "game" / "tl" / "spanish"
    es.mkdir(parents=True)
    (es / "script.rpy").write_text(
        "translate spanish a_1:\n    # e \"x\"\n    e \"X\"\n"
        "translate spanish b_2:\n    # e \"y\"\n    e \"\"\n"
    )
    out = parse(await reg.call("get_translation_coverage", {}))
    assert out["count"] == 1
    row = out["languages"][0]
    assert row["language"] == "spanish"
    assert row["translated"] == 1 and row["stale"] == 1


# ---------- find_stale_translations -------------------------------------------


async def test_find_stale_translations_filters_by_language(workspace):
    cfg, reg, _ = workspace
    es = cfg.project_root / "game" / "tl" / "spanish"
    fr = cfg.project_root / "game" / "tl" / "french"
    es.mkdir(parents=True)
    fr.mkdir(parents=True)
    (es / "a.rpy").write_text(
        "translate spanish a_1:\n    # e \"x\"\n    e \"\"\n"
    )
    (fr / "b.rpy").write_text(
        "translate french b_2:\n    # e \"y\"\n    e \"y\"\n"
    )
    out = parse(await reg.call("find_stale_translations", {"language": "spanish"}))
    assert out["count"] == 1
    assert out["stale"][0]["language"] == "spanish"
    out_all = parse(await reg.call("find_stale_translations", {}))
    assert out_all["count"] == 2


# ---------- generate_translation_scaffolding (mocked SDK) ---------------------


async def test_generate_translation_scaffolding_invokes_sdk(workspace, monkeypatch):
    cfg, reg, _ = workspace
    captured: dict = {}

    async def fake_run(sdk_root, project_root, *args, timeout=120.0):
        captured["args"] = args
        from renpy_mcp.sdk import SDKResult

        return SDKResult(returncode=0, stdout="generated", stderr="")

    monkeypatch.setattr("renpy_mcp.tools.lifecycle.renpy_sdk.run", fake_run)
    out = parse(
        await reg.call("generate_translation_scaffolding", {"language": "spanish"})
    )
    assert out["language"] == "spanish"
    assert out["returncode"] == 0
    assert captured["args"] == ("translate", "spanish")


async def test_generate_translation_scaffolding_rejects_unsafe_language(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "generate_translation_scaffolding", {"language": "spanish; rm -rf"}
        )
    )
    assert "error" in out


# ---------- build_distribution (mocked SDK) -----------------------------------


async def test_build_distribution_invokes_sdk(workspace, monkeypatch):
    cfg, reg, _ = workspace
    captured: dict = {}

    async def fake_run(sdk_root, basedir, *args, timeout=120.0):
        captured["sdk_root"] = sdk_root
        captured["basedir"] = basedir
        captured["args"] = args
        captured["timeout"] = timeout
        from renpy_mcp.sdk import SDKResult

        return SDKResult(returncode=0, stdout="built", stderr="")

    monkeypatch.setattr("renpy_mcp.tools.lifecycle.renpy_sdk.run", fake_run)
    out = parse(
        await reg.call("build_distribution", {"targets": ["pc", "mac"]})
    )
    assert out["returncode"] == 0
    assert out["targets"] == ["pc", "mac"]
    # Ren'Py's distribute command is launcher-implemented: basedir is the
    # SDK's launcher dir; the project path is a positional arg; each
    # `--package` is repeated, not joined with commas.
    assert captured["basedir"] == cfg.sdk_root / "launcher"
    assert captured["args"] == (
        "distribute",
        str(cfg.project_root),
        "--package",
        "pc",
        "--package",
        "mac",
    )
    # Distribute gets the longer 10-minute ceiling.
    assert captured["timeout"] == 600.0


async def test_build_distribution_rejects_empty_targets(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("build_distribution", {"targets": []}))
    assert "error" in out


async def test_build_distribution_rejects_unsafe_target(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("build_distribution", {"targets": ["pc; rm -rf /"]}))
    assert "error" in out
