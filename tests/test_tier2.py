"""Tier 2 tests use a per-test copy of the fixture so writes don't leak."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.project.writer import WriteRejected, apply_write
from renpy_mcp.tools import tier1_read, tier2_write
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT, parse


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[ServerConfig, ToolRegistry, ProjectIndex]:
    """Copy the fixture into tmp_path and return a config + registry pointing at it."""
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier2_write.register(reg, cfg, idx)
    return cfg, reg, idx


# ---------- writer foundation ---------------------------------------------------


def test_writer_normalizes_tabs(workspace):
    cfg, _, idx = workspace
    rel = "game/script.rpy"
    target = cfg.project_root / rel
    original = target.read_text()
    polluted = original + "\nlabel new_one:\n\tpass\n"
    result = apply_write(cfg, idx, rel, polluted)
    assert any("converted leading tab" in w for w in result.warnings)
    written = target.read_text()
    assert "\t" not in written  # tabs were normalized away


def test_writer_blocks_label_collision(tmp_path):
    """A new file that re-declares an existing label is rejected."""
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(project_root=proj.resolve(), sdk_root=SDK_ROOT)
    idx = ProjectIndex(cfg)
    with pytest.raises(WriteRejected, match="already exist"):
        apply_write(cfg, idx, "game/02_extra.rpy", "label start:\n    return\n")


def test_writer_rejects_path_traversal(workspace):
    cfg, _, idx = workspace
    with pytest.raises(WriteRejected, match="escapes project_root"):
        apply_write(cfg, idx, "../escape.rpy", "label e:\n    return\n")


def test_writer_rejects_reserved_filename(workspace):
    cfg, _, idx = workspace
    with pytest.raises(WriteRejected, match="reserved"):
        apply_write(cfg, idx, "game/00_reserved.rpy", "label foo:\n    return\n")


def test_writer_no_op_on_identical_content(workspace):
    cfg, _, idx = workspace
    rel = "game/script.rpy"
    target = cfg.project_root / rel
    result = apply_write(cfg, idx, rel, target.read_text())
    assert result.no_op is True
    assert result.diff == ""


def test_writer_cleans_rpyc_shadow(workspace):
    cfg, _, idx = workspace
    rel = "game/script.rpy"
    shadow = (cfg.project_root / rel).with_suffix(".rpyc")
    shadow.write_bytes(b"stale")
    target = cfg.project_root / rel
    result = apply_write(cfg, idx, rel, target.read_text() + "\n# trailing comment\n")
    assert "script.rpyc" in result.rpyc_cleaned
    assert not shadow.exists()


# ---------- add_label -----------------------------------------------------------


async def test_add_label_appends_block(workspace):
    cfg, reg, idx = workspace
    out = parse(await reg.call("add_label", {"name": "new_room", "body": ['e "Hello!"', "return"]}))
    assert out["summary"].startswith("added label `new_room`")
    assert "+label new_room:" in out["diff"]
    assert idx.snapshot().labels[-1].name == "new_room"


async def test_add_label_rejects_collision(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_label", {"name": "start"}))
    assert "already exists" in out["error"]


async def test_add_label_rejects_invalid_identifier(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_label", {"name": "1bad name"}))
    assert "not a valid Python identifier" in out["error"]


async def test_add_label_rejects_reserved_keyword(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_label", {"name": "init"}))
    assert "reserved" in out["error"]


async def test_add_label_default_pass_body(workspace):
    cfg, reg, _ = workspace
    await reg.call("add_label", {"name": "stub_label"})
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "label stub_label:\n    pass" in text


# ---------- add_say -------------------------------------------------------------


async def test_add_say_with_character(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("add_say", {"label": "park_scene", "character": "e", "text": "Quiet."}))
    assert "appended say-statement" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    park_block = text.split("label park_scene:")[1].split("label ")[0]
    # Reachability: the new line must appear BEFORE park_scene's `jump ending` terminator.
    assert park_block.index('e "Quiet."') < park_block.index("jump ending")


async def test_add_say_escapes_metacharacters(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_say",
        {"label": "park_scene", "character": "e", "text": "She said {hi} and [bye]."},
    )
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert '"She said {{hi}} and [[bye]]."' in text


async def test_add_say_raw_skips_escape(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_say",
        {"label": "park_scene", "character": "e", "text": "Pre-{{escaped}}", "raw": True},
    )
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert '"Pre-{{escaped}}"' in text


async def test_add_say_rejects_unknown_character(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_say", {"label": "park_scene", "character": "ghost", "text": "hi"}))
    assert "unknown character var" in out["error"]
    assert set(out["known"]) == {"e", "m"}


async def test_add_say_narration_no_character(workspace):
    cfg, reg, _ = workspace
    await reg.call("add_say", {"label": "park_scene", "text": "Narration."})
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert '\n    "Narration."' in text


# ---------- add_jump ------------------------------------------------------------


async def test_add_jump_validates_target(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("add_jump", {"label": "park_scene", "target": "missing"}))
    assert "does not exist" in out["error"]


async def test_add_jump_refuses_double_terminator(workspace):
    """park_scene already ends with `jump ending`; a second jump must be refused."""
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_jump",
            {"label": "park_scene", "target": "future_label", "validate_target": False},
        )
    )
    assert "already terminates" in out["error"]
    assert "replace_terminator" in out["error"]


async def test_add_jump_allows_forward_reference_via_replace(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_jump",
            {
                "label": "park_scene",
                "target": "future_label",
                "validate_target": False,
                "replace_terminator": True,
            },
        )
    )
    assert "replaced terminator of `park_scene`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    park_block = text.split("label park_scene:")[1].split("label ")[0]
    assert "    jump future_label" in park_block
    assert "    jump ending" not in park_block  # old terminator was overwritten


# ---------- set_variable_default -----------------------------------------------


async def test_set_variable_default_updates_existing(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("set_variable_default", {"name": "affection_mei", "value": "5"}))
    assert "updated `default affection_mei`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "default affection_mei = 5" in text


async def test_set_variable_default_creates_new(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("set_variable_default", {"name": "new_flag", "value": "True"}))
    assert "added `default new_flag = True`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "default new_flag = True" in text


# ---------- rename_label --------------------------------------------------------


async def test_rename_label_updates_decl_and_jumps(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("rename_label", {"old": "ending", "new": "epilogue"}))
    assert "renamed label `ending` -> `epilogue`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "label epilogue:" in text
    assert "jump epilogue" in text
    assert "ending" not in text  # all references rewritten


async def test_rename_label_rejects_existing_target(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("rename_label", {"old": "ending", "new": "start"}))
    assert "already exists" in out["error"]


async def test_rename_label_rejects_unknown_source(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("rename_label", {"old": "nope", "new": "fresh"}))
    assert "no such label" in out["error"]


# ---------- add_call ------------------------------------------------------------


async def test_add_call_appends_and_validates(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("add_call", {"label": "park_scene", "target": "ending"}))
    assert "added `call ending`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "    call ending" in text

    out = parse(await reg.call("add_call", {"label": "park_scene", "target": "missing_xyz"}))
    assert "does not exist" in out["error"]


# ---------- add_menu ------------------------------------------------------------


async def test_add_menu_emits_choices_with_indent(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_menu",
            {
                "label": "park_scene",
                "choices": [
                    {"text": "Stay", "body": ['e "ok"', "jump ending"]},
                    {"text": "Leave", "condition": "met_mei", "body": ["return"]},
                ],
            },
        )
    )
    assert "added menu with 2 choice(s)" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "    menu:" in text
    assert '        "Stay":' in text
    assert '        "Leave" if met_mei:' in text
    assert '            jump ending' in text


async def test_add_menu_escapes_text(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_menu",
        {"label": "park_scene", "choices": [{"text": "Pick {bold}", "body": ["return"]}]},
    )
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert '"Pick {{bold}}":' in text


# ---------- add_audio_play ------------------------------------------------------


async def test_add_audio_play_with_clauses(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_audio_play",
            {
                "label": "park_scene",
                "channel": "music",
                "asset": "audio/spring_theme.ogg",
                "loop": True,
                "fadein": 1.5,
            },
        )
    )
    assert "added `play music`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert 'play music "audio/spring_theme.ogg" fadein 1.5 loop' in text


async def test_add_audio_play_validates_asset(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_audio_play",
            {"label": "park_scene", "channel": "sound", "asset": "audio/missing.opus"},
        )
    )
    assert "asset file does not exist" in out["error"]


async def test_add_audio_play_skip_validation(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_audio_play",
            {
                "label": "park_scene",
                "channel": "sound",
                "asset": "audio/placeholder.opus",
                "validate_asset": False,
            },
        )
    )
    assert "summary" in out


# ---------- add_image_alias -----------------------------------------------------


async def test_add_image_alias_inserts_after_decls(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_image_alias",
            {"name": "bg rooftop", "asset": "images/park.png"},  # reuse existing asset
        )
    )
    assert "added `image bg rooftop`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert 'image bg rooftop = "images/park.png"' in text


async def test_add_image_alias_rejects_bad_name(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call("add_image_alias", {"name": "1bad", "asset": "images/park.png"})
    )
    assert "not a valid image name" in out["error"]


async def test_add_image_alias_validates_asset(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call("add_image_alias", {"name": "bg ghost", "asset": "images/missing.png"})
    )
    assert "asset file does not exist" in out["error"]


# ---------- add_character / update_character -----------------------------------


async def test_add_character_with_color_and_image(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_character",
            {
                "var": "n",
                "display_name": "Narrator",
                "color": "#888888",
                "image_tag": "n",
            },
        )
    )
    assert "defined character `n`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert 'define n = Character("Narrator", color="#888888", image="n")' in text


async def test_add_character_rejects_collision(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call("add_character", {"var": "e", "display_name": "Other"})
    )
    assert "already exists" in out["error"]


async def test_add_character_extra_kwargs(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_character",
        {
            "var": "z",
            "display_name": "Zed",
            "extra_kwargs": {"who_color": '"#ff0000"'},
        },
    )
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert 'define z = Character("Zed", who_color="#ff0000")' in text


async def test_update_character_color_only(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("update_character", {"var": "e", "color": "#ff8800"}))
    assert "updated character `e`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert 'color="#ff8800"' in text


async def test_update_character_display_name(workspace):
    cfg, reg, _ = workspace
    await reg.call("update_character", {"var": "m", "display_name": "Mei Chen"})
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert 'define m = Character("Mei Chen"' in text


async def test_update_character_requires_a_field(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("update_character", {"var": "e"}))
    assert "at least one of" in out["error"]


async def test_update_character_unknown_var(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("update_character", {"var": "ghost", "color": "#000"}))
    assert "no character named" in out["error"]


# ---------- add_layered_image ---------------------------------------------------


async def test_add_layered_image_renders_groups_and_attributes(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_layered_image",
            {
                "name": "yuki",
                "groups": [
                    {
                        "name": "body",
                        "attributes": [
                            {"name": "casual", "asset": "images/yuki_casual.png"},
                            {"name": "uniform", "asset": "images/yuki_uniform.png"},
                        ],
                    },
                    {
                        "name": "face",
                        "attributes": [{"name": "happy", "asset": "images/yuki_happy.png"}],
                    },
                ],
            },
        )
    )
    assert "added layeredimage `yuki`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "layeredimage yuki:" in text
    assert "    group body:" in text
    assert '        attribute casual "images/yuki_casual.png"' in text
    assert "    group face:" in text


# ---------- add_transform / add_screen ------------------------------------------


async def test_add_transform_emits_block(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_transform",
            {"name": "slide_in", "body": ["xalign 0.0", "linear 0.5 xalign 0.5"]},
        )
    )
    assert "added transform `slide_in`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "transform slide_in():" in text
    assert "    linear 0.5 xalign 0.5" in text


async def test_add_screen_emits_block_in_screens_file(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_screen",
            {"name": "debug_panel", "body": ['text "[affection_mei]"']},
        )
    )
    assert "added screen `debug_panel`" in out["summary"]
    text = (cfg.project_root / "game/screens.rpy").read_text()
    assert "screen debug_panel():" in text
    assert '    text "[affection_mei]"' in text


# ---------- update_options_field -----------------------------------------------


async def test_update_options_field_replaces_existing(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "update_options_field",
            {"field": "config.name", "value": '_("Updated Title")'},
        )
    )
    assert "updated `define config.name`" in out["summary"]
    text = (cfg.project_root / "game/options.rpy").read_text()
    assert 'define config.name = _("Updated Title")' in text


async def test_update_options_field_inserts_new(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "update_options_field",
            {"field": "config.has_quicksave", "value": "False"},
        )
    )
    assert "added `define config.has_quicksave" in out["summary"]
    text = (cfg.project_root / "game/options.rpy").read_text()
    assert "define config.has_quicksave = False" in text

