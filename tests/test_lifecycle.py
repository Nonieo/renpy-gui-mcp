"""Tests for the lifecycle tools (launch_preview / stop_preview / status).

We deliberately do NOT spawn a real Ren'Py window here. The launch path is
exercised by replacing the SDK launcher argv with a benign `sleep 30` via
``asyncio.create_subprocess_exec`` (argv list, no shell interpretation), so
we can verify tracking / status / stop semantics without a UI popup.
"""

from __future__ import annotations

import asyncio
import json

from renpy_mcp import tools as tools_pkg
from renpy_mcp.config import ServerConfig
from renpy_mcp.tools import lifecycle
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT


def _parse(content_list):
    assert len(content_list) == 1
    return json.loads(content_list[0].text)


def _registry() -> ToolRegistry:
    cfg = ServerConfig(project_root=FIXTURE_ROOT.resolve(), sdk_root=SDK_ROOT)
    reg = ToolRegistry()
    lifecycle.register(reg, cfg)
    return reg


def _reset_state():
    lifecycle._preview_proc = None  # type: ignore[attr-defined]


async def test_status_when_idle():
    _reset_state()
    reg = _registry()
    assert _parse(await reg.call("get_preview_status", {})) == {"running": False}


async def test_stop_when_idle():
    _reset_state()
    reg = _registry()
    assert _parse(await reg.call("stop_preview", {})) == {"running": False}


async def test_launch_then_stop_via_fake_process(monkeypatch):
    _reset_state()
    reg = _registry()

    real_create = asyncio.create_subprocess_exec

    async def fake_exec(*_cmd, **kwargs):
        # Replace the SDK launcher with a benign long-running command.
        return await real_create("sleep", "30", **kwargs)

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    started = _parse(await reg.call("launch_preview", {}))
    assert started["started"] is True
    assert isinstance(started["pid"], int)

    # Second launch must refuse with the existing PID.
    second = _parse(await reg.call("launch_preview", {}))
    assert second.get("already_running") is True
    assert second["pid"] == started["pid"]

    status = _parse(await reg.call("get_preview_status", {}))
    assert status["running"] is True
    assert status["pid"] == started["pid"]

    stopped = _parse(await reg.call("stop_preview", {}))
    assert stopped["stopped"] is True
    assert stopped["pid"] == started["pid"]
    assert stopped["force_killed"] is False

    assert _parse(await reg.call("get_preview_status", {}))["running"] is False


def test_lifecycle_module_importable():
    assert hasattr(tools_pkg, "__name__")
    assert lifecycle.register


def test_atexit_hook_registered_once():
    """Calling register() multiple times must register the hook exactly once."""
    # Reset the flag so we can observe the registration behavior cleanly.
    lifecycle._atexit_registered = False  # type: ignore[attr-defined]

    import atexit as atexit_mod

    calls: list = []

    def _spy(func, *args, **kwargs):
        calls.append(func)

    cfg = ServerConfig(project_root=FIXTURE_ROOT.resolve(), sdk_root=SDK_ROOT)

    # First register: should hook into atexit.
    original = atexit_mod.register
    atexit_mod.register = _spy  # type: ignore[assignment]
    try:
        lifecycle.register(ToolRegistry(), cfg)
        first_count = len(calls)
        # Second register: must NOT add another hook.
        lifecycle.register(ToolRegistry(), cfg)
        second_count = len(calls)
    finally:
        atexit_mod.register = original  # type: ignore[assignment]

    assert first_count == 1
    assert second_count == 1


def test_atexit_callback_no_op_when_idle():
    """The atexit callback must not raise when there's no preview running."""
    _reset_state()
    # Should be silent and safe.
    lifecycle._terminate_preview_on_exit()  # type: ignore[attr-defined]
