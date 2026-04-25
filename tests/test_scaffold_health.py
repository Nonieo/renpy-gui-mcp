"""Tests for `project/scaffold_health.py` and the `repair_scaffold` tool.

The user's bug — lint passes but the built Linux distribution crashes
with `ModuleNotFoundError: gui7` — was caused by the SDK template's
`game/guisupport.rpy` doing a launcher-only `gui7` import at init 100.
A second issue, `build.name = "gui"` left in `options.rpy`, misnames
the artifact even when the build succeeds. Both are detected and
repaired here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project import scaffold_health
from renpy_mcp.project.scaffold import scaffold_project
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import tier1_read, tier2_write, tier3_intents
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT, parse


# ---------- diagnose() ---------------------------------------------------------


def _make_project(tmp_path: Path, *, with_guisupport_text: str | None = None,
                  with_options_build_name: str | None = None,
                  with_gui_uses_scale: bool = False) -> ServerConfig:
    proj = tmp_path / "tiny"
    (proj / "game").mkdir(parents=True)
    if with_guisupport_text is not None:
        (proj / "game" / "guisupport.rpy").write_text(with_guisupport_text, encoding="utf-8")
    if with_gui_uses_scale:
        (proj / "game" / "gui.rpy").write_text(
            "init python:\n    gui.init(1280, 720)\ndefine gui.text_size = gui.scale(22)\n",
            encoding="utf-8",
        )
    if with_options_build_name is not None:
        (proj / "game" / "options.rpy").write_text(
            f'define config.name = _("My Game")\n'
            f'define build.name = "{with_options_build_name}"\n',
            encoding="utf-8",
        )
    return ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)


def test_diagnose_clean_project(tmp_path):
    cfg = _make_project(tmp_path)
    assert scaffold_health.diagnose(cfg) == []


def test_diagnose_detects_gui7_import(tmp_path):
    cfg = _make_project(
        tmp_path,
        with_guisupport_text=(
            "init -100 python in gui:\n    def scale(n): return int(n)\n"
            "init 100 python in gui:\n    from gui7.parameters import GuiParameters\n"
        ),
    )
    rules = {i.rule for i in scaffold_health.diagnose(cfg)}
    assert "guisupport_imports_gui7" in rules


def test_diagnose_ignores_gui7_in_comments(tmp_path):
    """The minimum guisupport.rpy left by repair() mentions gui7 in a
    comment. That's NOT a real import — diagnose must not flag it."""
    cfg = _make_project(
        tmp_path,
        with_guisupport_text=scaffold_health.MIN_GUISUPPORT,
    )
    rules = {i.rule for i in scaffold_health.diagnose(cfg)}
    assert "guisupport_imports_gui7" not in rules


def test_diagnose_detects_missing_scale_helper(tmp_path):
    """When guisupport.rpy is gone but gui.rpy still calls gui.scale,
    the project will crash on init."""
    cfg = _make_project(tmp_path, with_gui_uses_scale=True)
    rules = {i.rule for i in scaffold_health.diagnose(cfg)}
    assert "guisupport_missing_scale_helper" in rules


def test_diagnose_detects_build_name_gui(tmp_path):
    cfg = _make_project(tmp_path, with_options_build_name="gui")
    rules = {i.rule for i in scaffold_health.diagnose(cfg)}
    assert "build_name_is_gui" in rules


def test_diagnose_skips_already_fixed_build_name(tmp_path):
    cfg = _make_project(tmp_path, with_options_build_name="my_game")
    rules = {i.rule for i in scaffold_health.diagnose(cfg)}
    assert "build_name_is_gui" not in rules


# ---------- repair() rebuilds the slim guisupport ----------------------------


def test_repair_rewrites_guisupport(tmp_path):
    cfg = _make_project(
        tmp_path,
        with_guisupport_text=(
            "init -100 python in gui:\n    def scale(n): return int(n)\n"
            "init 100 python in gui:\n    from gui7.parameters import GuiParameters\n"
        ),
    )
    report = scaffold_health.repair(cfg, ProjectIndex(cfg))
    actions = {a["rule"]: a for a in report["actions"]}
    assert actions["guisupport_imports_gui7"]["outcome"] == "rewrote"
    new_text = (cfg.project_root / "game" / "guisupport.rpy").read_text(encoding="utf-8")
    assert new_text == scaffold_health.MIN_GUISUPPORT


