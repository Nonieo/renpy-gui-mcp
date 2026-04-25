"""Pure-logic tests for the RPBuilder launcher.

The Tk window and terminal prompts are interactive surfaces that
require a display or a TTY; this file covers the parts that don't —
config load/save, validation predicates, recent-projects bookkeeping,
and the `scaffold_empty_project` idempotency.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from renpy_mcp_gui import launcher as L


@pytest.fixture
def isolated_config(monkeypatch, tmp_path: Path) -> Path:
    """Redirect launcher.config_path() at a tmp file so tests don't touch
    the real ~/.config or %APPDATA%."""
    target = tmp_path / "launcher.json"
    monkeypatch.setattr(L, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(L, "config_path", lambda: target)
    return target


# ---------- config persistence -----------------------------------------------


def test_load_returns_defaults_when_missing(isolated_config):
    cfg = L.LauncherConfig.load()
    assert cfg.sdk_path is None
    assert cfg.recent_projects == []


def test_save_then_load_round_trip(isolated_config, tmp_path):
    cfg = L.LauncherConfig(sdk_path=str(tmp_path), recent_projects=["/a", "/b"])
    cfg.save()
    again = L.LauncherConfig.load()
    assert again.sdk_path == str(tmp_path)
    assert again.recent_projects == ["/a", "/b"]


def test_load_tolerates_corrupt_json(isolated_config):
    isolated_config.write_text("{not json", encoding="utf-8")
    cfg = L.LauncherConfig.load()
    assert cfg.sdk_path is None and cfg.recent_projects == []


def test_remember_project_dedupes_and_caps(isolated_config, tmp_path):
    cfg = L.LauncherConfig()
    # Add 12 distinct paths; only the most-recent 10 should remain.
    for i in range(12):
        cfg.remember_project(str(tmp_path / f"p{i}"))
    assert len(cfg.recent_projects) == L.RECENT_LIMIT
    # Most-recent first.
    assert cfg.recent_projects[0] == str((tmp_path / "p11").resolve())


def test_remember_project_moves_existing_to_front(isolated_config, tmp_path):
    cfg = L.LauncherConfig()
    cfg.remember_project(str(tmp_path / "a"))
    cfg.remember_project(str(tmp_path / "b"))
    cfg.remember_project(str(tmp_path / "a"))  # re-pick `a`
    assert cfg.recent_projects[0] == str((tmp_path / "a").resolve())
    assert cfg.recent_projects.count(str((tmp_path / "a").resolve())) == 1


# ---------- validation predicates --------------------------------------------


def test_validate_sdk_requires_launcher_file(tmp_path):
    fake_sdk = tmp_path / "fake_sdk"
    fake_sdk.mkdir()
    assert L.validate_sdk(str(fake_sdk)) is False
    (fake_sdk / L.sdk_launcher_filename()).write_text("#!/bin/sh\n", encoding="utf-8")
    assert L.validate_sdk(str(fake_sdk)) is True


def test_validate_sdk_handles_none_and_missing_dir():
    assert L.validate_sdk(None) is False
    assert L.validate_sdk("") is False
    assert L.validate_sdk("/definitely/does/not/exist") is False


def test_validate_project_requires_game_subdir(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    assert L.validate_project(str(proj)) is False
    (proj / "game").mkdir()
    assert L.validate_project(str(proj)) is True


# ---------- scaffold_empty_project idempotency -------------------------------


def test_scaffold_empty_project_creates_minimum(tmp_path):
    target = tmp_path / "fresh"
    L.scaffold_empty_project(target)
    assert (target / "game" / "script.rpy").is_file()
    assert L.validate_project(str(target)) is True


def test_scaffold_empty_project_preserves_existing_script(tmp_path):
    target = tmp_path / "preserved"
    (target / "game").mkdir(parents=True)
    sentinel = "label start:\n    \"Existing — do not clobber.\"\n    return\n"
    (target / "game" / "script.rpy").write_text(sentinel, encoding="utf-8")
    L.scaffold_empty_project(target)
    assert (target / "game" / "script.rpy").read_text() == sentinel
