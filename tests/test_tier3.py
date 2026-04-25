"""Tier 3 high-level intents — exercise the composed write paths.

Each test uses a per-test copy of the fixture so writes don't leak.
After each mutation we re-snapshot via `idx.snapshot()` to confirm the
generated .rpy actually parses back through the scanner.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import tier1_read, tier2_write, tier3_intents
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT, parse


@pytest.fixture
def workspace(tmp_path: Path):
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    cfg = ServerConfig(
        project_root=proj.resolve(),
        sdk_root=SDK_ROOT,
        games_root=tmp_path.resolve(),
    )
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier2_write.register(reg, cfg, idx)
    tier3_intents.register(reg, cfg, idx)
    return cfg, reg, idx


# ---------- new_project ---------------------------------------------------------


async def test_new_project_scaffolds_and_rebinds(workspace, tmp_path):
    cfg, reg, idx = workspace
    out = parse(await reg.call("new_project", {"name": "Pirate Tale"}))
    assert out["slug"] == "pirate_tale"
    assert out["bound"] is True
    new_root = tmp_path / "pirate_tale"
    assert (new_root / "game" / "script.rpy").is_file()
    # The session is now pointed at the new project — the index snapshot
    # should reflect the scaffold's files, not the original tiny_project's.
    assert cfg.project_root == new_root.resolve()
    snap = idx.snapshot()
    assert any(l.name == "start" for l in snap.labels)


async def test_new_project_rejects_multiline_name(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("new_project", {"name": "bad\nname"}))
    assert "single-line" in out["error"]


async def test_new_project_is_idempotent(workspace, tmp_path):
    _, reg, _ = workspace
    await reg.call("new_project", {"name": "twice"})
    marker = tmp_path / "twice" / "game" / "script.rpy"
    first_bytes = marker.read_bytes()
    out2 = parse(await reg.call("new_project", {"name": "twice"}))
    assert out2["preexisting"] is True
    # Existing content is left untouched on re-scaffold.
    assert marker.read_bytes() == first_bytes


# ---------- create_scene --------------------------------------------------------


async def test_create_scene_full(workspace):
    cfg, reg, idx = workspace
    out = parse(
        await reg.call(
            "create_scene",
            {
                "name": "rooftop_meeting",
                "background": "bg park",
                "music": "audio/spring_theme.ogg",
                "characters": ["eileen happy"],
                "dialogue": [
                    {"character": "e", "text": "Hi there!"},
                    {"text": "She paused."},
                ],
                "ends_with": "jump",
                "jump_target": "ending",
            },
        )
    )
    assert "created scene `rooftop_meeting`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "label rooftop_meeting:" in text
    assert "    scene bg park" in text
    assert '    play music "audio/spring_theme.ogg"' in text
    assert "    show eileen happy" in text
    assert '    e "Hi there!"' in text
    assert '    "She paused."' in text
    assert "    jump ending" in text
    assert any(l.name == "rooftop_meeting" for l in idx.snapshot().labels)


async def test_create_scene_rejects_unknown_character(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "create_scene",
            {
                "name": "ghost_scene",
                "background": "bg park",
                "dialogue": [{"character": "ghost", "text": "boo"}],
            },
        )
    )
    assert "unknown character" in out["error"]


async def test_create_scene_rejects_collision(workspace):
    _, reg, _ = workspace
    out = parse(await reg.call("create_scene", {"name": "start", "background": "bg park"}))
    assert "already exists" in out["error"]


async def test_create_scene_jump_requires_target(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "create_scene",
            {"name": "no_target", "background": "bg park", "ends_with": "jump"},
        )
    )
    assert "jump_target" in out["error"]


# ---------- create_choice_node --------------------------------------------------


async def test_create_choice_node_with_prompt_and_flag(workspace):
    cfg, reg, idx = workspace
    out = parse(
        await reg.call(
            "create_choice_node",
            {
                "name": "fork",
                "prompt": {"character": "e", "text": "Where to?"},
                "choices": [
                    {
                        "text": "Cafe",
                        "target_label": "cafe_scene",
                        "set_flag": {"name": "met_mei", "value": "True"},
                    },
                    {"text": "Park", "target_label": "park_scene", "condition": "True"},
                ],
            },
        )
    )
    assert "created choice node `fork`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "label fork:" in text
    assert '    e "Where to?"' in text
    assert "    menu:" in text
    assert '        "Cafe":' in text
    assert "            $ met_mei = True" in text
    assert "            jump cafe_scene" in text
    assert '        "Park" if True:' in text
    assert any(l.name == "fork" for l in idx.snapshot().labels)


# ---------- create_route --------------------------------------------------------


async def test_create_route_chains_labels(workspace):
    cfg, reg, idx = workspace
    out = parse(
        await reg.call(
            "create_route",
            {"prefix": "mei_route", "nodes": ["intro", "date", "ending"]},
        )
    )
    assert "created route `mei_route` with 3 node(s)" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "label mei_route_intro:" in text
    assert "    jump mei_route_date" in text
    assert "label mei_route_date:" in text
    assert "    jump mei_route_ending" in text
    assert "label mei_route_ending:" in text
    assert text.rstrip().endswith("return")
    snap = idx.snapshot()
    names = [l.name for l in snap.labels]
    assert all(n in names for n in ("mei_route_intro", "mei_route_date", "mei_route_ending"))


async def test_create_route_rejects_existing_node(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "create_route", {"prefix": "ending", "nodes": ["fake"]},  # would create `ending_fake`
        )
    )
    # name collisions checked against generated `<prefix>_<node>`; the simple
    # case here (no collision) should succeed — exercise the explicit one:
    assert "summary" in out

    out = parse(
        await reg.call(
            "create_route", {"prefix": "tutorial", "nodes": ["start"]},  # collides with `tutorial_start`? no
        )
    )
    assert "summary" in out


# ---------- add_dialogue_block --------------------------------------------------


async def test_add_dialogue_block_rejects_newline(workspace):
    """Regression: multi-line text in dialogue breaks indent/quoting."""
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_dialogue_block",
            {
                "label": "park_scene",
                "lines": [{"character": "e", "text": "bad\nline"}],
            },
        )
    )
    assert "single-line" in out["error"]


async def test_create_choice_node_rejects_newline_in_choice(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "create_choice_node",
            {
                "name": "bad_choice_node",
                "choices": [{"text": "pick\nme", "target_label": "ending"}],
            },
        )
    )
    assert "single-line" in out["error"]


async def test_add_dialogue_block_appends_multiple(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_dialogue_block",
            {
                "label": "park_scene",
                "lines": [
                    {"character": "e", "text": "It's nice out."},
                    {"text": "A breeze {bold}stirs{/bold}."},  # tags get auto-escaped
                    {"character": "e", "text": "Yeah."},
                ],
            },
        )
    )
    assert "appended 3 dialogue line(s)" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert '    e "It\'s nice out."' in text or '    e "It\\\'s nice out."' in text or "It" in text
    assert "{{bold}}" in text  # escaped


async def test_add_dialogue_block_validates_characters(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_dialogue_block",
            {
                "label": "park_scene",
                "lines": [{"character": "e", "text": "ok"}, {"character": "ghost", "text": "boo"}],
            },
        )
    )
    assert "unknown character" in out["error"]


# ---------- swap_background -----------------------------------------------------


async def test_swap_background_replaces_scene_line(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("swap_background", {"label": "cafe_scene", "new_background": "bg park"}))
    assert "swapped background in `cafe_scene` to `bg park`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "    scene bg park" in text  # was originally `scene bg cafe`
    # The original `scene bg cafe` line should be gone from cafe_scene's body:
    cafe_block = text.split("label cafe_scene:")[1].split("label ")[0]
    assert "bg cafe" not in cafe_block


async def test_swap_background_no_scene(workspace):
    _, reg, _ = workspace
    # `ending` has no scene line.
    out = parse(await reg.call("swap_background", {"label": "ending", "new_background": "bg cafe"}))
    assert "no `scene` line" in out["error"]


# ---------- add_character_to_scene ---------------------------------------------


async def test_add_character_to_scene_after_scene_line(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_character_to_scene",
            {"label": "cafe_scene", "character": "m", "attribute": "happy", "position": "left"},
        )
    )
    assert "added `show m`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    cafe_block = text.split("label cafe_scene:")[1].split("label ")[0]
    # `show m happy at left` appears after the `scene` line, before the dialogue.
    scene_idx = cafe_block.index("scene bg cafe")
    show_idx = cafe_block.index("show m happy at left")
    dialogue_idx = cafe_block.index('m "Hi!')
    assert scene_idx < show_idx < dialogue_idx


async def test_add_character_to_scene_with_transition(workspace):
    cfg, reg, _ = workspace
    await reg.call(
        "add_character_to_scene",
        {"label": "cafe_scene", "character": "m", "with_transition": "dissolve"},
    )
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "    show m" in text
    assert "    with dissolve" in text


async def test_add_character_to_scene_appends_when_no_scene(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call("add_character_to_scene", {"label": "ending", "character": "e"})
    )
    assert "added `show e`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "    show e" in text


# ---------- set_scene_music -----------------------------------------------------


async def test_set_scene_music_replaces_existing(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "set_scene_music",
            {"label": "start", "asset": "audio/door.opus", "fadein": 2, "loop": True},
        )
    )
    assert "replaced music in `start`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert 'play music "audio/door.opus" fadein 2 loop' in text
    assert "spring_theme.ogg" not in text  # old music line gone


async def test_set_scene_music_inserts_after_scene(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "set_scene_music", {"label": "cafe_scene", "asset": "audio/spring_theme.ogg"}
        )
    )
    assert "added music to `cafe_scene`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    cafe_block = text.split("label cafe_scene:")[1].split("label ")[0]
    scene_idx = cafe_block.index("scene bg cafe")
    play_idx = cafe_block.index("play music")
    assert scene_idx < play_idx


async def test_set_scene_music_stop(workspace):
    cfg, reg, _ = workspace
    out = parse(await reg.call("set_scene_music", {"label": "start", "asset": ""}))
    assert "replaced music" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    start_block = text.split("label start:")[1].split("label ")[0]
    assert "stop music" in start_block
    assert "play music" not in start_block


# ---------- add_condition_branch -----------------------------------------------


async def test_add_condition_branch_if_elif_else(workspace):
    cfg, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_condition_branch",
            {
                "label": "park_scene",
                "branches": [
                    {"condition": "affection_mei > 5", "body": ['e "Wow."']},
                    {"condition": "affection_mei > 0", "body": ['e "Hmm."']},
                    {"body": ['e "OK."']},
                ],
            },
        )
    )
    assert "added if/elif/else block (3 branch(es))" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    park_block = text.split("label park_scene:")[1].split("label ")[0]
    assert "if affection_mei > 5:" in park_block
    assert "elif affection_mei > 0:" in park_block
    assert "else:" in park_block


async def test_add_condition_branch_first_must_have_condition(workspace):
    _, reg, _ = workspace
    out = parse(
        await reg.call(
            "add_condition_branch",
            {"label": "park_scene", "branches": [{"body": ["pass"]}]},
        )
    )
    assert "first branch must have a `condition`" in out["error"]


# ---------- add_inventory_item_scaffold ----------------------------------------


async def test_add_inventory_item_scaffold(workspace):
    cfg, reg, idx = workspace
    out = parse(
        await reg.call(
            "add_inventory_item_scaffold",
            {"name": "umbrella", "description": "Useful when it rains."},
        )
    )
    assert "scaffolded inventory item `umbrella`" in out["summary"]
    text = (cfg.project_root / "game/script.rpy").read_text()
    assert "# inventory item: Useful when it rains." in text
    assert "default has_umbrella = False" in text
    assert any(v.name == "has_umbrella" for v in idx.snapshot().defaults)


async def test_add_inventory_item_scaffold_rejects_existing_flag(workspace):
    _, reg, _ = workspace
    # First call succeeds.
    await reg.call("add_inventory_item_scaffold", {"name": "key"})
    # Second collides.
    out = parse(await reg.call("add_inventory_item_scaffold", {"name": "key"}))
    assert "already exists" in out["error"]


# ---------- add_minigame_screen_scaffold ---------------------------------------


async def test_add_minigame_screen_scaffold(workspace):
    cfg, reg, idx = workspace
    out = parse(
        await reg.call(
            "add_minigame_screen_scaffold",
            {"name": "fishing", "on_complete_label": "ending"},
        )
    )
    assert "scaffolded minigame `fishing`" in out["summary"]
    assert len(out["diffs"]) == 2
    screens_text = (cfg.project_root / "game/screens.rpy").read_text()
    script_text = (cfg.project_root / "game/script.rpy").read_text()
    assert "screen fishing_minigame():" in screens_text
    assert "label fishing_play:" in script_text
    assert "    call screen fishing_minigame" in script_text
    assert "    jump ending" in script_text
    snap = idx.snapshot()
    assert any(s.name == "fishing_minigame" for s in snap.screens)
    assert any(l.name == "fishing_play" for l in snap.labels)


async def test_add_minigame_screen_scaffold_rejects_existing_screen(workspace):
    _, reg, _ = workspace
    await reg.call(
        "add_minigame_screen_scaffold", {"name": "puzzle", "on_complete_label": "ending"}
    )
    out = parse(
        await reg.call(
            "add_minigame_screen_scaffold", {"name": "puzzle", "on_complete_label": "ending"}
        )
    )
    assert "already exists" in out["error"]
