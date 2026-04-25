"""GUI-side recent-edits ring buffer.

Captures every edit the GUI saw, distinguishing writes the GUI initiated
(through its MCP subprocess) from writes detected externally by the
file-system watcher (i.e. another `renpy-mcp` instance, an LLM harness,
or a human editing the source directly).

The MCP server has its own buffer in `renpy_mcp.project.recent` for the
`get_recent_edits` tool. That buffer can't see external writes; this one
can. Both surfaces coexist on purpose — see DESIGN.md §1 for the
file-system-as-integration-point rationale.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Literal

MAX_ENTRIES = 50

Origin = Literal["gui", "agent"]


@dataclass(frozen=True)
class GuiRecentEdit:
    timestamp: float
    file: str
    origin: Origin
    summary: str
    diff: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "file": self.file,
            "origin": self.origin,
            "summary": self.summary,
            "diff": self.diff,
        }


_lock = threading.Lock()
_entries: deque[GuiRecentEdit] = deque(maxlen=MAX_ENTRIES)


def record(*, file: str, origin: Origin, summary: str = "", diff: str = "") -> None:
    entry = GuiRecentEdit(
        timestamp=time.time(),
        file=file,
        origin=origin,
        summary=summary,
        diff=diff,
    )
    with _lock:
        _entries.append(entry)


def snapshot(limit: int | None = None) -> list[GuiRecentEdit]:
    with _lock:
        items = list(_entries)
    items.reverse()
    if limit is not None and limit >= 0:
        items = items[:limit]
    return items


def clear() -> None:
    with _lock:
        _entries.clear()
