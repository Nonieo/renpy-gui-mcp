"""Phase 1c: watcher self-write suppression.

Tests run unconditionally — no SDK or subprocess. We exercise the
suppression logic directly against the watcher and its event handler,
plus the lifespan-side helper that extracts file paths from tool
responses.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from watchdog.events import FileModifiedEvent

from renpy_mcp_gui.app import _self_write_observer, state
from renpy_mcp_gui.watcher import ProjectWatcher, _Handler


class _StubLoop:
    """Drop-in for asyncio.AbstractEventLoop that runs callbacks inline.

    `_Handler.on_any_event` calls `loop.call_soon_threadsafe(fn, *args)`
    to hop the queue.put_nowait off the watchdog thread. In tests we
    can collapse that and assert against the queue synchronously.
    """

    def call_soon_threadsafe(self, fn, *args):
        fn(*args)


def _make_watcher(tmp_path: Path, *, window: float = 3.0) -> ProjectWatcher:
    (tmp_path / "game").mkdir(exist_ok=True)
    return ProjectWatcher(tmp_path.resolve(), suppression_window_seconds=window)


# ---------- mark_self_write / is_self_write ------------------------------------


def test_mark_self_write_records_path(tmp_path):
    watcher = _make_watcher(tmp_path)
    assert watcher.is_self_write("game/script.rpy") is False
    watcher.mark_self_write("game/script.rpy")
    assert watcher.is_self_write("game/script.rpy") is True


def test_mark_self_write_expires_after_window(tmp_path):
    watcher = _make_watcher(tmp_path, window=0.05)
    watcher.mark_self_write("game/script.rpy")
    time.sleep(0.1)
    assert watcher.is_self_write("game/script.rpy") is False


def test_marks_for_different_paths_dont_interfere(tmp_path):
    watcher = _make_watcher(tmp_path)
    watcher.mark_self_write("game/script.rpy")
    assert watcher.is_self_write("game/script.rpy") is True
    assert watcher.is_self_write("game/other.rpy") is False


def test_mark_self_write_ignores_falsy_input(tmp_path):
    watcher = _make_watcher(tmp_path)
    watcher.mark_self_write("")  # no crash
    watcher.mark_self_write(None)  # type: ignore[arg-type]
    assert watcher.is_self_write("") is False


# ---------- _Handler integration -----------------------------------------------


def test_handler_skips_events_on_self_written_paths(tmp_path):
    watcher = _make_watcher(tmp_path)
    handler = _Handler(watcher, _StubLoop())
    target = tmp_path / "game" / "script.rpy"
    target.write_text("label x:\n    return\n")
    watcher.mark_self_write("game/script.rpy")
    handler.on_any_event(FileModifiedEvent(str(target)))
    assert watcher.queue.qsize() == 0


def test_handler_forwards_unmarked_events(tmp_path):
    watcher = _make_watcher(tmp_path)
    handler = _Handler(watcher, _StubLoop())
    target = tmp_path / "game" / "script.rpy"
    target.write_text("label x:\n    return\n")
    handler.on_any_event(FileModifiedEvent(str(target)))
    assert watcher.queue.qsize() == 1
    evt = watcher.queue.get_nowait()
    assert evt.kind == "rpy"
    assert evt.path == "game/script.rpy"
    assert evt.action == "modified"


def test_handler_ignores_unwatched_extensions(tmp_path):
    watcher = _make_watcher(tmp_path)
    handler = _Handler(watcher, _StubLoop())
    target = tmp_path / "game" / "ignore_me.txt"
    target.write_text("hi")
    handler.on_any_event(FileModifiedEvent(str(target)))
    assert watcher.queue.qsize() == 0


def test_handler_drops_events_outside_project(tmp_path):
    watcher = _make_watcher(tmp_path)
    handler = _Handler(watcher, _StubLoop())
    outside = tmp_path.parent / "elsewhere.rpy"
    outside.write_text("label x:\n    return\n")
    handler.on_any_event(FileModifiedEvent(str(outside)))
    assert watcher.queue.qsize() == 0


# ---------- _self_write_observer payload extraction ---------------------------
#
# We replace `state.watcher` with a recording stub for these tests because
# the observer is module-level and reads `state.watcher.mark_self_write`.


class _RecordingWatcher:
    def __init__(self):
        self.marks: list[str] = []

    def mark_self_write(self, rel_path: str) -> None:
        self.marks.append(rel_path)


def _with_stub_watcher(test_fn):
    """Decorator: swap `state.watcher` for a stub recorder around the test."""

    def wrapper(*args, **kwargs):
        original = getattr(state, "watcher", None)
        stub = _RecordingWatcher()
        state.watcher = stub  # type: ignore[assignment]
        try:
            return test_fn(stub, *args, **kwargs)
        finally:
            if original is None:
                # Don't leave a stale attr if there wasn't one to begin with.
                if hasattr(state, "watcher"):
                    delattr(state, "watcher")
            else:
                state.watcher = original

    wrapper.__name__ = test_fn.__name__
    return wrapper


@_with_stub_watcher
def test_observer_marks_single_file_writes(stub):
    _self_write_observer("add_say", {"file": "game/script.rpy", "diff": "..."})
    assert stub.marks == ["game/script.rpy"]


@_with_stub_watcher
def test_observer_marks_multi_file_diffs(stub):
    payload = {
        "summary": "scaffolded minigame",
        "diffs": [
            {"file": "game/screens.rpy", "diff": "..."},
            {"file": "game/script.rpy", "diff": "..."},
        ],
    }
    _self_write_observer("add_minigame_screen_scaffold", payload)
    assert stub.marks == ["game/screens.rpy", "game/script.rpy"]


@_with_stub_watcher
def test_observer_skips_error_responses(stub):
    _self_write_observer("add_label", {"error": "label already exists"})
    assert stub.marks == []


@_with_stub_watcher
def test_observer_skips_payloads_without_file(stub):
    # Sidecar writes (set_canvas_positions, set_ignored_diagnostics) and
    # pure read responses don't carry a file field.
    _self_write_observer("read_canvas_positions", {"version": 1, "labels": {}})
    _self_write_observer(
        "set_canvas_positions",
        {"summary": "saved 1", "version": 1, "labels": {"start": {"x": 0, "y": 0}}},
    )
    assert stub.marks == []


@_with_stub_watcher
def test_observer_handles_non_dict_payload_gracefully(stub):
    _self_write_observer("foo", None)  # type: ignore[arg-type]
    _self_write_observer("foo", [1, 2, 3])  # type: ignore[arg-type]
    assert stub.marks == []
