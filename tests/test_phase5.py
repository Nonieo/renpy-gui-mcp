"""Phase 5 tests — `warp_to` + `set_drafting_mode`.

Subprocess spawns are mocked the same way `test_lifecycle.py` does:
the asyncio argv-list spawn API is monkeypatched to start a benign
`sleep` instead of `renpy.sh`. That lets us verify the flag handling,
temp-file write paths, and stop_preview cleanup without ever needing a
real Ren'Py SDK.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import lifecycle
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT


def _parse(content_list):
    assert len(content_list) == 1
    return json.loads(content_list[0].text)


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[ServerConfig, ToolRegistry, ProjectIndex]:
    """Per-test fixture copy with the lifecycle tools registered."""
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    lifecycle.register(reg, cfg, idx)
    # Reset module state so tests don't leak previews between cases.
    lifecycle._preview_proc = None  # type: ignore[attr-defined]
    lifecycle._warp_temp_active = False  # type: ignore[attr-defined]
    return cfg, reg, idx


def _patch_subprocess(monkeypatch):
    """Replace SDK launch with a benign long-running command."""
    real_create = asyncio.create_subprocess_exec

    async def fake(*_cmd, **kwargs):
        return await real_create("sleep", "30", **kwargs)

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake)


# ---------- warp_to validation -------------------------------------------------


async def test_warp_to_rejects_unknown_label(workspace):
    _, reg, _ = workspace
    out = _parse(await reg.call("warp_to", {"label": "nowhere_label"}))
    assert "error" in out
    assert "no such label" in out["error"]


async def test_warp_to_rejects_existing_temp_file(workspace):
    cfg, reg, _ = workspace
    (cfg.project_root / "game" / "_ide_after_warp.rpy").write_text(
        "label after_warp:\n    return\n"
    )
    out = _parse(await reg.call("warp_to", {"label": "start"}))
    assert "error" in out
    assert "_ide_after_warp.rpy" in out["error"]


async def test_warp_to_rejects_user_after_warp_label(workspace):
    cfg, reg, idx = workspace
    # Add a user-authored after_warp label outside the temp filename, so
    # the index sees it but the temp-file precheck doesn't trip first.
    (cfg.project_root / "game" / "user_hook.rpy").write_text(
        "label after_warp:\n    return\n"
    )
    idx.refresh()
    out = _parse(await reg.call("warp_to", {"label": "start"}))
    assert "error" in out
    assert "after_warp" in out["error"]


async def test_warp_to_rejects_invalid_override_name(workspace):
    _, reg, _ = workspace
    out = _parse(
        await reg.call(
            "warp_to",
            {"label": "start", "overrides": {"not a name!": 1}},
        )
    )
    assert "error" in out


async def test_warp_to_rejects_unsupported_override_type(workspace):
    _, reg, _ = workspace
    out = _parse(
        await reg.call(
            "warp_to",
            {"label": "start", "overrides": {"tags": ["a", "b"]}},
        )
    )
    assert "error" in out


# ---------- warp_to happy path -------------------------------------------------


async def test_warp_to_writes_temp_and_spawns(workspace, monkeypatch):
    cfg, reg, _ = workspace
    _patch_subprocess(monkeypatch)
    out = _parse(
        await reg.call(
            "warp_to",
            {
                "label": "cafe_scene",
                "overrides": {
                    "trust_mei": 3,
                    "knows_diary": True,
                    "innkeeper_alibi": "sleeping",
                    "weight": 1.5,
                    "ghost": None,
                },
            },
        )
    )
    assert out["warped"] is True
    assert out["label"] == "cafe_scene"
    assert out["temp_file"] == "game/_ide_after_warp.rpy"
    assert isinstance(out["pid"], int)

    body = (cfg.project_root / "game" / "_ide_after_warp.rpy").read_text()
    assert "label after_warp:" in body
    assert "$ trust_mei = 3" in body
    assert "$ knows_diary = True" in body
    assert '$ innkeeper_alibi = "sleeping"' in body
    assert "$ weight = 1.5" in body
    assert "$ ghost = None" in body
    assert body.rstrip().endswith("return")

    # Status reflects warp-active state.
    status = _parse(await reg.call("get_preview_status", {}))
    assert status["running"] is True
    assert status["warp_active"] is True


async def test_warp_to_refuses_when_preview_running(workspace, monkeypatch):
    _, reg, _ = workspace
    _patch_subprocess(monkeypatch)
    first = _parse(await reg.call("launch_preview", {}))
    assert first["started"] is True
    out = _parse(await reg.call("warp_to", {"label": "start"}))
    assert "error" in out
    assert "already running" in out["error"]


# ---------- stop_preview cleans up after warp ----------------------------------


async def test_stop_preview_removes_warp_temp(workspace, monkeypatch):
    cfg, reg, _ = workspace
    _patch_subprocess(monkeypatch)
    await reg.call("warp_to", {"label": "start"})
    temp = cfg.project_root / "game" / "_ide_after_warp.rpy"
    assert temp.is_file()

    stopped = _parse(await reg.call("stop_preview", {}))
    assert stopped["stopped"] is True
    assert stopped["warp_temp_removed"] is True
    assert not temp.is_file()


async def test_stop_preview_when_idle_scrubs_stale_temp(workspace):
    cfg, reg, _ = workspace
    # Simulate a crashed prior run: temp file present, no live process.
    (cfg.project_root / "game" / "_ide_after_warp.rpy").write_text(
        "label after_warp:\n    return\n"
    )
    out = _parse(await reg.call("stop_preview", {}))
    assert out["running"] is False
    assert out["warp_temp_removed"] is True
    assert not (cfg.project_root / "game" / "_ide_after_warp.rpy").is_file()


# ---------- set_drafting_mode --------------------------------------------------


async def test_set_drafting_mode_off_when_no_file(workspace):
    _, reg, _ = workspace
    out = _parse(await reg.call("set_drafting_mode", {"on": False}))
    assert out["drafting"] is False
    assert out["removed"] is False


async def test_set_drafting_mode_clean_fixture_no_fallbacks(workspace):
    """Fixture project has no missing image refs — drafting file is empty of fallbacks."""
    cfg, reg, _ = workspace
    out = _parse(await reg.call("set_drafting_mode", {"on": True}))
    assert out["drafting"] is True
    assert out["fallbacks"] == []
    body = (cfg.project_root / "game" / "_ide_drafting.rpy").read_text()
    assert "Auto-generated" in body
    assert "image " not in body  # no fallback lines


async def test_set_drafting_mode_emits_fallbacks_for_missing_images(workspace):
    cfg, reg, idx = workspace
    (cfg.project_root / "game" / "broken.rpy").write_text(
        "label brokenscene:\n"
        "    scene bg ghost\n"
        "    show eileen amused\n"
        "    return\n"
    )
    idx.refresh()
    out = _parse(await reg.call("set_drafting_mode", {"on": True}))
    assert out["drafting"] is True
    assert "bg ghost" in out["fallbacks"]
    assert "eileen amused" in out["fallbacks"]
    body = (cfg.project_root / "game" / "_ide_drafting.rpy").read_text()
    assert 'image bg ghost = Solid("#444444")' in body
    assert 'image eileen amused = Solid("#444444")' in body


async def test_set_drafting_mode_off_removes_file(workspace):
    cfg, reg, _ = workspace
    await reg.call("set_drafting_mode", {"on": True})
    target = cfg.project_root / "game" / "_ide_drafting.rpy"
    assert target.is_file()
    out = _parse(await reg.call("set_drafting_mode", {"on": False}))
    assert out["drafting"] is False
    assert out["removed"] is True
    assert not target.is_file()


async def test_set_drafting_mode_idempotent_on(workspace):
    """Two consecutive on-calls produce identical files (no spurious diff)."""
    cfg, reg, _ = workspace
    first = _parse(await reg.call("set_drafting_mode", {"on": True}))
    target = cfg.project_root / "game" / "_ide_drafting.rpy"
    mtime1 = target.stat().st_mtime_ns
    second = _parse(await reg.call("set_drafting_mode", {"on": True}))
    # apply_write detects no-op identical content and skips disk write.
    assert target.stat().st_mtime_ns == mtime1
    assert first["fallbacks"] == second["fallbacks"]
