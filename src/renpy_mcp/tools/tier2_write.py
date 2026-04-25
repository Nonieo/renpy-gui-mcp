"""Tier 2 — guarded write primitives.

Each tool mutates exactly one creator-visible thing. Inputs are structured;
the tool builds the .rpy text itself rather than accepting raw fragments.
Every tool routes through `project.writer.apply_write` so guardrails (indent
normalization, label-uniqueness check, .rpyc cleanup, atomic write, diff
generation, index refresh) are enforced uniformly.

Responses always include a unified diff. Harness UIs (hermes-agent,
Claude Code) render this for per-change approval.
"""

from __future__ import annotations

import re
from typing import Any

import mcp.types as types

from ..config import ServerConfig
from ..guardrails.dialogue import escape_dialogue, reject_multiline
from ..guardrails.reserved import reject_reserved_identifier
from ..project.scanner import ProjectIndex
from ..project.writer import WriteRejected, WriteResult, apply_write
from ._shared import (
    BODY_INDENT,
    append_block,
    err,
    find_default_insertion,
    find_single_label,
    find_top_level_decl_insertion,
    insert_into_label_body,
    label_terminator_line,
    num_str,
    ok,
    quote,
    splice_line,
    write_response,
)
from .registry import ToolDef, ToolRegistry

DEFAULT_SCRIPT = "game/script.rpy"


def register(registry: ToolRegistry, config: ServerConfig, index: ProjectIndex) -> None:
    registry.add(_add_label(config, index))
    registry.add(_add_say(config, index))
    registry.add(_add_jump(config, index))
    registry.add(_add_call(config, index))
    registry.add(_add_menu(config, index))
    registry.add(_set_variable_default(config, index))
    registry.add(_rename_label(config, index))
    registry.add(_add_audio_play(config, index))
    registry.add(_add_image_alias(config, index))
    registry.add(_add_character(config, index))
    registry.add(_update_character(config, index))
    registry.add(_add_layered_image(config, index))
    registry.add(_add_transform(config, index))
    registry.add(_add_screen(config, index))
    registry.add(_update_options_field(config, index))


# ---------- add_label -----------------------------------------------------------


