"""Tests for the SDK fetch / cache helpers.

We can't actually download Ren'Py during a unit-test run (200 MB and a
network dependency), so the tests synthesize fake archives + fake cache
layouts and exercise the surface that doesn't touch the network.
"""

from __future__ import annotations

import os
import tarfile
from pathlib import Path

import pytest

from renpy_mcp.project import sdk_fetch


def test_default_cache_dir_honors_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("RENPY_MCP_SDK_CACHE", str(tmp_path / "custom"))
    assert sdk_fetch.default_cache_dir() == (tmp_path / "custom")


def test_default_cache_dir_uses_xdg(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("RENPY_MCP_SDK_CACHE", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert sdk_fetch.default_cache_dir() == (tmp_path / "xdg" / "renpy-mcp")


def test_cached_sdk_returns_none_when_empty(tmp_path: Path):
    assert sdk_fetch.cached_sdk(tmp_path / "missing") is None


def test_cached_sdk_picks_highest_version(tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    for v in ("8.4.2", "8.5.1", "8.6.0", "8.5.2"):
        sdk_dir = cache / f"sdk-{v}"
        sdk_dir.mkdir()
        (sdk_dir / "renpy.sh").write_text("#!/bin/sh\n")
    # A directory without renpy.sh should be ignored even if it sorts highest.
    bogus = cache / "sdk-9.0.0"
    bogus.mkdir()
    result = sdk_fetch.cached_sdk(cache)
    assert result == cache / "sdk-8.6.0"


def test_cached_sdk_skips_non_sdk_directories(tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "tmp_extract").mkdir()
    (cache / "scratch").mkdir()
    assert sdk_fetch.cached_sdk(cache) is None


def test_fetch_reuses_existing_cache(tmp_path: Path):
    """A pre-populated cache returns `cached=True` without touching the network."""
    cache = tmp_path / "cache"
    target = cache / "sdk-8.6.0"
    target.mkdir(parents=True)
    (target / "renpy.sh").write_text("#!/bin/sh\n")
    result = sdk_fetch.fetch_sdk(version="8.6.0", cache_dir=cache, progress=False)
    assert result.cached is True
    assert result.sdk_path == target
    assert result.version == "8.6.0"


def test_safe_extract_refuses_path_traversal(tmp_path: Path):
    """The extraction guard must reject archives that try to escape the dest."""
    archive = tmp_path / "evil.tar.bz2"
    payload = tmp_path / "evil"
    payload.mkdir()
    bad = payload / "innocent.txt"
    bad.write_text("safe")
    with tarfile.open(archive, "w:bz2") as tf:
        # A relative path that resolves outside `into` if not guarded.
        info = tarfile.TarInfo(name="../../../escape.txt")
        info.size = 4
        import io
        tf.addfile(info, io.BytesIO(b"evil"))
    extract = tmp_path / "out"
    extract.mkdir()
    with pytest.raises(sdk_fetch.SDKFetchError):
        sdk_fetch._safe_extract(archive, extract)


def test_locate_sdk_root_finds_renpy_sh(tmp_path: Path):
    extract = tmp_path / "extract"
    inner = extract / "renpy-8.6.0-sdk"
    inner.mkdir(parents=True)
    (inner / "renpy.sh").write_text("#!/bin/sh\n")
    assert sdk_fetch._locate_sdk_root(extract) == inner


def test_locate_sdk_root_returns_none_when_missing(tmp_path: Path):
    extract = tmp_path / "extract"
    extract.mkdir()
    (extract / "scratch").mkdir()
    assert sdk_fetch._locate_sdk_root(extract) is None