def test_repair_creates_missing_guisupport(tmp_path):
    cfg = _make_project(tmp_path, with_gui_uses_scale=True)
    report = scaffold_health.repair(cfg, ProjectIndex(cfg))
    assert any(
        a["rule"] == "guisupport_missing_scale_helper" and a["outcome"] == "created"
        for a in report["actions"]
    )
    new_text = (cfg.project_root / "game" / "guisupport.rpy").read_text(encoding="utf-8")
    assert "def scale" in new_text
    assert "from gui7" not in new_text


def test_repair_rewrites_build_name(tmp_path):
    cfg = _make_project(tmp_path, with_options_build_name="gui")
    # Need an options.rpy with config.name so the slug is derivable.
    options = cfg.project_root / "game" / "options.rpy"
    options.write_text(
        'define config.name = _("Pirate Tale")\n'
        'define build.name = "gui"\n',
        encoding="utf-8",
    )
    report = scaffold_health.repair(cfg, ProjectIndex(cfg))
    rewrote = next(a for a in report["actions"] if a["rule"] == "build_name_is_gui")
    assert rewrote["outcome"] == "rewrote"
    assert rewrote["build_name"] == "pirate_tale"
    after = options.read_text(encoding="utf-8")
    assert 'build.name = "pirate_tale"' in after


def test_repair_is_idempotent(tmp_path):
    """Running repair on a clean project returns no actions."""
    cfg = _make_project(tmp_path)
    report = scaffold_health.repair(cfg, ProjectIndex(cfg))
    assert report["issues"] == []
    assert report["actions"] == []


# ---------- new scaffolds ship the slim version ------------------------------


def test_new_scaffold_does_not_carry_gui7_import(tmp_path):
    """The scaffolded `guisupport.rpy` must come out clean, even though
    we copy the SDK template that includes the broken version."""
    fake_sdk = tmp_path / "fake_sdk"
    template = fake_sdk / "gui" / "game"
    template.mkdir(parents=True)
    (template / "script.rpy").write_text("label start:\n    return\n")
    (template / "options.rpy").write_text(
        'define config.name = _("My Game")\n'
        'define build.name = "gui"\n'
    )
    (template / "guisupport.rpy").write_text(
        # The exact pattern the SDK ships, including the broken import.
        "init -100 python in gui:\n    def scale(n): return int(n)\n"
        "init 100 python in gui:\n    from gui7.parameters import GuiParameters\n"
        "    generate_gui(p)\n"
    )

    proj = tmp_path / "scaffolded"
    scaffold_project(proj, display_name="Pirate Tale", sdk_root=fake_sdk)
    out = (proj / "game" / "guisupport.rpy").read_text(encoding="utf-8")
    assert "from gui7" not in out
    assert "def scale" in out


# ---------- repair_scaffold Tier 3 tool --------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[ServerConfig, ToolRegistry, ProjectIndex]:
    """Per-test fixture project copy with all tiers registered."""
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier2_write.register(reg, cfg, idx)
    tier3_intents.register(reg, cfg, idx)
    return cfg, reg, idx


async def test_repair_scaffold_tool_clean(workspace):
    """Fixture project is healthy → no repairs needed."""
    _, reg, _ = workspace
    out = parse(await reg.call("repair_scaffold", {}))
    assert out["summary"] == "scaffold is clean"
    assert out["issues"] == []
    assert out["actions"] == []


async def test_repair_scaffold_tool_fixes_broken_project(workspace):
    cfg, reg, idx = workspace
    # Seed both bugs.
    (cfg.project_root / "game" / "guisupport.rpy").write_text(
        "init -100 python in gui:\n    def scale(n): return int(n)\n"
        "init 100 python in gui:\n    from gui7.parameters import GuiParameters\n",
        encoding="utf-8",
    )
    options = cfg.project_root / "game" / "options.rpy"
    options.write_text(
        options.read_text(encoding="utf-8").replace(
            'define build.name = "tiny_project"',
            'define build.name = "gui"',
        ) if 'build.name' in options.read_text() else
        options.read_text() + '\ndefine build.name = "gui"\n',
        encoding="utf-8",
    )
    idx.refresh()
    out = parse(await reg.call("repair_scaffold", {}))
    assert "applied" in out["summary"]
    rules = {a["rule"] for a in out["actions"]}
    assert "guisupport_imports_gui7" in rules