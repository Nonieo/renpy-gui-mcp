"""Persistent MCP client connection to the renpy-mcp server.

The GUI backend spawns one renpy-mcp subprocess at startup and keeps the
stdio MCP session open for the lifetime of the app. All tool calls flow
through this single session — there's no connection-per-request overhead.
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

log = logging.getLogger("renpy_mcp_gui.mcp")

# A response observer is invoked with (tool_name, parsed_payload) after
# every successful tool call. Used by the GUI backend to feed the
# watcher's self-write suppression: the watcher's `mark_self_write` is
# wired up as the observer in `app.py`'s lifespan, so any tool response
# carrying a `file` (single-file writes) or `diffs[].file` (multi-file
# writes like the minigame scaffold) records a suppression mark on the
# matching path. Observer exceptions never propagate — a broken hook
# must not break tool calls.
ResponseObserver = Callable[[str, dict[str, Any]], None]


class RenpyMcpClient:
    """Owns the long-lived MCP ClientSession; serializes calls through asyncio."""

    def __init__(
        self,
        project_root: Path,
        sdk_root: Path,
        response_observer: ResponseObserver | None = None,
    ) -> None:
        self._project_root = project_root
        self._sdk_root = sdk_root
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._response_observer = response_observer

    @property
    def project_root(self) -> Path:
        return self._project_root

    async def start(self) -> None:
        log.info("spawning renpy-mcp subprocess for project=%s sdk=%s", self._project_root, self._sdk_root)
        self._stack = AsyncExitStack()
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "renpy_mcp",
                "--project",
                str(self._project_root),
                "--sdk",
                str(self._sdk_root),
            ],
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        tools = (await self._session.list_tools()).tools
        log.info("renpy-mcp ready; %d tools available", len(tools))

    async def stop(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    async def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invoke a renpy-mcp tool and return its parsed JSON payload."""
        if self._session is None:
            raise RuntimeError("MCP client is not started")
        result = await self._session.call_tool(name, arguments or {})
        if not result.content:
            raise RuntimeError(f"tool `{name}` returned no content")
        first = result.content[0]
        if not hasattr(first, "text"):
            raise RuntimeError(f"tool `{name}` returned non-text content: {type(first).__name__}")
        try:
            payload = json.loads(first.text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"tool `{name}` returned invalid JSON: {exc}") from exc

        if self._response_observer is not None:
            try:
                self._response_observer(name, payload)
            except Exception:  # observer must never break tool calls
                log.exception("response observer raised for tool=%s", name)
        return payload
