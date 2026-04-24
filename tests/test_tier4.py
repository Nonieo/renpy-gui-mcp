"""Tier 4 — escape-hatch tools. Each test gets a per-test fixture copy."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import tier1_read, tier4_escape
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT, parse


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[ServerConfig, ToolRegistry, ProjectIndex]:
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(
        project_root=proj.resolve(),
        sdk_root=SDK_ROOT,
        tiers=frozenset({1, 2, 3, 4}),
    )
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier4_escape.register(reg, cfg, idx)
    return cfg, reg, idx


# ---------- apply_unified_diff --------------------------------------------------


async def test_apply_unified_diff_modifies_existing_file(workspace):
    cfg, reg, _ = workspace
    diff = (
        "--- a/game/script.rpy\n"
        "+++ b/game/script.rpy\n"
        "@@ -1,4 +1,4 @@\n"
        "-## script.rpy — entry point for the fixture VN.\n"
        "+## script.rpy — entry point for the fixture VN (patched).\n"
        " ##\n"
        " ## Two characters, a branching menu, an image alias, and an audio play.\n"
        " ## Deliberately small but exercises every read-tool path.\n"
    )
    out = parse(await reg.call("apply_unified_diff", {"diff": diff}))
    assert out["summary"] == "applied diff to 1 file(s)"
    assert len(out["results"]) == 1
    script = (cfg.project_root / "game/script.rpy").read_text(encoding="utf-8")
    assert script.startswith("## script.rpy — entry point for the fixture VN (patched).\n")


async def test_apply_unified_diff_rejects_context_mismatch(workspace):
    _, reg, _ = workspace
    diff = (
        "--- a/game/script.rpy\n"
        "+++ b/game/script.rpy\n"
        "@@ -1,2 +1,2 @@\n"
        "-## this line is not actually in the file\n"
        "+## replaced\n"
        " ##\n"
    )
    out = parse(await reg.call("apply_unified_diff", {"diff": diff}))
    assert "context does not match" in out["error"]


async def test_apply_unified_diff_rejects_path_escape(workspace):
    _, reg, _ = workspace
    diff = (
        "--- a/../escape.rpy\n"
        "+++ b/../escape.rpy\n"
        "@@ -0,0 +1,1 @@\n"
        "+hello\n"
    )
    out = parse(await reg.call("apply_unified_diff", {"diff": diff}))
    assert "error" in out


async def test_apply_unified_diff_rejects_deletion(workspace):
    _, reg, _ = workspace
    diff = (
        "--- a/game/script.rpy\n"
        "+++ /dev/null\n"
        "@@ -1,1 +0,0 @@\n"
        "-anything\n"
    )
    out = parse(await reg.call("apply_unified_diff", {"diff": diff}))
    assert "deletion" in out["error"].lower()


async def test_apply_unified_diff_creates_new_file(workspace):
    cfg, reg, _ = workspace
    diff = (
        "--- /dev/null\n"
        "+++ b/game/extra.rpy\n"
        "@@ -0,0 +1,3 @@\n"
        "+# net new file\n"
        "+define x = 1\n"
        "+define y = 2\n"
    )
    out = parse(await reg.call("apply_unified_diff", {"diff": diff}))
    assert out["summary"] == "applied diff to 1 file(s)"
    created = (cfg.project_root / "game/extra.rpy").read_text(encoding="utf-8")
    assert "define x = 1" in created
    assert "define y = 2" in created


async def test_apply_unified_diff_rejects_creation_over_existing(workspace):
    _, reg, _ = workspace
    diff = (
        "--- /dev/null\n"
        "+++ b/game/script.rpy\n"
        "@@ -0,0 +1,1 @@\n"
        "+hello\n"
    )
    out = parse(await reg.call("apply_unified_diff", {"diff": diff}))
    assert "already exists" in out["error"]


async def test_apply_unified_diff_rejects_empty_input(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("apply_unified_diff", {"diff": "   "}))
    assert "non-empty string" in out["error"]


async def test_apply_unified_diff_rejects_ambiguous_hunk(workspace):
    cfg, reg, _ = workspace
    # Seed a file where a single-line hunk context appears twice so the
    # strict matcher has to refuse instead of guessing.
    target = cfg.project_root / "game/dupes.rpy"
    target.write_text("pass\npass\n", encoding="utf-8")
    diff = (
        "--- a/game/dupes.rpy\n"
        "+++ b/game/dupes.rpy\n"
        "@@ -1,1 +1,1 @@\n"
        "-pass\n"
        "+continue\n"
    )
    out = parse(await reg.call("apply_unified_diff", {"diff": diff}))
    assert "ambiguous" in out["error"]


# ---------- exec_python_in_init -------------------------------------------------


async def test_exec_python_in_init_appends_block(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "exec_python_in_init",
            {"code": "store.custom_flag = True\nstore.other = 42"},
        )
    )
    assert "appended `init python:` block" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text(encoding="utf-8")
    assert "init python:" in text
    assert "    store.custom_flag = True" in text
    assert "    store.other = 42" in text


async def test_exec_python_in_init_respects_priority(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "exec_python_in_init",
            {"code": "pass", "priority": -100},
        )
    )
    assert "error" not in out
    text = (cfg.project_root / "game/script.rpy").read_text(encoding="utf-8")
    assert "init -100 python:" in text


async def test_exec_python_in_init_rejects_bad_syntax(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call("exec_python_in_init", {"code": "def bad(:\n    pass\n"})
    )
    assert "failed to parse" in out["error"]


async def test_exec_python_in_init_rejects_non_rpy_target(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "exec_python_in_init",
            {"code": "pass", "file": "game/options.txt"},
        )
    )
    assert ".rpy" in out["error"]


async def test_exec_python_in_init_rejects_path_escape(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "exec_python_in_init",
            {"code": "pass", "file": "../escape.rpy"},
        )
    )
    assert "error" in out
