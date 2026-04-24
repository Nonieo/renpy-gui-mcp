"""Tier 3 — high-level intents.

These tools compose multiple Ren'Py constructs in a single call. They are
the primary surface agents will reach for; Tier 2 is for fine adjustment.
Each tool still routes its mutations through `apply_write`, so the writer's
guardrails (label uniqueness, .rpyc cleanup, indent normalization, atomic
write, diff response) apply uniformly.
"""

from __future__ import annotations

import re
from typing import Any

import mcp.types as types

from ..config import ServerConfig
from ..guardrails.dialogue import escape_dialogue
from ..guardrails.reserved import reject_reserved_identifier
from ..project.scanner import LabelInfo, ProjectIndex
from ..project.writer import WriteRejected, apply_write
from ._shared import (
    BODY_INDENT,
    append_block,
    err,
    find_default_insertion,
    find_single_label,
    insert_into_label_body,
    num_str,
    ok,
    quote,
    splice_line,
    write_response,
)
from .registry import ToolDef, ToolRegistry

DEFAULT_SCRIPT = "game/script.rpy"


def register(registry: ToolRegistry, config: ServerConfig, index: ProjectIndex) -> None:
    registry.add(_create_scene(config, index))
    registry.add(_create_choice_node(config, index))
    registry.add(_create_route(config, index))
    registry.add(_add_dialogue_block(config, index))
    registry.add(_swap_background(config, index))
    registry.add(_add_character_to_scene(config, index))
    registry.add(_set_scene_music(config, index))
    registry.add(_add_condition_branch(config, index))
    registry.add(_add_inventory_item_scaffold(config, index))
    registry.add(_add_minigame_screen_scaffold(config, index))


# ---------- create_scene --------------------------------------------------------


