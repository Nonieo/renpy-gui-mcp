"""File-system watcher: pushes .rpy / asset change events into an asyncio queue.

Runs the watchdog observer in its own thread (watchdog is sync); each
filesystem event is forwarded into the shared asyncio queue via the
event loop reference captured at startup.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

log = logging.getLogger("renpy_mcp_gui.watcher")

_WATCHED_EXTS = (".rpy", ".png", ".jpg", ".jpeg", ".webp", ".ogg", ".opus", ".mp3", ".wav")


@dataclass(frozen=True)
class FileEvent:
    """One filesystem change worth telling the frontend about."""

    kind: str  # "rpy" or "asset"
    action: str  # "modified", "created", "deleted", "moved"
    path: str  # POSIX path relative to project_root


class _Handler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[FileEvent], project_root: Path) -> None:
        self._loop = loop
        self._queue = queue
        self._project_root = project_root

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in _WATCHED_EXTS:
            return
        try:
            rel = path.relative_to(self._project_root).as_posix()
        except ValueError:
            return
        kind = "rpy" if path.suffix.lower() == ".rpy" else "asset"
        evt = FileEvent(kind=kind, action=event.event_type, path=rel)
        # We're on a watchdog thread; hop back to the event loop.
        self._loop.call_soon_threadsafe(self._queue.put_nowait, evt)


class ProjectWatcher:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._observer: Observer | None = None
        self.queue: asyncio.Queue[FileEvent] = asyncio.Queue()

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        log.info("starting watcher on %s", self._project_root)
        handler = _Handler(loop, self.queue, self._project_root)
        observer = Observer()
        observer.schedule(handler, str(self._project_root / "game"), recursive=True)
        observer.start()
        self._observer = observer

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
