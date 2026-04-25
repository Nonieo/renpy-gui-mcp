"""Tests for Phase 1b: asset/screen/reachability diagnostics + suppression."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.diagnostics import (
    SIDECAR_DIR,
    SIDECAR_FILENAME,
    DiagnosticsError,
    filter_diagnostics,
    read_ignored,
    set_ignored,
)
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


# ---------- find_missing_assets ------------------------------------------------


async def test_find_missing_assets_clean_fixture(registry):
    out = parse(await registry.call("find_missing_assets", {}))
    assert out["rule"] == "missing_asset"
    assert out["count"] == 0


async def test_find_missing_assets_flags_missing_image(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label visit:\n"
        "    scene bg nonexistent\n"
        "    return\n"
    )
    idx.refresh()
    out = parse(await reg.call("find_missing_assets", {}))
    assert out["count"] == 1
    diag = out["diagnostics"][0]
    assert diag["rule"] == "missing_asset"
    assert diag["severity"] == "error"
    assert diag["label"] == "visit"
    assert "nonexistent" in diag["message"]


async def test_find_missing_assets_accepts_at_and_with_modifiers(workspace):
    """`scene bg park at left with dissolve` should still resolve to `bg park`."""
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label visit:\n"
        "    scene bg park at left with dissolve\n"
        "    show eileen happy at right\n"
        "    return\n"
    )
    idx.refresh()
    out = parse(await reg.call("find_missing_assets", {}))
    # `bg park` is an alias in the fixture; `eileen happy` is auto-named
    # from `images/eileen_happy.png`.
    assert out["count"] == 0


async def test_find_missing_assets_flags_missing_audio(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        'label visit:\n'
        '    play music "audio/never_recorded.ogg"\n'
        '    return\n'
    )
    idx.refresh()
    out = parse(await reg.call("find_missing_assets", {}))
    assert out["count"] == 1
    assert "never_recorded" in out["diagnostics"][0]["message"]


# ---------- find_undefined_screens ---------------------------------------------


async def test_find_undefined_screens_clean_fixture(registry):
    out = parse(await registry.call("find_undefined_screens", {}))
    assert out["count"] == 0


async def test_find_undefined_screens_flags_show_screen(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label visit:\n"
        "    show screen ghost_overlay\n"
        "    return\n"
    )
    idx.refresh()
    out = parse(await reg.call("find_undefined_screens", {}))
    assert out["count"] == 1
    diag = out["diagnostics"][0]
    assert diag["rule"] == "undefined_screen"
    assert "ghost_overlay" in diag["message"]


async def test_find_undefined_screens_flags_call_screen(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label visit:\n"
        "    call screen pause_menu\n"
        "    return\n"
    )
    idx.refresh()
    out = parse(await reg.call("find_undefined_screens", {}))
    assert out["count"] == 1
    assert "pause_menu" in out["diagnostics"][0]["message"]


# ---------- find_unreachable_labels --------------------------------------------


async def test_find_unreachable_labels_clean_fixture(registry):
    """Every fixture label is reachable from `start`."""
    out = parse(await registry.call("find_unreachable_labels", {}))
    assert out["count"] == 0


async def test_find_unreachable_labels_flags_orphan(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label orphan_draft:\n"
        "    \"nobody calls me.\"\n"
        "    return\n"
    )
    idx.refresh()
    out = parse(await reg.call("find_unreachable_labels", {}))
    assert out["count"] == 1
    diag = out["diagnostics"][0]
    assert diag["rule"] == "unreachable_label"
    assert diag["severity"] == "warning"
    assert diag["label"] == "orphan_draft"


async def test_find_unreachable_labels_treats_init_prefix_as_root(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label init_setup:\n"
        "    \"engine entry point.\"\n"
        "    return\n"
    )
    idx.refresh()
    out = parse(await reg.call("find_unreachable_labels", {}))
    assert out["count"] == 0


# ---------- ignored_diagnostics sidecar ----------------------------------------


async def test_read_ignored_diagnostics_empty_when_no_sidecar(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("read_ignored_diagnostics", {}))
    assert out["count"] == 0
    assert out["ignored"] == []


async def test_set_ignored_diagnostics_round_trip(workspace):
    cfg, reg, _ = workspace
    entries = [{"rule": "unused_character", "file": "game/script.rpy"}]
    out = parse(await reg.call("set_ignored_diagnostics", {"entries": entries}))
    assert out["count"] == 1
    sidecar = cfg.project_root / SIDECAR_DIR / SIDECAR_FILENAME
    assert sidecar.is_file()
    on_disk = json.loads(sidecar.read_text())
    assert on_disk["ignored"] == entries
    read_back = parse(await reg.call("read_ignored_diagnostics", {}))
    assert read_back["ignored"] == entries


async def test_set_ignored_diagnostics_dedupes_appends(workspace):
    _, reg, _ = workspace
    entry = {"rule": "invalid_jump", "label": "wip"}
    await reg.call("set_ignored_diagnostics", {"entries": [entry]})
    await reg.call("set_ignored_diagnostics", {"entries": [entry, entry]})
    out = parse(await reg.call("read_ignored_diagnostics", {}))
    assert out["count"] == 1


async def test_set_ignored_diagnostics_replace(workspace):
    _, reg, _ = workspace
    await reg.call(
        "set_ignored_diagnostics",
        {"entries": [{"rule": "invalid_jump", "label": "old"}]},
    )
    await reg.call(
        "set_ignored_diagnostics",
        {"entries": [{"rule": "unused_character"}], "replace": True},
    )
    out = parse(await reg.call("read_ignored_diagnostics", {}))
    assert out["count"] == 1
    assert out["ignored"][0]["rule"] == "unused_character"


async def test_set_ignored_diagnostics_rejects_unknown_field(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "set_ignored_diagnostics",
            {"entries": [{"rule": "x", "severity": "error"}]},
        )
    )
    assert "error" in out


async def test_read_ignored_diagnostics_rejects_malformed(workspace):
    cfg, reg, _ = workspace
    sidecar_dir = cfg.project_root / SIDECAR_DIR
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    (sidecar_dir / SIDECAR_FILENAME).write_text("[ not json")
    out = parse(await reg.call("read_ignored_diagnostics", {}))
    assert "error" in out


# ---------- end-to-end suppression in find_* tools -----------------------------


async def test_find_invalid_jumps_respects_suppression(workspace):
    cfg, reg, idx = workspace
    extra = cfg.project_root / "game" / "extra.rpy"
    extra.write_text(
        "label exper:\n"
        "    jump nowhere\n"
    )
    idx.refresh()
    # Without suppression, one diagnostic.
    before = parse(await reg.call("find_invalid_jumps", {}))
    assert before["count"] == 1
    assert before["suppressed_count"] == 0
    # Suppress that one occurrence by file+line.
    diag = before["diagnostics"][0]
    await reg.call(
        "set_ignored_diagnostics",
        {
            "entries": [
                {"rule": "invalid_jump", "file": diag["file"], "line": diag["line"]}
            ]
        },
    )
    after = parse(await reg.call("find_invalid_jumps", {}))
    assert after["count"] == 0
    assert after["suppressed_count"] == 1


async def test_diagnostic_call_returns_meta_warning_on_malformed_sidecar(workspace):
    cfg, reg, _ = workspace
    sidecar_dir = cfg.project_root / SIDECAR_DIR
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    (sidecar_dir / SIDECAR_FILENAME).write_text("not json")
    # The diagnostic itself should still return — with an extra
    # `sidecar_warning` field flagging the malformed sidecar.
    out = parse(await reg.call("find_invalid_jumps", {}))
    assert "sidecar_warning" in out
    assert "malformed" in out["sidecar_warning"]
    # Diagnostics aren't filtered when the sidecar can't be parsed.
    assert out["suppressed_count"] == 0


# ---------- direct unit-level filter helper ------------------------------------


def test_filter_diagnostics_pattern_matching():
    diagnostics = [
        {"rule": "invalid_jump", "file": "a.rpy", "line": 3, "label": "x"},
        {"rule": "invalid_jump", "file": "b.rpy", "line": 7, "label": "y"},
        {"rule": "unused_character", "file": "a.rpy", "line": 1, "label": None},
    ]
    # Suppress all of one rule.
    kept, n = filter_diagnostics(diagnostics, [{"rule": "invalid_jump"}])
    assert n == 2 and len(kept) == 1
    # Suppress one occurrence.
    kept, n = filter_diagnostics(
        diagnostics, [{"rule": "invalid_jump", "file": "b.rpy", "line": 7}]
    )
    assert n == 1 and len(kept) == 2
    # No match → no suppression.
    kept, n = filter_diagnostics(
        diagnostics, [{"rule": "invalid_jump", "file": "z.rpy"}]
    )
    assert n == 0 and len(kept) == 3


def test_set_ignored_no_op_skips_disk_write(workspace):
    cfg, _, _ = workspace
    entries = [{"rule": "unused_character"}]
    set_ignored(cfg, entries)
    sidecar = cfg.project_root / SIDECAR_DIR / SIDECAR_FILENAME
    first_mtime = sidecar.stat().st_mtime_ns
    set_ignored(cfg, entries)  # identical → no rewrite
    assert sidecar.stat().st_mtime_ns == first_mtime


def test_set_ignored_rejects_missing_rule(workspace):
    cfg, _, _ = workspace
    with pytest.raises(DiagnosticsError):
        set_ignored(cfg, [{"file": "x.rpy"}])