def _add_label(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "New label name. Must be a valid Python identifier."},
            "body": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of body lines (without indentation; the tool "
                    "indents at 4 spaces). Defaults to `[\"pass\"]` so the label is well-formed."
                ),
            },
            "file": {
                "type": "string",
                "description": "Target .rpy file relative to project root. Defaults to `game/script.rpy`.",
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        body: list[str] = arguments.get("body") or []
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT

        if not name.isidentifier():
            return err(f"`{name}` is not a valid Python identifier")
        if msg := reject_reserved_identifier(name):
            return err(msg)

        snap = index.snapshot()
        if any(l.name == name for l in snap.labels):
            existing = next(l for l in snap.labels if l.name == name)
            return err(
                f"label `{name}` already exists",
                existing={"file": existing.range.file, "line": existing.range.start_line},
            )

        body_lines = [f"{BODY_INDENT}{ln}" for ln in (body or ["pass"])]
        block_lines = [f"label {name}:", *body_lines]
        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        new_text = append_block(original, block_lines)
        return write_response(config, index, rel_file, new_text, summary=f"added label `{name}`")

    return ToolDef(
        name="add_label",
        description=(
            "Create a new top-level Ren'Py label. Provide the name and an "
            "optional list of body lines (the tool indents them at 4 spaces and "
            "emits `pass` if you give no body). Refuses if the name is already "
            "in use anywhere in the project, is a reserved keyword, or is not a "
            "valid Python identifier. Default target file is `game/script.rpy`."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_say -------------------------------------------------------------


def _add_say(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Existing label whose body the say-statement is appended to."},
            "character": {
                "type": "string",
                "description": (
                    "Character variable name (e.g. `e`, `m`). Omit for narration. "
                    "Validated against the project's defined Characters."
                ),
            },
            "text": {
                "type": "string",
                "description": (
                    "Dialogue text. The tool escapes Ren'Py text-tag and "
                    "substitution metacharacters (`{`, `}`, `[`, `]`) for you. "
                    "Set `raw: true` if you have already escaped them yourself."
                ),
            },
            "raw": {
                "type": "boolean",
                "default": False,
                "description": "Skip dialogue escaping. Use only when you know what you are doing.",
            },
        },
        "required": ["label", "text"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        character: str | None = arguments.get("character")
        raw_text: str = arguments["text"]
        raw_flag: bool = bool(arguments.get("raw", False))

        if msg := reject_multiline(raw_text):
            return err(msg)

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)
        if character is not None and not any(c.var_name == character for c in snap.characters):
            return err(
                f"unknown character var: `{character}`",
                known=[c.var_name for c in snap.characters],
            )

        body_text = raw_text if raw_flag else escape_dialogue(raw_text)
        quoted = quote(body_text)
        say = f"{character} {quoted}" if character else quoted
        return insert_into_label_body(
            config, index, label, [say], summary=f"appended say-statement to `{label_name}`"
        )

    return ToolDef(
        name="add_say",
        description=(
            "Append a say-statement to the end of an existing label's body. "
            "Provide the target `label`, optional `character` (variable name), "
            "and the dialogue `text`. The tool double-escapes `{`, `}`, `[`, "
            "`]` for you (set `raw: true` to opt out) and validates the "
            "character variable against `list_characters`."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_jump / add_call -----------------------------------------------


def _add_jump(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    return _make_jumplike(config, index, keyword="jump")


def _add_call(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    return _make_jumplike(config, index, keyword="call")


def _make_jumplike(config: ServerConfig, index: ProjectIndex, *, keyword: str) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": f"Existing label whose body receives the {keyword}."},
            "target": {"type": "string", "description": "Label name to transfer control to."},
            "validate_target": {
                "type": "boolean",
                "default": True,
                "description": "Refuse the write when `target` does not yet exist. Disable for forward-references.",
            },
        },
        "required": ["label", "target"],
        "additionalProperties": False,
    }
    if keyword == "jump":
        schema["properties"]["replace_terminator"] = {
            "type": "boolean",
            "default": False,
            "description": (
                "If true, replace the label's existing trailing `jump`/`return` "
                "with the new jump. Default false so a stray double-jump fails loudly."
            ),
        }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        target_name: str = arguments["target"]
        validate_target: bool = bool(arguments.get("validate_target", True))
        replace_terminator: bool = bool(arguments.get("replace_terminator", False))

        if not target_name.isidentifier():
            return err(f"`{target_name}` is not a valid label identifier")

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)

        if validate_target and not any(l.name == target_name for l in snap.labels):
            return err(
                f"{keyword} target `{target_name}` does not exist; pass `validate_target: false` to allow forward-references"
            )

        # `jump` is a terminator. Refuse to add a second one unless caller opts in.
        if keyword == "jump":
            rel = label.range.file
            file_lines = (config.project_root / rel).read_text(encoding="utf-8").splitlines()
            term_idx = label_terminator_line(label, file_lines)
            if term_idx is not None:
                if not replace_terminator:
                    return err(
                        f"label `{label_name}` already terminates with `{file_lines[term_idx].strip()}`; "
                        "pass `replace_terminator: true` to overwrite it",
                    )
                file_lines[term_idx] = f"{BODY_INDENT}jump {target_name}"
                text = (config.project_root / rel).read_text(encoding="utf-8")
                new_text = "\n".join(file_lines) + ("\n" if text.endswith("\n") else "")
                return write_response(
                    config, index, rel, new_text,
                    summary=f"replaced terminator of `{label_name}` with `jump {target_name}`",
                )

        return insert_into_label_body(
            config,
            index,
            label,
            [f"{keyword} {target_name}"],
            summary=f"added `{keyword} {target_name}` to `{label_name}`",
        )

    if keyword == "jump":
        description = (
            "Append a `jump <target>` statement to the end of an existing "
            "label's body. By default the target label must already exist; "
            "pass `validate_target: false` to permit a forward-reference."
        )
    else:
        description = (
            "Append a `call <target>` statement. Unlike `jump`, `call` pushes "
            "onto the call stack and control returns to the next statement after "
            "`target` returns. Target validation matches `add_jump`."
        )
    return ToolDef(name=f"add_{keyword}", description=description, input_schema=schema, handler=handler)


# ---------- add_menu ------------------------------------------------------------


def _add_menu(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Existing label whose body receives the menu."},
            "choices": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Choice prompt. Auto-escaped like `add_say` text."},
                        "body": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lines executed when this choice is picked. Defaults to `[\"pass\"]`.",
                        },
                        "condition": {
                            "type": "string",
                            "description": "Optional Python expression gating the choice (`\"text\" if <condition>:`).",
                        },
                        "raw": {
                            "type": "boolean",
                            "default": False,
                            "description": "If true, skip metacharacter escaping on `text`.",
                        },
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["label", "choices"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        choices: list[dict[str, Any]] = arguments["choices"]

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)

        menu_lines: list[str] = ["menu:"]
        for ch in choices:
            if msg := reject_multiline(ch["text"]):
                return err(f"choice text: {msg}")
            text = ch["text"] if ch.get("raw") else escape_dialogue(ch["text"])
            quoted = quote(text)
            condition = ch.get("condition")
            header = f"{quoted} if {condition}:" if condition else f"{quoted}:"
            menu_lines.append(f"{BODY_INDENT}{header}")
            for body_line in ch.get("body") or ["pass"]:
                menu_lines.append(f"{BODY_INDENT * 2}{body_line}")

        return insert_into_label_body(
            config,
            index,
            label,
            menu_lines,
            summary=f"added menu with {len(choices)} choice(s) to `{label_name}`",
        )

    return ToolDef(
        name="add_menu",
        description=(
            "Append a `menu:` block to the end of an existing label's body. "
            "Each choice is `{text, body, condition?, raw?}`: `text` is the "
            "prompt (auto-escaped), `body` is the lines run on selection "
            "(defaults to `pass`), `condition` is an optional Python expression "
            "that gates the choice. Indentation is generated automatically."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- set_variable_default -----------------------------------------------


def _set_variable_default(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Variable name (Python identifier; dotted names not supported here)."},
            "value": {
                "type": "string",
                "description": (
                    "Raw Python literal/expression for the default value (e.g. `False`, `0`, `\"\"`, `[]`)."
                ),
            },
            "file": {
                "type": "string",
                "description": (
                    "Target .rpy file when creating a new declaration. Defaults to `game/script.rpy`. "
                    "Ignored when updating an existing declaration."
                ),
            },
        },
        "required": ["name", "value"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        value: str = arguments["value"]
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT

        if not name.isidentifier():
            return err(f"`{name}` is not a valid Python identifier")
        if msg := reject_reserved_identifier(name):
            return err(msg)

        snap = index.snapshot()
        existing = next((v for v in snap.defaults if v.name == name), None)
        if existing is not None:
            target_file = existing.range.file
            target = config.project_root / target_file
            text = target.read_text(encoding="utf-8")
            lines = text.splitlines()
            lines[existing.range.start_line - 1] = f"default {name} = {value}"
            new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
            return write_response(
                config, index, target_file, new_text,
                summary=f"updated `default {name}` (was `{existing.raw_value}`)",
            )

        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        insertion = find_default_insertion(original)
        new_text = splice_line(original, insertion, f"default {name} = {value}")
        return write_response(
            config, index, rel_file, new_text,
            summary=f"added `default {name} = {value}` to `{rel_file}`",
        )

    return ToolDef(
        name="set_variable_default",
        description=(
            "Add or update a `default name = value` declaration. If the variable "
            "already exists anywhere in the project, the tool rewrites its line "
            "in place (the `file` argument is ignored). If new, the declaration "
            "is inserted after the last existing `default`/`define` in `file` "
            "(default: `game/script.rpy`). Use this for branching flags and "
            "anything referenced by save/load — `default` participates in "
            "rollback, `define` does not."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- rename_label --------------------------------------------------------


_REF_PATTERNS = (
    (r"\blabel\s+{name}\b", "label"),
    (r"\bjump\s+{name}\b", "jump"),
    (r"\bcall\s+{name}\b", "call"),
    (r"""\bJump\(\s*["']{name}["']\s*\)""", "Jump"),
    (r"""\bCall\(\s*["']{name}["']\s*\)""", "Call"),
)


def _rename_label(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "old": {"type": "string", "description": "Existing label name."},
            "new": {"type": "string", "description": "New label name (must be a valid identifier)."},
        },
        "required": ["old", "new"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        old: str = arguments["old"]
        new: str = arguments["new"]

        if not new.isidentifier():
            return err(f"`{new}` is not a valid Python identifier")
        if msg := reject_reserved_identifier(new):
            return err(msg)

        snap = index.snapshot()
        if not any(l.name == old for l in snap.labels):
            return err(f"no such label: `{old}`")
        if any(l.name == new for l in snap.labels):
            return err(f"label `{new}` already exists")

        compiled = [
            (re.compile(pat.replace("{name}", re.escape(old))), kind) for pat, kind in _REF_PATTERNS
        ]
        replacements = {
            "label": f"label {new}",
            "jump": f"jump {new}",
            "call": f"call {new}",
            "Jump": f'Jump("{new}")',
            "Call": f'Call("{new}")',
        }

        diffs: list[dict[str, Any]] = []
        warnings: list[str] = []
        rpyc_cleaned: list[str] = []
        files_changed: list[str] = []

        for rel in snap.files:
            target = config.project_root / rel
            text = target.read_text(encoding="utf-8")
            new_text = text
            for pat, kind in compiled:
                new_text = pat.sub(replacements[kind], new_text)
            if new_text == text:
                continue
            try:
                result = apply_write(config, index, rel, new_text)
            except WriteRejected as exc:
                return err(f"rename rejected while rewriting `{rel}`: {exc}")
            if result.no_op:
                continue
            files_changed.append(rel)
            diffs.append({"file": rel, "diff": result.diff})
            warnings.extend(result.warnings)
            rpyc_cleaned.extend(result.rpyc_cleaned)

        if not files_changed:
            return err(f"renamed `{old}` -> `{new}` but no references were found; nothing was written")

        return ok(
            {
                "summary": f"renamed label `{old}` -> `{new}` across {len(files_changed)} file(s)",
                "files_changed": files_changed,
                "diffs": diffs,
                "warnings": warnings,
                "rpyc_cleaned": rpyc_cleaned,
            }
        )

    return ToolDef(
        name="rename_label",
        description=(
            "Rename a label everywhere it appears: the `label name:` "
            "declaration plus every `jump name`, `call name`, `Jump(\"name\")`, "
            "and `Call(\"name\")` reference across all .rpy files in the "
            "project. Refuses if the new name already exists or is a reserved "
            "keyword. Returns one diff per modified file."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_audio_play ------------------------------------------------------


def _add_audio_play(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Existing label whose body receives the play statement."},
            "channel": {"type": "string", "description": "Audio channel: `music`, `sound`, `voice`, `audio`, or any custom channel."},
            "asset": {"type": "string", "description": "Asset path relative to `game/` (e.g. `audio/spring_theme.ogg`)."},
            "loop": {"type": "boolean", "default": False, "description": "Add the `loop` clause."},
            "fadein": {"type": "number", "minimum": 0, "description": "Optional `fadein <seconds>` clause."},
            "fadeout": {"type": "number", "minimum": 0, "description": "Optional `fadeout <seconds>` clause."},
            "validate_asset": {
                "type": "boolean",
                "default": True,
                "description": "Refuse the write if the asset file does not exist on disk.",
            },
        },
        "required": ["label", "channel", "asset"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        label_name: str = arguments["label"]
        channel: str = arguments["channel"]
        asset: str = arguments["asset"]
        loop: bool = bool(arguments.get("loop", False))
        fadein = arguments.get("fadein")
        fadeout = arguments.get("fadeout")
        validate_asset: bool = bool(arguments.get("validate_asset", True))

        if not channel.isidentifier():
            return err(f"`{channel}` is not a valid channel identifier")

        snap = index.snapshot()
        label = find_single_label(snap.labels, label_name)
        if isinstance(label, str):
            return err(label)

        if validate_asset and not (config.game_dir / asset).is_file():
            return err(
                f"asset file does not exist: `game/{asset}`; pass `validate_asset: false` to allow placeholder paths"
            )

        clauses = [f'play {channel} "{asset}"']
        if fadein is not None:
            clauses.append(f"fadein {num_str(fadein)}")
        if fadeout is not None:
            clauses.append(f"fadeout {num_str(fadeout)}")
        if loop:
            clauses.append("loop")
        return insert_into_label_body(
            config, index, label, [" ".join(clauses)],
            summary=f"added `play {channel}` of `{asset}` to `{label_name}`",
        )

    return ToolDef(
        name="add_audio_play",
        description=(
            "Append a `play <channel> \"<asset>\"` statement to the end of an "
            "existing label's body. Optional `loop`, `fadein <seconds>`, "
            "`fadeout <seconds>` clauses are emitted in canonical order. The "
            "asset must exist under `game/` unless `validate_asset: false`."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_image_alias -----------------------------------------------------


_IMAGE_NAME_RE = re.compile(r"^[A-Za-z_]\w*( [A-Za-z_]\w*)*$")


def _add_image_alias(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": (
                    "Image name as Ren'Py sees it: one or more space-separated "
                    "identifiers (e.g. `bg park`, `eileen happy smile`). The "
                    "first token is the tag; the rest are attributes."
                ),
            },
            "asset": {"type": "string", "description": "Asset path relative to `game/` (e.g. `images/park.png`)."},
            "file": {"type": "string", "description": "Target .rpy file. Defaults to `game/script.rpy`."},
            "validate_asset": {
                "type": "boolean",
                "default": True,
                "description": "Refuse the write if the asset file does not exist on disk.",
            },
        },
        "required": ["name", "asset"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        asset: str = arguments["asset"]
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT
        validate_asset: bool = bool(arguments.get("validate_asset", True))

        if not _IMAGE_NAME_RE.match(name):
            return err(f"`{name}` is not a valid image name (must be space-separated identifiers)")
        if validate_asset and not (config.game_dir / asset).is_file():
            return err(
                f"asset file does not exist: `game/{asset}`; pass `validate_asset: false` to allow placeholder paths"
            )

        new_line = f'image {name} = "{asset}"'
        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        insertion = find_top_level_decl_insertion(original)
        new_text = splice_line(original, insertion, new_line)
        return write_response(
            config, index, rel_file, new_text, summary=f"added `image {name}` -> `{asset}`"
        )

    return ToolDef(
        name="add_image_alias",
        description=(
            "Add an `image <name> = \"<asset>\"` declaration. The image name "
            "follows Ren'Py tag/attribute conventions (space-separated "
            "identifiers). Inserted near other top-level declarations in the "
            "target file. Asset must exist under `game/` unless "
            "`validate_asset: false`."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_character / update_character -----------------------------------


def _add_character(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "var": {"type": "string", "description": "Variable name the Character is bound to (used as say-tag in dialogue)."},
            "display_name": {"type": "string", "description": "On-screen name shown above dialogue. Auto-escaped."},
            "color": {"type": "string", "description": "Optional name color (e.g. `#0099cc`). Wrapped in quotes for you."},
            "image_tag": {
                "type": "string",
                "description": (
                    "Optional image tag (single identifier) to enable "
                    "attribute-say syntax (`e happy \"...\"` -> show `e happy`)."
                ),
            },
            "extra_kwargs": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": (
                    "Optional extra keyword arguments. Values are emitted "
                    "verbatim — quote strings and pass valid Python expressions."
                ),
            },
            "file": {"type": "string", "description": "Target .rpy file. Defaults to `game/script.rpy`."},
        },
        "required": ["var", "display_name"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        var: str = arguments["var"]
        display_name: str = arguments["display_name"]
        color: str | None = arguments.get("color")
        image_tag: str | None = arguments.get("image_tag")
        extras: dict[str, str] = arguments.get("extra_kwargs") or {}
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT

        if not var.isidentifier():
            return err(f"`{var}` is not a valid Python identifier")
        if msg := reject_reserved_identifier(var):
            return err(msg)
        if image_tag is not None and not image_tag.isidentifier():
            return err(f"image tag `{image_tag}` must be a single identifier")
        if msg := reject_multiline(display_name):
            return err(f"display_name: {msg}")

        snap = index.snapshot()
        if any(c.var_name == var for c in snap.characters):
            return err(f"character `{var}` already exists")

        kwargs: list[str] = []
        if color is not None:
            kwargs.append(f'color="{color}"')
        if image_tag is not None:
            kwargs.append(f'image="{image_tag}"')
        for key, value in extras.items():
            if not key.isidentifier():
                return err(f"`{key}` is not a valid keyword argument name")
            kwargs.append(f"{key}={value}")
        kwargs_str = (", " + ", ".join(kwargs)) if kwargs else ""
        line = f'define {var} = Character("{escape_dialogue(display_name)}"{kwargs_str})'

        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        insertion = find_top_level_decl_insertion(original)
        new_text = splice_line(original, insertion, line)
        return write_response(config, index, rel_file, new_text, summary=f"defined character `{var}`")

    return ToolDef(
        name="add_character",
        description=(
            "Define a new Character: `define <var> = Character(\"<display>\", "
            "color=..., image=..., ...)`. Refuses if the variable name is taken "
            "or reserved. Pass extra Character kwargs through `extra_kwargs` "
            "(values emitted verbatim — quote strings yourself)."
        ),
        input_schema=schema,
        handler=handler,
    )


_CHARACTER_DISPLAY_QUOTED_RE = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")
_CHARACTER_COLOR_RE = re.compile(r"""color\s*=\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")


def _update_character(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "var": {"type": "string", "description": "Variable name of the Character to update."},
            "display_name": {"type": "string", "description": "New display name. Auto-escaped."},
            "color": {"type": "string", "description": "New name color (e.g. `#ff8800`)."},
        },
        "required": ["var"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        var: str = arguments["var"]
        new_display = arguments.get("display_name")
        new_color = arguments.get("color")
        if new_display is None and new_color is None:
            return err("provide at least one of `display_name` or `color`")
        if new_display is not None and (msg := reject_multiline(new_display)):
            return err(f"display_name: {msg}")

        snap = index.snapshot()
        match = next((c for c in snap.characters if c.var_name == var), None)
        if match is None:
            return err(f"no character named `{var}`")

        rel = match.range.file
        target = config.project_root / rel
        text = target.read_text(encoding="utf-8")
        lines = text.splitlines()
        idx = match.range.start_line - 1
        line = lines[idx]

        if new_display is not None:
            new_quoted = f'"{escape_dialogue(new_display)}"'
            line, count = _CHARACTER_DISPLAY_QUOTED_RE.subn(new_quoted, line, count=1)
            if count == 0:
                return err(
                    f"could not locate the display-name string in line {match.range.start_line}; "
                    "use Tier 4 `apply_unified_diff` for non-trivial Character edits"
                )
        if new_color is not None:
            replacement = f'color="{new_color}"'
            new_line, count = _CHARACTER_COLOR_RE.subn(replacement, line, count=1)
            if count == 0:
                if ")" not in line:
                    return err(f"line {match.range.start_line} has no closing `)`; cannot inject color")
                close_idx = line.rfind(")")
                inside = line[:close_idx].rstrip()
                sep = ", " if not inside.endswith("(") else ""
                line = f"{inside}{sep}{replacement})"
            else:
                line = new_line

        lines[idx] = line
        new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        return write_response(config, index, rel, new_text, summary=f"updated character `{var}`")

    return ToolDef(
        name="update_character",
        description=(
            "Modify an existing Character's display name and/or color in place. "
            "Other Character kwargs are preserved verbatim. Provide at least "
            "one of `display_name` or `color`. For deeper edits use Tier 4 "
            "`apply_unified_diff`."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_layered_image ---------------------------------------------------


def _add_layered_image(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Tag name for the layered image (single identifier)."},
            "groups": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "attributes": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "asset": {"type": "string"},
                                },
                                "required": ["name", "asset"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["name", "attributes"],
                    "additionalProperties": False,
                },
            },
            "file": {"type": "string", "description": "Target .rpy file. Defaults to `game/script.rpy`."},
        },
        "required": ["name", "groups"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        groups: list[dict[str, Any]] = arguments["groups"]
        rel_file: str = arguments.get("file") or DEFAULT_SCRIPT

        if not name.isidentifier():
            return err(f"`{name}` must be a single identifier")

        snap = index.snapshot()
        if any(li.name == name for li in snap.layered_images):
            return err(f"layered image `{name}` already exists")

        block_lines: list[str] = [f"layeredimage {name}:"]
        for grp in groups:
            grp_name = grp["name"]
            if not grp_name.isidentifier():
                return err(f"group name `{grp_name}` must be an identifier")
            block_lines.append(f"{BODY_INDENT}group {grp_name}:")
            for attr in grp["attributes"]:
                attr_name = attr["name"]
                if not attr_name.isidentifier():
                    return err(f"attribute name `{attr_name}` must be an identifier")
                block_lines.append(f'{BODY_INDENT * 2}attribute {attr_name} "{attr["asset"]}"')

        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        new_text = append_block(original, block_lines)
        return write_response(config, index, rel_file, new_text, summary=f"added layeredimage `{name}`")

    return ToolDef(
        name="add_layered_image",
        description=(
            "Add a `layeredimage <name>:` block with one or more groups, each "
            "containing inline `attribute <name> \"<asset>\"` lines. Use for "
            "composable character sprites (body/expression/clothing layers). "
            "For block-form attributes or `if`/`always` clauses, use Tier 4."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- add_transform / add_screen ------------------------------------------


def _add_transform(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    return _make_block_decl(
        config,
        index,
        keyword="transform",
        header_suffix="():",
        default_file=DEFAULT_SCRIPT,
        default_body=["pass"],
        existing_check=lambda snap, name: any(t.name == name for t in snap.transforms),
        description=(
            "Add a `transform <name>():` block with ATL body. Body lines are "
            "indented at 4 spaces automatically. Refuses on name collision or "
            "reserved-keyword name."
        ),
    )


def _add_screen(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    return _make_block_decl(
        config,
        index,
        keyword="screen",
        header_suffix="():",
        default_file="game/screens.rpy",
        default_body=["null"],
        existing_check=lambda snap, name: any(s.name == name for s in snap.screens),
        description=(
            "Add a `screen <name>():` block. Body lines are indented at 4 "
            "spaces automatically. Default target file is `game/screens.rpy` "
            "(created if missing). Variables read inside a screen MUST be "
            "declared with `default`, not `define` — use `set_variable_default` "
            "for any flag the screen depends on."
        ),
    )


def _make_block_decl(
    config: ServerConfig,
    index: ProjectIndex,
    *,
    keyword: str,
    header_suffix: str,
    default_file: str,
    default_body: list[str],
    existing_check,
    description: str,
) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": f"{keyword.capitalize()} name (Python identifier)."},
            "body": {
                "type": "array",
                "items": {"type": "string"},
                "description": f"Body lines without indentation. Defaults to {default_body!r}.",
            },
            "file": {"type": "string", "description": f"Target .rpy file. Defaults to `{default_file}`."},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name: str = arguments["name"]
        body: list[str] = arguments.get("body") or list(default_body)
        rel_file: str = arguments.get("file") or default_file

        if not name.isidentifier():
            return err(f"`{name}` must be a Python identifier")
        if msg := reject_reserved_identifier(name):
            return err(msg)
        if existing_check(index.snapshot(), name):
            return err(f"{keyword} `{name}` already exists")

        block_lines = [f"{keyword} {name}{header_suffix}", *(f"{BODY_INDENT}{ln}" for ln in body)]
        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        new_text = append_block(original, block_lines)
        return write_response(
            config, index, rel_file, new_text, summary=f"added {keyword} `{name}`"
        )

    return ToolDef(
        name=f"add_{keyword}",
        description=description,
        input_schema=schema,
        handler=handler,
    )


# ---------- update_options_field -----------------------------------------------


def _update_options_field(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "description": (
                    "Dotted field name as it appears after `define`, e.g. "
                    "`config.name`, `config.version`, `build.name`."
                ),
            },
            "value": {
                "type": "string",
                "description": "Raw Python literal (quote strings yourself: `\"My Game\"`).",
            },
            "file": {"type": "string", "description": "Target .rpy file. Defaults to `game/options.rpy`."},
        },
        "required": ["field", "value"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        field: str = arguments["field"]
        value: str = arguments["value"]
        rel_file: str = arguments.get("file") or "game/options.rpy"

        if not all(part.isidentifier() for part in field.split(".")):
            return err(f"`{field}` must be a dotted identifier")

        snap = index.snapshot()
        existing = next((d for d in snap.defines if d.name == field), None)
        if existing is not None:
            target_file = existing.range.file
            target = config.project_root / target_file
            text = target.read_text(encoding="utf-8")
            lines = text.splitlines()
            lines[existing.range.start_line - 1] = f"define {field} = {value}"
            new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
            return write_response(
                config, index, target_file, new_text,
                summary=f"updated `define {field}` (was `{existing.raw_value}`)",
            )

        target = config.project_root / rel_file
        original = target.read_text(encoding="utf-8") if target.is_file() else ""
        insertion = find_default_insertion(original)
        new_text = splice_line(original, insertion, f"define {field} = {value}")
        return write_response(
            config, index, rel_file, new_text,
            summary=f"added `define {field} = {value}` to `{rel_file}`",
        )

    return ToolDef(
        name="update_options_field",
        description=(
            "Set a `define <field> = <value>` line — typically in "
            "`game/options.rpy` (project title, version, build name, "
            "config flags). Updates the existing declaration in place when "
            "found; otherwise inserts in the target file. Pass `value` exactly "
            "as it should appear after the `=` (quote strings yourself)."
        ),
        input_schema=schema,
        handler=handler,
    )


__all__ = ["register", "WriteResult"]
