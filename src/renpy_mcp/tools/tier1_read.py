"""Tier 1 — read-only project introspection.

Tool descriptions matter more than tool code: the harness uses them to pick
which tool to call. Keep them imperative, concrete, and short. Every tool
returns a single TextContent containing pretty-printed JSON.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import mcp.types as types

from .. import sdk as renpy_sdk
from ..config import ServerConfig
from ..project.scanner import (
    CharacterInfo,
    LabelInfo,
    ProjectIndex,
    ProjectSnapshot,
    ScreenInfo,
    SourceRange,
)
from .registry import ToolDef, ToolRegistry

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
_AUDIO_EXTS = (".ogg", ".opus", ".mp3", ".wav")


def register(registry: ToolRegistry, config: ServerConfig, index: ProjectIndex) -> None:
    registry.add(_get_project_overview(config, index))
    registry.add(_list_labels(index))
    registry.add(_read_label(config, index))
    registry.add(_list_characters(index))
    registry.add(_read_character(index))
    registry.add(_list_variables(index))
    registry.add(_list_screens(index))
    registry.add(_read_screen(config, index))
    registry.add(_list_images(config, index))
    registry.add(_list_audio(config, index))
    registry.add(_find_references(config))
    registry.add(_read_raw_file(config))
    registry.add(_get_lint_report(config))


# ---------- get_project_overview ------------------------------------------------


def _get_project_overview(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        snap = index.snapshot()
        overview = {
            "project_root": str(config.project_root),
            "files": list(snap.files),
            "counts": {
                "labels": len(snap.labels),
                "characters": len(snap.characters),
                "defaults": len(snap.defaults),
                "defines": len(snap.defines),
                "images": len(snap.images),
                "layered_images": len(snap.layered_images),
                "screens": len(snap.screens),
                "transforms": len(snap.transforms),
                "audio_plays": len(snap.audio_plays),
            },
            "labels": [l.name for l in snap.labels],
            "characters": [
                {"var": c.var_name, "display_name": c.display_name} for c in snap.characters
            ],
            "warnings": _overview_warnings(snap),
        }
        return _ok(overview)

    return ToolDef(
        name="get_project_overview",
        description=(
            "Return a high-level summary of the Ren'Py project: the list of .rpy "
            "files under game/, counts of every top-level construct (labels, "
            "characters, defaults, defines, images, screens, transforms, audio "
            "plays), the label name list, and the character roster. Call this "
            "first when starting work on a project; it is cheap and gives enough "
            "context to pick the right follow-up tool."
        ),
        input_schema=schema,
        handler=handler,
    )


def _overview_warnings(snap: ProjectSnapshot) -> list[str]:
    warnings: list[str] = []
    if snap.duplicate_labels:
        warnings.append(
            "duplicate label names (must be globally unique in Ren'Py): "
            + ", ".join(snap.duplicate_labels)
        )
    if not any(l.name == "start" for l in snap.labels):
        warnings.append("no `label start:` found — the project will not run as-is")
    return warnings


# ---------- list_labels / read_label --------------------------------------------


def _list_labels(index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "file": {
                "type": "string",
                "description": (
                    "Optional. Restrict results to labels declared in this .rpy file "
                    "(path relative to project root, e.g. 'game/script.rpy')."
                ),
            },
        },
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        snap = index.snapshot()
        labels = snap.labels
        wanted = arguments.get("file")
        if wanted:
            labels = tuple(l for l in labels if l.range.file == wanted)
        return _ok({"labels": [_label_dict(l) for l in labels], "count": len(labels)})

    return ToolDef(
        name="list_labels",
        description=(
            "List every Ren'Py label in the project (or in one .rpy file when "
            "`file` is given). Each entry includes the label name, the file and "
            "line range it spans, and a heuristic say-statement count. Use this "
            "to discover scenes, find the right label to read, or audit "
            "branching coverage."
        ),
        input_schema=schema,
        handler=handler,
    )


def _read_label(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The label name as written after `label ` (no colon).",
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name = arguments["name"]
        snap = index.snapshot()
        matches = [l for l in snap.labels if l.name == name]
        if not matches:
            return _err(f"no such label: {name}")
        if len(matches) > 1:
            return _err(
                f"label `{name}` is declared in multiple places — fix the duplicates first",
                locations=[_label_dict(l) for l in matches],
            )
        label = matches[0]
        return _ok(
            {
                "label": _label_dict(label),
                "source": _slice_source(config.project_root, label.range),
            }
        )

    return ToolDef(
        name="read_label",
        description=(
            "Return the full Ren'Py source of one label, including its header "
            "line, body, and source range (file + line numbers). Use this after "
            "`list_labels` when you need to see what a scene actually does — "
            "dialogue, jumps, menus, music, conditions."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- list_characters / read_character ------------------------------------


def _list_characters(index: ProjectIndex) -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        snap = index.snapshot()
        return _ok(
            {
                "characters": [_character_dict(c) for c in snap.characters],
                "count": len(snap.characters),
            }
        )

    return ToolDef(
        name="list_characters",
        description=(
            "List every Character defined via `define x = Character(...)`. Each "
            "entry has the variable name (used as the say-tag in dialogue lines), "
            "the display name if quoted positionally, the raw constructor "
            "arguments, and the source location. Use this to learn the cast and "
            "the say-tag conventions before adding dialogue."
        ),
        input_schema=schema,
        handler=handler,
    )


def _read_character(index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "var": {
                "type": "string",
                "description": "The variable name (e.g. 'e', 'm') the Character is bound to.",
            },
        },
        "required": ["var"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        var = arguments["var"]
        snap = index.snapshot()
        matches = [c for c in snap.characters if c.var_name == var]
        if not matches:
            return _err(f"no character named `{var}`")
        return _ok({"character": _character_dict(matches[0])})

    return ToolDef(
        name="read_character",
        description=(
            "Return the full Character definition for one variable: display "
            "name, raw constructor arguments (color, image tag, callback, etc.), "
            "and source location. Use after `list_characters` when you need to "
            "see exactly how a character was configured."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- list_variables ------------------------------------------------------


def _list_variables(index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["default", "define", "all"],
                "default": "all",
                "description": (
                    "Which kind to return. `default` participates in save/load "
                    "and rollback; `define` is a constant the engine may inline. "
                    "Variables read inside a screen MUST be `default`, not `define`."
                ),
            },
        },
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        kind = arguments.get("kind", "all")
        snap = index.snapshot()
        result: list[dict[str, Any]] = []
        if kind in ("default", "all"):
            result.extend(_variable_dict(v) for v in snap.defaults)
        if kind in ("define", "all"):
            result.extend(_variable_dict(v) for v in snap.defines)
        return _ok({"variables": result, "count": len(result)})

    return ToolDef(
        name="list_variables",
        description=(
            "List `default` and/or `define` declarations in the project. Filter "
            "with `kind: default|define|all` (default: all). Use to discover "
            "branching flags, persistent state, GUI tokens, and config values."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- list_screens / read_screen ------------------------------------------


def _list_screens(index: ProjectIndex) -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        snap = index.snapshot()
        return _ok(
            {
                "screens": [_screen_dict(s) for s in snap.screens],
                "count": len(snap.screens),
            }
        )

    return ToolDef(
        name="list_screens",
        description=(
            "List every `screen name():` declaration. Returns name plus source "
            "location for each. Use this before adding HUD, menu, or overlay "
            "elements to see what already exists."
        ),
        input_schema=schema,
        handler=handler,
    )


def _read_screen(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The screen name."},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        name = arguments["name"]
        snap = index.snapshot()
        matches = [s for s in snap.screens if s.name == name]
        if not matches:
            return _err(f"no such screen: {name}")
        screen = matches[0]
        return _ok(
            {
                "screen": _screen_dict(screen),
                "source": _slice_source(config.project_root, screen.range),
            }
        )

    return ToolDef(
        name="read_screen",
        description=(
            "Return the full Ren'Py source of one screen, including its header, "
            "body, and source range. Use after `list_screens` when you need to "
            "see what a custom screen actually displays."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- list_images ---------------------------------------------------------


def _list_images(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        snap = index.snapshot()
        results: list[dict[str, Any]] = []

        # Explicit `image x = "..."` aliases.
        for img in snap.images:
            results.append(
                {
                    "name": img.name,
                    "kind": "alias",
                    "value": img.raw_value,
                    "file": img.range.file,
                    "line": img.range.start_line,
                }
            )

        # `layeredimage name:` declarations.
        for li in snap.layered_images:
            results.append(
                {
                    "name": li.name,
                    "kind": "layered",
                    "file": li.range.file,
                    "line": li.range.start_line,
                }
            )

        # Auto-named files in game/images/. Filename underscores become spaces;
        # the directory is not part of the name.
        images_dir = config.game_dir / "images"
        if images_dir.is_dir():
            for path in sorted(images_dir.rglob("*")):
                if path.suffix.lower() not in _IMAGE_EXTS:
                    continue
                auto_name = path.stem.replace("_", " ")
                results.append(
                    {
                        "name": auto_name,
                        "kind": "auto",
                        "asset_path": path.relative_to(config.project_root).as_posix(),
                    }
                )

        return _ok({"images": results, "count": len(results)})

    return ToolDef(
        name="list_images",
        description=(
            "List every image known to Ren'Py: explicit `image foo = ...` "
            "aliases, `layeredimage` declarations, and auto-named asset files in "
            "`game/images/` (filename underscores become spaces, e.g. "
            "`eileen_happy.png` -> image name `eileen happy`). Each entry has a "
            "`kind` (alias|layered|auto) so you can tell them apart."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- list_audio ----------------------------------------------------------


def _list_audio(config: ServerConfig, index: ProjectIndex) -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        snap = index.snapshot()
        files: list[dict[str, Any]] = []
        audio_dir = config.game_dir / "audio"
        if audio_dir.is_dir():
            for path in sorted(audio_dir.rglob("*")):
                if path.suffix.lower() not in _AUDIO_EXTS:
                    continue
                files.append(
                    {
                        "asset_path": path.relative_to(config.project_root).as_posix(),
                        "size_bytes": path.stat().st_size,
                    }
                )

        plays = [
            {
                "channel": p.channel,
                "asset": p.asset,
                "file": p.range.file,
                "line": p.range.start_line,
            }
            for p in snap.audio_plays
        ]
        return _ok({"files": files, "plays": plays})

    return ToolDef(
        name="list_audio",
        description=(
            "List audio assets under `game/audio/` (.ogg/.opus/.mp3/.wav) and "
            "every `play <channel> \"asset\"` statement found in scripts. Use "
            "this to discover what music/SFX are available and where each is "
            "currently triggered."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- find_references -----------------------------------------------------


def _find_references(config: ServerConfig) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "needle": {
                "type": "string",
                "description": (
                    "The literal symbol to search for (label name, character "
                    "var, image name, asset path)."
                ),
            },
            "word_boundary": {
                "type": "boolean",
                "default": True,
                "description": (
                    "If true (default), match only when `needle` is bounded by "
                    "non-word characters. Disable for substring search."
                ),
            },
            "max_results": {
                "type": "integer",
                "default": 50,
                "minimum": 1,
                "maximum": 500,
            },
        },
        "required": ["needle"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        needle: str = arguments["needle"]
        if not needle:
            return _err("needle must be non-empty")
        word_boundary = arguments.get("word_boundary", True)
        max_results = int(arguments.get("max_results", 50))

        if word_boundary:
            pattern = re.compile(rf"\b{re.escape(needle)}\b")
        else:
            pattern = re.compile(re.escape(needle))

        matches: list[dict[str, Any]] = []
        for rpy in sorted(config.game_dir.rglob("*.rpy")):
            rel = rpy.relative_to(config.project_root).as_posix()
            text = rpy.read_text(encoding="utf-8", errors="replace")
            for idx, line in enumerate(text.splitlines()):
                if pattern.search(line):
                    matches.append({"file": rel, "line": idx + 1, "context": line.rstrip()})
                    if len(matches) >= max_results:
                        return _ok(
                            {
                                "matches": matches,
                                "count": len(matches),
                                "truncated": True,
                            }
                        )
        return _ok({"matches": matches, "count": len(matches), "truncated": False})

    return ToolDef(
        name="find_references",
        description=(
            "Search every .rpy file under `game/` for occurrences of a literal "
            "symbol (label name, character var, image name, asset path). Returns "
            "file/line/context for each match. Word-boundary by default so "
            "searching `e` does not match `eileen`. Cap with `max_results` "
            "(default 50, max 500)."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- read_raw_file -------------------------------------------------------


def _read_raw_file(config: ServerConfig) -> ToolDef:
    schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "File path relative to project root (e.g. 'game/options.rpy'). "
                    "Must resolve inside the project; absolute paths are rejected."
                ),
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    async def handler(arguments: dict[str, Any]) -> list[types.TextContent]:
        rel = arguments["path"]
        try:
            target = (config.project_root / rel).resolve()
            target.relative_to(config.project_root.resolve())
        except (ValueError, OSError) as exc:
            return _err(f"path must resolve inside project_root: {exc}")
        if not target.is_file():
            return _err(f"file does not exist: {rel}")
        text = target.read_text(encoding="utf-8", errors="replace")
        return _ok(
            {
                "path": rel,
                "lines": text.count("\n") + (0 if text.endswith("\n") or not text else 1),
                "content": text,
            }
        )

    return ToolDef(
        name="read_raw_file",
        description=(
            "Read any file inside the project root, returning its full text. Use "
            "for files the typed read tools do not cover: `game/options.rpy`, "
            "`game/gui.rpy`, translations, custom Python modules. Path must be "
            "relative to project root and stay inside it."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- get_lint_report -----------------------------------------------------


def _get_lint_report(config: ServerConfig) -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    # Lint output ends with a summary line of the form
    #   "1 errors, 2 warnings, 3 informational messages, 4 obsolete creator..."
    # Capture it for a quick at-a-glance answer; the agent can read full output too.
    summary_re = re.compile(r"^[\d,]+\s+errors?.*", re.MULTILINE)

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        try:
            result = await renpy_sdk.run_lint(config.sdk_root, config.project_root)
        except Exception as exc:
            return _err(f"failed to invoke renpy.sh lint: {exc}")
        m = summary_re.search(result.stdout)
        return _ok(
            {
                "returncode": result.returncode,
                "summary": m.group(0).strip() if m else None,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )

    return ToolDef(
        name="get_lint_report",
        description=(
            "Run Ren'Py's built-in `lint` command over the project and return its "
            "stdout, stderr, exit code, and the one-line summary at the bottom. "
            "Slow (a couple of seconds for small projects); call after writes "
            "or when investigating runtime issues, not as a routine probe."
        ),
        input_schema=schema,
        handler=handler,
    )


# ---------- helpers -------------------------------------------------------------


def _label_dict(label: LabelInfo) -> dict[str, Any]:
    return {
        "name": label.name,
        "file": label.range.file,
        "start_line": label.range.start_line,
        "end_line": label.range.end_line,
        "say_count": label.say_count,
    }


def _character_dict(c: CharacterInfo) -> dict[str, Any]:
    return {
        "var": c.var_name,
        "display_name": c.display_name,
        "raw_args": c.raw_args,
        "file": c.range.file,
        "line": c.range.start_line,
    }


def _variable_dict(v: Any) -> dict[str, Any]:
    return {
        "name": v.name,
        "kind": v.kind,
        "value": v.raw_value,
        "file": v.range.file,
        "line": v.range.start_line,
    }


def _screen_dict(s: ScreenInfo) -> dict[str, Any]:
    return {
        "name": s.name,
        "file": s.range.file,
        "start_line": s.range.start_line,
        "end_line": s.range.end_line,
    }


def _slice_source(project_root: Path, rng: SourceRange) -> str:
    text = (project_root / rng.file).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return "\n".join(lines[rng.start_line - 1 : rng.end_line])


def _ok(payload: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]


def _err(message: str, **extra: Any) -> list[types.TextContent]:
    body: dict[str, Any] = {"error": message}
    body.update(extra)
    return [types.TextContent(type="text", text=json.dumps(body, indent=2, ensure_ascii=False))]