def _create_scene(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Label name for the scene (Python identifier)."},
            "background": {
                "type": "string",
                "description": (
                    "Image name to show with `scene` (e.g. `bg park`). Must "
                    "already be defined or auto-named in `game/images/`."
                ),
            },
            "music": {
                "type": "string",
                "description": "Optional music asset path (relative to `game/`). Played on `music` channel.",
            },
            "characters": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of image names/tags to `show` at scene "
                    "start (e.g. `[\"eileen happy\", \"mei\"]`)."
                ),
            },
            "dialogue": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {
                            "type": "string",
                            "description": "Character variable; omit for narration.",
                        },
                        "text": {"type": "string"},
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
                "description": "Optional opening dialogue lines (auto-escaped).",
            },
            "ends_with": {
                "type": "string",
                "enum": ["return", "jump", "fall_through"],
                "default": "return",
                "description": (
                    "How the scene ends: `return` (default), `jump` (requires "
                    "`jump_target`), or `fall_through` (no terminator)."
                ),
            },
            "jump_target": {"type": "string", "description": "Label to jump to when `ends_with: jump`."},
            "file": {"type": "string", "description": "Target .rpy file. Defaults to `game/script.rpy`."},
        },
        "required": ["name", "background"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        background: str = arguments["background"]
        music: str | None = arguments.get("music")
        characters: list[str] = arguments.get("characters") or []
        dialogue: list[dict[str, Any]] = arguments.get("dialogue") or []
        ends_with: str = arguments.get("ends_with", "return")
        jump_target: str | None = arguments.get("jump_target")
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT

        if not name.isidentifier():
            return err(f"`{name}` is not a valid Python identifier")
        if msg := reject_reserved_identifier(name):
            return err(msg)
        if ends_with == "jump" and not jump_target:
            return err("`jump_target` is required when `ends_with: jump`")
        if ends_with == "jump" and jump_target and not jump_target.isidentifier():
            return err(f"`{jump_target}` is not a valid label identifier")

        snap = index.snapshot()
        if any(l.name == name for l in snap.labels):
            return err(f"label `{name}` already exists")

        # Validate dialogue characters up front; surface them as a single error.
        known_chars = {c.var_name for c in snap.characters}
        unknown: list[str] = []
        for line in dialogue:
            ch = line.get("character")
            if ch is not None and ch not in known_chars:
                unknown.append(ch)
        if unknown:
            return err(
                f"unknown character var(s): {sorted(set(unknown))}",
                known=sorted(known_chars),
            )

        body: list[str] = [f"scene {background}"]
        if music is not None:
            body.append(f'play music "{music}"')
        for char in characters:
            body.append(f"show {char}")
        for line in dialogue:
            text = escape_dialogue(line["text"])
            quoted = quote(text)
            ch = line.get("character")
            body.append(f"{ch} {quoted}" if ch else quoted)
        if ends_with == "return":
            body.append("return")
        elif ends_with == "jump":
            body.append(f"jump {jump_target}")
        # fall_through: no terminator

        block_lines = [f"label {name}:", *(f"{BODY_INDENT}{ln}" for ln in body)]
        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        new_text = append_block(original, block_lines)
        return write_response(
            config, index, rel_file, new_text, summary=f"created scene `{name}`"
        )

    return ToolDef(
        name="create_scene",
        description=(
            "Create a complete scene as a single label: `scene <background>` + "
            "optional `play music` + optional `show <character>` lines + "
            "optional dialogue + a terminator (`return`, `jump <target>`, or "
            "fall-through). One call composes what would otherwise be many "
            "Tier 2 calls. Use this when authoring new content; use Tier 2 "
            "for fine-grained edits to existing scenes."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- create_choice_node --------------------------------------------------


def _create_choice_node(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Label name for the choice node."},
            "prompt": {
                "type": "object",
                "properties": {
                    "character": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["text"],
                "additionalProperties": False,
                "description": "Optional dialogue line shown immediately before the menu.",
            },
            "choices": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Choice prompt (auto-escaped)."},
                        "target_label": {"type": "string", "description": "Label to `jump` to when picked."},
                        "set_flag": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["name", "value"],
                            "additionalProperties": False,
                            "description": "Optional `$ name = value` line emitted before the jump.",
                        },
                        "condition": {"type": "string", "description": "Optional gating expression."},
                    },
                    "required": ["text", "target_label"],
                    "additionalProperties": False,
                },
            },
            "file": {"type": "string", "description": "Target .rpy file. Defaults to `game/script.rpy`."},
        },
        "required": ["name", "choices"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        prompt: dict[str, Any] | None = arguments.get("prompt")
        choices: list[dict[str, Any]] = arguments["choices"]
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT

        if not name.isidentifier():
            return err(f"`{name}` is not a valid Python identifier")
        if msg := reject_reserved_identifier(name):
            return err(msg)

        snap = index.snapshot()
        if any(l.name == name for l in snap.labels):
            return err(f"label `{name}` already exists")
        known_chars = {c.var_name for c in snap.characters}
        if prompt is not None and prompt.get("character") and prompt["character"] not in known_chars:
            return err(f"unknown character var: `{prompt['character']}`", known=sorted(known_chars))
        for ch in choices:
            if not ch["target_label"].isidentifier():
                return err(f"`{ch['target_label']}` is not a valid label identifier")

        body: list[str] = []
        if prompt is not None:
            text = quote(escape_dialogue(prompt["text"]))
            ch = prompt.get("character")
            body.append(f"{ch} {text}" if ch else text)
        body.append("menu:")
        for choice in choices:
            text = quote(escape_dialogue(choice["text"]))
            condition = choice.get("condition")
            header = f"{text} if {condition}:" if condition else f"{text}:"
            body.append(f"{BODY_INDENT}{header}")
            flag = choice.get("set_flag")
            if flag is not None:
                body.append(f"{BODY_INDENT * 2}$ {flag['name']} = {flag['value']}")
            body.append(f"{BODY_INDENT * 2}jump {choice['target_label']}")

        block_lines = [f"label {name}:", *(f"{BODY_INDENT}{ln}" for ln in body)]
        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        new_text = append_block(original, block_lines)
        return write_response(
            config, index, rel_file, new_text, summary=f"created choice node `{name}`"
        )

    return ToolDef(
        name="create_choice_node",
        description=(
            "Create a label that holds an optional opening dialogue line "
            "followed by a `menu:` whose choices each `jump` to a target "
            "label, optionally setting a flag first. Targets are NOT "
            "validated for existence so you can wire up routes in any order."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- create_route --------------------------------------------------------


def _create_route(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "prefix": {
                "type": "string",
                "description": "Identifier prefix for all node labels (e.g. `mei_route`).",
            },
            "nodes": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string"},
                "description": "Node names appended to the prefix with `_` (e.g. `[\"intro\", \"date\"]`).",
            },
            "ends_with": {
                "type": "string",
                "enum": ["return", "fall_through"],
                "default": "return",
                "description": "How the final node ends.",
            },
            "file": {"type": "string", "description": "Target .rpy file. Defaults to `game/script.rpy`."},
        },
        "required": ["prefix", "nodes"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        prefix: str = arguments["prefix"]
        nodes: list[str] = arguments["nodes"]
        ends_with: str = arguments.get("ends_with", "return")
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT

        if not prefix.isidentifier():
            return err(f"`{prefix}` is not a valid Python identifier")
        for n in nodes:
            if not n.isidentifier():
                return err(f"node name `{n}` is not a valid Python identifier")

        full_names = [f"{prefix}_{n}" for n in nodes]
        snap = index.snapshot()
        existing_labels = {l.name for l in snap.labels}
        collisions = [fn for fn in full_names if fn in existing_labels]
        if collisions:
            return err(f"label name(s) already exist: {collisions}")

        block_lines: list[str] = []
        for idx, full in enumerate(full_names):
            block_lines.append(f"label {full}:")
            block_lines.append(f"{BODY_INDENT}# TODO: write {full}")
            if idx < len(full_names) - 1:
                block_lines.append(f"{BODY_INDENT}jump {full_names[idx + 1]}")
            else:
                if ends_with == "return":
                    block_lines.append(f"{BODY_INDENT}return")
            block_lines.append("")  # blank line between labels for readability
        if block_lines and block_lines[-1] == "":
            block_lines.pop()

        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        new_text = append_block(original, block_lines)
        return write_response(
            config, index, rel_file, new_text,
            summary=f"created route `{prefix}` with {len(nodes)} node(s)",
        )

    return ToolDef(
        name="create_route",
        description=(
            "Scaffold a chain of empty labels named `<prefix>_<node>` that "
            "each fall-through into the next via `jump`. Last node terminates "
            "with `return` (default) or falls through. Use to lay down route "
            "structure before filling in dialogue with Tier 2 tools."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_dialogue_block --------------------------------------------------


def _add_dialogue_block(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Existing label whose body receives the dialogue."},
            "lines": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {"type": "string", "description": "Character variable; omit for narration."},
                        "text": {"type": "string"},
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
            "raw": {
                "type": "boolean",
                "default": False,
                "description": "If true, skip Ren'Py metacharacter escaping on every `text`.",
            },
        },
        "required": ["label", "lines"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        lines: list[dict[str, Any]] = arguments["lines"]
        raw_flag: bool = bool(arguments.get("raw", False))

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)

        known_chars = {c.var_name for c in snap.characters}
        unknown = sorted({l["character"] for l in lines if l.get("character") and l["character"] not in known_chars})
        if unknown:
            return err(f"unknown character var(s): {unknown}", known=sorted(known_chars))

        body_lines: list[str] = []
        for ln in lines:
            text = ln["text"] if raw_flag else escape_dialogue(ln["text"])
            quoted = quote(text)
            ch = ln.get("character")
            body_lines.append(f"{ch} {quoted}" if ch else quoted)

        return insert_into_label_body(
            config, index, label, body_lines,
            summary=f"appended {len(lines)} dialogue line(s) to `{label_name}`",
        )

    return ToolDef(
        name="add_dialogue_block",
        description=(
            "Append multiple dialogue lines to a label in one write. Each line "
            "is `{character?, text}`; characters are validated up front. Saves "
            "the round-trip cost of repeated `add_say` calls when authoring a "
            "scene."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- swap_background -----------------------------------------------------


_SCENE_LINE_RE = re.compile(r"^(\s*)scene\s+([^\s].*?)$")


def _swap_background(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Label whose first `scene` line is replaced."},
            "new_background": {"type": "string", "description": "New image name (e.g. `bg cafe`)."},
        },
        "required": ["label", "new_background"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        new_bg: str = arguments["new_background"]

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)

        rel = label.range.file
        target = config.project_root / rel
        text = target.read_text(encoding="utf-8")
        lines = text.splitlines()

        # Search inside the label's body for the first `scene <X>` line.
        body_start = label.range.start_line  # 0-based: label header at start_line - 1
        body_end = label.range.end_line  # inclusive end
        for idx in range(body_start, body_end):
            m = _SCENE_LINE_RE.match(lines[idx])
            if m:
                indent = m.group(1)
                lines[idx] = f"{indent}scene {new_bg}"
                new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
                return write_response(
                    config, index, rel, new_text,
                    summary=f"swapped background in `{label_name}` to `{new_bg}`",
                )
        return err(f"no `scene` line found in label `{label_name}`")

    return ToolDef(
        name="swap_background",
        description=(
            "Replace the first `scene <image>` line inside an existing label "
            "with `scene <new_background>`. Use when re-skinning a scene "
            "without rewriting the rest of the body."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_character_to_scene ---------------------------------------------


def _add_character_to_scene(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Label to insert the `show` into."},
            "character": {
                "type": "string",
                "description": "Image tag (often the character var, e.g. `eileen`).",
            },
            "attribute": {
                "type": "string",
                "description": "Optional attribute (e.g. `happy`). Combined with the tag in the `show` statement.",
            },
            "position": {
                "type": "string",
                "enum": ["left", "center", "right", "truecenter"],
                "description": "Optional `at <position>` clause.",
            },
            "with_transition": {
                "type": "string",
                "description": "Optional transition name (e.g. `dissolve`). Emitted as a `with <name>` follow-up.",
            },
        },
        "required": ["label", "character"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        character: str = arguments["character"]
        attribute: str | None = arguments.get("attribute")
        position: str | None = arguments.get("position")
        transition: str | None = arguments.get("with_transition")

        if not character.isidentifier():
            return err(f"`{character}` must be a single identifier")
        if attribute is not None and not attribute.isidentifier():
            return err(f"attribute `{attribute}` must be a single identifier")

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)

        show_parts = ["show", character]
        if attribute is not None:
            show_parts.append(attribute)
        if position is not None:
            show_parts.extend(["at", position])
        body_lines = [" ".join(show_parts)]
        if transition is not None:
            body_lines.append(f"with {transition}")

        # Insert immediately after the first `scene` line if one exists; else append.
        rel = label.range.file
        target = config.project_root / rel
        text = target.read_text(encoding="utf-8")
        lines = text.splitlines()
        body_start = label.range.start_line
        body_end = label.range.end_line
        scene_idx = -1
        scene_indent = BODY_INDENT
        for idx in range(body_start, body_end):
            m = _SCENE_LINE_RE.match(lines[idx])
            if m:
                scene_idx = idx
                scene_indent = m.group(1)
                break

        if scene_idx >= 0:
            indented = [f"{scene_indent}{ln}" for ln in body_lines]
            new_lines = lines[: scene_idx + 1] + indented + lines[scene_idx + 1 :]
            new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
            return write_response(
                config, index, rel, new_text,
                summary=f"added `show {character}` to `{label_name}`",
            )

        # No scene line — just append at the end of the label body.
        return insert_into_label_body(
            config, index, label, body_lines,
            summary=f"added `show {character}` to `{label_name}`",
        )

    return ToolDef(
        name="add_character_to_scene",
        description=(
            "Add a `show <character> [attribute] [at <position>]` statement to "
            "an existing label. Inserted immediately after the label's first "
            "`scene` line; appended to the body if no `scene` exists. Optional "
            "`with_transition` adds a follow-up `with <name>` line."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- set_scene_music -----------------------------------------------------


_PLAY_LINE_RE = re.compile(r"^(\s*)play\s+(\w+)\s+\".+?\"(?:\s+.*)?$")


def _set_scene_music(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Label whose music is set."},
            "asset": {
                "type": "string",
                "description": "Asset path relative to `game/`. Pass an empty string to emit `stop music` instead.",
            },
            "fadein": {"type": "number", "minimum": 0, "description": "Optional `fadein <seconds>` clause."},
            "loop": {"type": "boolean", "default": False, "description": "Add the `loop` clause."},
            "validate_asset": {
                "type": "boolean",
                "default": True,
                "description": "Refuse the write if the asset file does not exist on disk.",
            },
        },
        "required": ["label", "asset"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        asset: str = arguments["asset"]
        fadein = arguments.get("fadein")
        loop: bool = bool(arguments.get("loop", False))
        validate_asset: bool = bool(arguments.get("validate_asset", True))

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)
        if asset and validate_asset and not (config.game_dir / asset).is_file():
            return err(
                f"asset file does not exist: `game/{asset}`; pass `validate_asset: false` to allow placeholder paths"
            )

        if asset:
            clauses = [f'play music "{asset}"']
            if fadein is not None:
                clauses.append(f"fadein {num_str(fadein)}")
            if loop:
                clauses.append("loop")
            new_play = " ".join(clauses)
        else:
            new_play = "stop music"

        rel = label.range.file
        target = config.project_root / rel
        text = target.read_text(encoding="utf-8")
        lines = text.splitlines()
        body_start = label.range.start_line
        body_end = label.range.end_line
        for idx in range(body_start, body_end):
            m = _PLAY_LINE_RE.match(lines[idx])
            if m and m.group(2) == "music":
                lines[idx] = f"{m.group(1)}{new_play}"
                new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
                return write_response(
                    config, index, rel, new_text,
                    summary=f"replaced music in `{label_name}`",
                )

        # No existing music line — insert after the scene line if one exists, else append.
        scene_idx = -1
        scene_indent = BODY_INDENT
        for idx in range(body_start, body_end):
            m = _SCENE_LINE_RE.match(lines[idx])
            if m:
                scene_idx = idx
                scene_indent = m.group(1)
                break
        if scene_idx >= 0:
            new_lines = lines[: scene_idx + 1] + [f"{scene_indent}{new_play}"] + lines[scene_idx + 1 :]
            new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
            return write_response(
                config, index, rel, new_text,
                summary=f"added music to `{label_name}`",
            )
        return insert_into_label_body(
            config, index, label, [new_play],
            summary=f"added music to `{label_name}`",
        )

    return ToolDef(
        name="set_scene_music",
        description=(
            "Set or replace the music in a label: rewrites the existing "
            "`play music` line if present, otherwise inserts one after the "
            "label's first `scene` line. Pass an empty `asset` to emit "
            "`stop music` instead."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_condition_branch -----------------------------------------------


def _add_condition_branch(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Existing label whose body receives the if/elif/else block."},
            "branches": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "condition": {
                            "type": "string",
                            "description": (
                                "Python expression for the branch. Omit on the "
                                "last branch to make it the `else` clause."
                            ),
                        },
                        "body": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lines run when the condition holds. Defaults to `[\"pass\"]`.",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
        "required": ["label", "branches"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        branches: list[dict[str, Any]] = arguments["branches"]

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)

        body_lines: list[str] = []
        for idx, branch in enumerate(branches):
            condition = branch.get("condition")
            body = branch.get("body") or ["pass"]
            if idx == 0:
                if not condition:
                    return err("first branch must have a `condition`")
                body_lines.append(f"if {condition}:")
            elif condition is None:
                body_lines.append("else:")
            else:
                body_lines.append(f"elif {condition}:")
            body_lines.extend(f"{BODY_INDENT}{ln}" for ln in body)

        return insert_into_label_body(
            config, index, label, body_lines,
            summary=f"added if/elif/else block ({len(branches)} branch(es)) to `{label_name}`",
        )

    return ToolDef(
        name="add_condition_branch",
        description=(
            "Append an `if/elif/else` block to a label's body. Each branch is "
            "`{condition?, body}`. The first branch must have a `condition`; "
            "an omitted condition on the last branch becomes `else`."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_inventory_item_scaffold ----------------------------------------


def _add_inventory_item_scaffold(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Item identifier (Python identifier; used as the flag-variable suffix).",
            },
            "description": {
                "type": "string",
                "description": "Optional human-readable description; emitted as a comment above the flag.",
            },
            "file": {"type": "string", "description": "Target .rpy file. Defaults to `game/script.rpy`."},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        description: str | None = arguments.get("description")
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT

        if not name.isidentifier():
            return err(f"`{name}` is not a valid Python identifier")
        if msg := reject_reserved_identifier(name):
            return err(msg)

        flag = f"has_{name}"
        snap = index.snapshot()
        if any(v.name == flag for v in snap.defaults):
            return err(f"inventory flag `{flag}` already exists")

        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        insertion = find_default_insertion(original)
        new_lines: list[str] = []
        if description:
            new_lines.append(f"# inventory item: {description}")
        new_lines.append(f"default {flag} = False")

        new_text = original
        for line in new_lines:
            new_text = splice_line(new_text, insertion, line)
            insertion += 1
        return write_response(
            config, index, rel_file, new_text,
            summary=f"scaffolded inventory item `{name}` (flag `{flag}`)",
        )

    return ToolDef(
        name="add_inventory_item_scaffold",
        description=(
            "Add a `default has_<name> = False` flag plus an optional "
            "description comment to track an inventory item. Ren'Py has no "
            "primitive inventory system; this is the minimal flag-based "
            "pattern. For richer item metadata define a Python `Item` class "
            "via Tier 4 `apply_unified_diff`."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_minigame_screen_scaffold ---------------------------------------


def _add_minigame_screen_scaffold(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Identifier prefix; the screen is `<name>_minigame`, the entry label is `<name>_play`."},
            "on_complete_label": {"type": "string", "description": "Label to `jump` to once the minigame returns."},
            "screens_file": {"type": "string", "description": "Target file for the screen. Defaults to `game/screens.rpy`."},
            "label_file": {"type": "string", "description": "Target file for the entry label. Defaults to `game/script.rpy`."},
        },
        "required": ["name", "on_complete_label"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        on_complete: str = arguments["on_complete_label"]
        screens_file: str = arguments.get("screens_file") or "game/screens.rpy"
        label_file: str = arguments.get("label_file") or DEFAULT_SCRIPT

        if not name.isidentifier():
            return err(f"`{name}` is not a valid Python identifier")
        if msg := reject_reserved_identifier(name):
            return err(msg)
        if not on_complete.isidentifier():
            return err(f"`{on_complete}` is not a valid label identifier")

        screen_name = f"{name}_minigame"
        label_name = f"{name}_play"

        snap = index.snapshot()
        if any(s.name == screen_name for s in snap.screens):
            return err(f"screen `{screen_name}` already exists")
        if any(l.name == label_name for l in snap.labels):
            return err(f"label `{label_name}` already exists")

        screen_block = [
            f"screen {screen_name}():",
            f'{BODY_INDENT}# placeholder — replace with real minigame UI',
            f"{BODY_INDENT}timer 5.0 action Return()",
            f"{BODY_INDENT}vbox:",
            f"{BODY_INDENT * 2}xalign 0.5",
            f"{BODY_INDENT * 2}yalign 0.5",
            f'{BODY_INDENT * 2}text "[{screen_name}] minigame placeholder"',
            f'{BODY_INDENT * 2}textbutton "Skip" action Return()',
        ]
        label_block = [
            f"label {label_name}:",
            f"{BODY_INDENT}call screen {screen_name}",
            f"{BODY_INDENT}jump {on_complete}",
        ]

        try:
            screens_target = config.project_root / screens_file
            screens_original = screens_target.read_text(encoding="utf-8") if screens_target.is_file() else ""
            screens_new = append_block(screens_original, screen_block)
            screen_result = apply_write(config, index, screens_file, screens_new)

            label_target = config.project_root / label_file
            label_original = label_target.read_text(encoding="utf-8") if label_target.is_file() else ""
            label_new = append_block(label_original, label_block)
            label_result = apply_write(config, index, label_file, label_new)
        except WriteRejected as exc:
            return err(str(exc))

        return ok(
            {
                "summary": f"scaffolded minigame `{name}` (screen `{screen_name}`, entry `{label_name}`)",
                "diffs": [
                    {"file": screen_result.file, "diff": screen_result.diff},
                    {"file": label_result.file, "diff": label_result.diff},
                ],
                "warnings": list(screen_result.warnings) + list(label_result.warnings),
                "rpyc_cleaned": list(screen_result.rpyc_cleaned) + list(label_result.rpyc_cleaned),
            }
        )

    return ToolDef(
        name="add_minigame_screen_scaffold",
        description=(
            "Generate a placeholder minigame: a `screen <name>_minigame` that "
            "auto-returns after 5 seconds (or via a Skip button), plus a "
            "`label <name>_play` that calls the screen and jumps to "
            "`on_complete_label`. The screen body is meant to be replaced with "
            "real gameplay; the label wiring is production-shaped."
        ),
        input_schema=schema,
        handler=handler,
    )


__all__ = ["register"]
