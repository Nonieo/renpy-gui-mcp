"""Lifecycle tools — launch/stop/inspect long-running SDK subprocesses.

These tools manage processes; they intentionally do NOT touch project files.
State (the running preview's process handle) lives module-local. Only one
preview can be running per server instance — a second `launch_preview` while
one is up returns an error with the existing PID rather than silently
spawning a second window.

Safety note: spawning uses ``asyncio.create_subprocess_exec`` (argv list, no
shell interpretation), so caller-supplied paths never reach a shell parser.

If the MCP server itself exits, the preview survives (default Linux/macOS
parent-child behavior). Future work: register an atexit hook that
terminates the preview when the server shuts down.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import signal
from typing import Any

import mcp.types as types

from ..config import ServerConfig, sdk_launcher_name
from .registry import ToolDef, ToolRegistry

log = logging.getLogger("renpy_mcp.lifecycle")

_preview_proc: asyncio.subprocess.Process | None = None
_atexit_registered = False


def _terminate_preview_on_exit() -> None:
    """Best-effort cleanup if the MCP server exits while a preview is alive.

    Uses raw ``os.kill`` (not the asyncio Process API) because by atexit
    time the event loop is gone and ``proc.terminate()`` would no-op or
    raise. ProcessLookupError is benign — the process already exited.
    """
    global _preview_proc
    if _preview_proc is None or _preview_proc.returncode is not None:
        return
    pid = _preview_proc.pid
    try:
        os.kill(pid, signal.SIGTERM)
        log.info("atexit: SIGTERM sent to preview pid=%d", pid)
    except ProcessLookupError:
        pass
    except OSError as exc:
        log.warning("atexit: failed to terminate preview pid=%d: %s", pid, exc)


def register(registry: ToolRegistry, config: ServerConfig) -> None:
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_terminate_preview_on_exit)
        _atexit_registered = True
    registry.add(_launch_preview(config))
    registry.add(_stop_preview(config))
    registry.add(_get_preview_status())


def _launch_preview(config: ServerConfig) -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        global _preview_proc
        if _preview_proc is not None and _preview_proc.returncode is None:
            return _ok({"already_running": True, "pid": _preview_proc.pid})

        cmd = [str(config.sdk_root / sdk_launcher_name()), str(config.project_root)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _preview_proc = proc
        return _ok({"started": True, "pid": proc.pid, "command": cmd})

    return ToolDef(
        name="launch_preview",
        description=(
            "Launch the Ren'Py SDK against the project to play the game in a "
            "window. Returns immediately; the player closes the window when "
            "done. Refuses if a preview is already running — call `stop_preview` "
            "first or use `get_preview_status` to inspect."
        ),
        input_schema=schema,
        handler=handler,
    )


def _stop_preview(_config: ServerConfig) -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        global _preview_proc
        if _preview_proc is None or _preview_proc.returncode is not None:
            return _ok({"running": False})
        pid = _preview_proc.pid
        _preview_proc.terminate()
        try:
            await asyncio.wait_for(_preview_proc.wait(), timeout=5.0)
            forced = False
        except asyncio.TimeoutError:
            _preview_proc.kill()
            await _preview_proc.wait()
            forced = True
        rc = _preview_proc.returncode
        _preview_proc = None
        return _ok({"stopped": True, "pid": pid, "exit_code": rc, "force_killed": forced})

    return ToolDef(
        name="stop_preview",
        description=(
            "Terminate the running Ren'Py preview. Sends SIGTERM first; "
            "SIGKILL if the process hasn't exited within 5 seconds. Safe to "
            "call when nothing is running (returns running=false)."
        ),
        input_schema=schema,
        handler=handler,
    )


def _get_preview_status() -> ToolDef:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def handler(_arguments: dict[str, Any]) -> list[types.TextContent]:
        global _preview_proc
        if _preview_proc is None:
            return _ok({"running": False})
        if _preview_proc.returncode is None:
            return _ok({"running": True, "pid": _preview_proc.pid})
        rc = _preview_proc.returncode
        pid = _preview_proc.pid
        _preview_proc = None
        return _ok({"running": False, "last_pid": pid, "last_exit_code": rc})

    return ToolDef(
        name="get_preview_status",
        description=(
            "Report whether a Ren'Py preview is running. When idle and the "
            "previous run exited, returns the last PID and exit code so the "
            "caller can detect crashes."
        ),
        input_schema=schema,
        handler=handler,
    )


def _ok(payload: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]
