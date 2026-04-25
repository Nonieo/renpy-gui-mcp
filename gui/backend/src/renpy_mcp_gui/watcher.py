"""File-system watcher: pushes .rpy / asset change events into an asyncio queue.

Runs the watchdog observer in its own thread (watchdog is sync); each
filesystem event is forwarded into the shared asyncio queue via the
event loop reference captured at startup.

**Self-write suppression.** When the GUI's MCP subprocess writes a file
through `apply_write`, the OS reports that change to this watcher just
like any other edit — but the GUI already knows about it, so echoing it
to WebSocket clients would invalidate queries unnecessarily and confuse
"external file changed" prompts in the future Inspector. The fix is a
short suppression window: every successful tool response that mutates a
file calls `mark_self_write(rel_path)`, and the observer thread skips
events on paths marked within the window (default 3s, mirrors Vangard's
discipline). Cross-thread access is guarded by a lock since marks come
from the asyncio loop thread and checks come from the watchdog thread.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

log = logging.getLogger("renpy_mcp_gui.watcher")

_WATCHED_EXTS = (".rpy", ".png", ".jpg", ".jpeg", ".webp", ".ogg", ".opus", ".mp3", ".wav")

# Default time after a self-write during which the observer ignores
# events on that path. 3 seconds is enough to cover the .rpyc cleanup
# fanout that follows an `apply_write` and any debouncing the underlying
# filesystem performs, without hiding genuinely independent edits.
DEFAULT_SUPPRESSION_WINDOW_SECONDS = 3.0


@dataclass(frozen=True)
class FileEvent:
    """One filesystem change worth telling the frontend about."""

    kind: str  # "rpy" or "asset"
    action: str  # "modified", "created", "deleted", "moved"
    path: str  # POSIX path relative to project_root


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: ProjectWatcher, loop: asyncio.AbstractEventLoop) -> None:
        self._watcher = watcher
        self._loop = loop

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in _WATCHED_EXTS:
            return
        try:
            rel = path.relative_to(self._watcher.project_root).as_posix()
        except ValueError:
            return
        # Drop events that originated from our own apply_write.
        if self._watcher.is_self_write(rel):
            return
        kind = "rpy" if path.suffix.lower() == ".rpy" else "asset"
        evt = FileEvent(kind=kind, action=event.event_type, path=rel)
        # We're on a watchdog thread; hop back to the event loop.
        self._loop.call_soon_threadsafe(self._watcher.queue.put_nowait, evt)


class ProjectWatcher:
    def __init__(
        self,
        project_root: Path,
        suppression_window_seconds: float = DEFAULT_SUPPRESSION_WINDOW_SECONDS,
    ) -> None:
        self._project_root = project_root
        self._observer: Observer | None = None
        self.queue: asyncio.Queue[FileEvent] = asyncio.Queue()

        self._self_writes: dict[str, float] = {}
        self._self_writes_lock = threading.Lock()
        self._window = suppression_window_seconds

    @property
    def project_root(self) -> Path:
        return self._project_root

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        log.info("starting watcher on %s", self._project_root)
        handler = _Handler(self, loop)
        observer = Observer()
        observer.schedule(handler, str(self._project_root / "game"), recursive=True)
        observer.start()
        self._observer = observer

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None

    # ---------- self-write suppression API --------------------------------------

    def mark_self_write(self, rel_path: str) -> None:
        """Record that an internal write just touched `rel_path`.

        Called from the asyncio thread (after a tool response with a
        `file` field comes back through the MCP client). The observer
        thread checks `is_self_write` before forwarding events. Old
        marks are purged opportunistically so the dict stays small.
        """
        if not isinstance(rel_path, str) or not rel_path:
            return
        with self._self_writes_lock:
            now = time.monotonic()
            self._self_writes[rel_path] = now
            cutoff = now - self._window
            # Purge expired entries while we hold the lock.
            self._self_writes = {
                p: t for p, t in self._self_writes.items() if t >= cutoff
            }

    def is_self_write(self, rel_path: str) -> bool:
        """Return True when `rel_path` was marked within the suppression window."""
        with self._self_writes_lock:
            ts = self._self_writes.get(rel_path)
            if ts is None:
                return False
            if (time.monotonic() - ts) >= self._window:
                # Lazy eviction — keeps the dict from accreting stale keys
                # even when no new marks come in.
                self._self_writes.pop(rel_path, None)
                return False
            return True
