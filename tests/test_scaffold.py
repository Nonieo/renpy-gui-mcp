"""Tests for the scaffold helper + slugify.

``__main__`` uses these when ``--project`` is omitted so an empty cwd gets a
runnable starting state without explicit setup. The scaffold must stay
idempotent and produce Ren'Py-valid bytes.
"""

from __future__ import annotations

from pathlib import Path

from renpy_mcp.project.scaffold import scaffold_project, slugify


def test_slugify_common_inputs():
    assert slugify("Pirate Tale") == "pirate_tale"
    assert slugify("  hello-world  ") == "hello_world"
    assert slugify("!@#$%") == "project"
    assert slugify("MixedCase_123") == "mixedcase_123"


def test_scaffold_minimal_fallback(tmp_path: Path):
    """No SDK -> minimal skeleton still produces a runnable label start."""
    summary = scaffold_project(tmp_path / "empty", sdk_root=None)
    assert "minimal skeleton" in summary
    script = (tmp_path / "empty" / "game" / "script.rpy").read_text()
    assert "label start:" in script
    assert (tmp_path / "empty" / "game" / "images").is_dir()
    assert (tmp_path / "empty" / "game" / "audio").is_dir()


def test_scaffold_is_idempotent(tmp_path: Path):
    proj = tmp_path / "twice"
    scaffold_project(proj, sdk_root=None)
    before = (proj / "game" / "script.rpy").read_bytes()
    summary2 = scaffold_project(proj, sdk_root=None)
    assert "already scaffolded" in summary2
    assert (proj / "game" / "script.rpy").read_bytes() == before


def test_scaffold_prefers_sdk_template_when_available(tmp_path: Path):
    """Fake an SDK template and confirm scaffold picks it up."""
    fake_sdk = tmp_path / "fake_sdk"
    template = fake_sdk / "gui" / "game"
    template.mkdir(parents=True)
    (template / "script.rpy").write_text(
        "# sentinel from fake SDK template\nlabel start:\n    return\n"
    )
    (template / "testcases.rpy").write_text("# skip me\n")

    proj = tmp_path / "fresh"
    summary = scaffold_project(proj, display_name="Fresh", sdk_root=fake_sdk)
    assert "from SDK template" in summary
    assert "sentinel from fake SDK template" in (proj / "game" / "script.rpy").read_text()
    # testcases.rpy is deliberately skipped — it's the SDK's test-harness template.
    assert not (proj / "game" / "testcases.rpy").exists()


def test_scaffold_rewrites_config_and_build_name(tmp_path: Path):
    """SDK template ships with `build.name = "gui"`; scaffold must rewrite
    both config.name AND build.name so distribute artifacts pick up the
    actual project name (not the SDK launcher's name). build.name must
    be slug-safe so `build.directory_name` (which derives from it) doesn't
    contain spaces/colons/semicolons that Ren'Py distribute rejects.
    """
    fake_sdk = tmp_path / "fake_sdk"
    template = fake_sdk / "gui" / "game"
    template.mkdir(parents=True)
    (template / "script.rpy").write_text("label start:\n    return\n")
    (template / "options.rpy").write_text(
        '## options.rpy template\n'
        'define config.name = _("My Game")\n'
        'define config.version = "1.0"\n'
        'define build.name = "gui"\n'
    )

    # display_name with a space — config.name keeps it, build.name slugifies.
    proj = tmp_path / "shipping_test"
    scaffold_project(proj, display_name="Pirate Tale", sdk_root=fake_sdk)
    options = (proj / "game" / "options.rpy").read_text()
    assert 'define config.name = _("Pirate Tale")' in options
    # build.name must be slug-safe — Ren'Py distribute crashes on
    # `build.directory_name` containing spaces.
    assert 'define build.name = "pirate_tale"' in options
    assert 'build.name = "Pirate Tale"' not in options
    assert 'build.name = "gui"' not in options
