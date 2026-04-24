"""Backend tests for the FastAPI GUI app.

Each test gets its own copy of the fixture project so write endpoints
don't leak across tests. The TestClient context triggers FastAPI's
lifespan, which spawns the renpy-mcp subprocess and starts the file
watcher — so each test exercises the real wiring end-to-end.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from renpy_mcp.config import sdk_launcher_name
from renpy_mcp_gui.app import build_app

from .conftest import FIXTURE_ROOT, SDK_ROOT

# Skip the whole module if the SDK launcher isn't present (CI/dev without one).
sdk_launcher_path = SDK_ROOT / sdk_launcher_name()
pytestmark = pytest.mark.skipif(
    not sdk_launcher_path.is_file(),
    reason="Ren'Py SDK not present (set RENPY_SDK to enable backend tests)",
)


@pytest.fixture
def app_client(tmp_path: Path):
    """Per-test FastAPI client backed by a fresh fixture-project copy."""
    proj = tmp_path / "tiny_project"
    shutil.copytree(FIXTURE_ROOT, proj)
    app = build_app(proj.resolve(), SDK_ROOT)
    with TestClient(app) as client:
        yield client, proj


# ---------- read endpoints ------------------------------------------------------


def test_meta_endpoint(app_client):
    client, proj = app_client
    r = client.get("/api/meta")
    assert r.status_code == 200
    assert r.json() == {"project_root": str(proj.resolve()), "sdk_root": str(SDK_ROOT)}


def test_overview_endpoint(app_client):
    client, _ = app_client
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["labels"] == 4
    assert "start" in body["labels"]


def test_labels_listing(app_client):
    client, _ = app_client
    r = client.get("/api/labels")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 4
    assert {l["name"] for l in body["labels"]} == {"start", "cafe_scene", "park_scene", "ending"}


def test_read_label_happy(app_client):
    client, _ = app_client
    r = client.get("/api/labels/cafe_scene")
    assert r.status_code == 200
    body = r.json()
    assert body["label"]["name"] == "cafe_scene"
    assert "label cafe_scene:" in body["source"]


def test_read_label_missing_returns_404(app_client):
    client, _ = app_client
    r = client.get("/api/labels/no_such_label")
    assert r.status_code == 404


def test_branch_graph_endpoint(app_client):
    client, _ = app_client
    r = client.get("/api/graph")
    assert r.status_code == 200
    body = r.json()
    # 4 labels in the fixture; start branches into cafe + park, both jump to ending.
    assert len(body["nodes"]) == 4
    edge_pairs = {(e["from"], e["to"]) for e in body["edges"]}
    assert ("start", "cafe_scene") in edge_pairs
    assert ("start", "park_scene") in edge_pairs
    assert ("cafe_scene", "ending") in edge_pairs
    assert ("park_scene", "ending") in edge_pairs


def test_characters_endpoint(app_client):
    client, _ = app_client
    r = client.get("/api/characters")
    assert r.status_code == 200
    vars_ = {c["var"] for c in r.json()["characters"]}
    assert vars_ == {"e", "m"}


def test_variables_endpoint(app_client):
    client, _ = app_client
    r = client.get("/api/variables")
    assert r.status_code == 200
    body = r.json()
    names = {v["name"] for v in body["variables"]}
    # default declarations from the fixture
    assert {"met_mei", "affection_mei"}.issubset(names)


def test_lint_endpoint(app_client):
    client, _ = app_client
    r = client.get("/api/lint")
    assert r.status_code == 200
    body = r.json()
    assert "stdout" in body
    assert "returncode" in body


# ---------- write endpoints -----------------------------------------------------


def test_update_character_returns_diff(app_client):
    client, proj = app_client
    r = client.patch("/api/characters/m", json={"color": "#ff8800"})
    assert r.status_code == 200
    body = r.json()
    assert "diff" in body
    assert 'color="#ff8800"' in (proj / "game/script.rpy").read_text()


def test_upsert_variable_creates_new(app_client):
    client, proj = app_client
    r = client.put("/api/variables/new_flag", json={"value": "True"})
    assert r.status_code == 200
    assert "summary" in r.json()
    assert "default new_flag = True" in (proj / "game/script.rpy").read_text()


def test_append_dialogue_returns_diff(app_client):
    client, proj = app_client
    r = client.post(
        "/api/labels/cafe_scene/dialogue",
        json={"character": "e", "text": "Wired through the inspector."},
    )
    assert r.status_code == 200
    body = r.json()
    assert "appended say-statement" in body["summary"]
    text = (proj / "game/script.rpy").read_text()
    cafe_block = text.split("label cafe_scene:")[1].split("label ")[0]
    # Reachability: must come BEFORE the trailing `jump ending`.
    assert cafe_block.index('e "Wired through the inspector."') < cafe_block.index("jump ending")


def test_swap_background_returns_diff(app_client):
    client, proj = app_client
    r = client.post("/api/labels/cafe_scene/background", json={"new_background": "bg park"})
    assert r.status_code == 200
    body = r.json()
    assert "swapped background" in body["summary"]
    text = (proj / "game/script.rpy").read_text()
    cafe_block = text.split("label cafe_scene:")[1].split("label ")[0]
    assert "scene bg park" in cafe_block
    assert "scene bg cafe" not in cafe_block


def test_set_scene_music_returns_diff(app_client):
    client, proj = app_client
    r = client.post(
        "/api/labels/cafe_scene/music",
        json={"asset": "audio/spring_theme.ogg", "loop": True, "validate_asset": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    text = (proj / "game/script.rpy").read_text()
    assert 'play music "audio/spring_theme.ogg" loop' in text


# ---------- preview lifecycle ---------------------------------------------------


def test_preview_status_initially_idle(app_client):
    client, _ = app_client
    r = client.get("/api/preview")
    assert r.status_code == 200
    assert r.json() == {"running": False}


def test_stop_preview_when_idle_is_safe(app_client):
    client, _ = app_client
    r = client.delete("/api/preview")
    assert r.status_code == 200
    assert r.json() == {"running": False}


# ---------- websocket file watcher ---------------------------------------------


def test_ws_pushes_file_change_event(app_client):
    """Touching a watched file in game/ must produce a file_change WS message."""
    client, proj = app_client
    with client.websocket_connect("/ws") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"

        # Modify a watched file. The watcher uses `os.path.getmtime`, so a real
        # write (not just touch) is the most reliable trigger across platforms.
        target = proj / "game" / "script.rpy"
        target.write_text(target.read_text() + "\n# trailing comment from test\n")

        # The watchdog observer fires on a separate thread; give it a moment.
        deadline = time.time() + 5.0
        change_evt = None
        while time.time() < deadline:
            try:
                msg = ws.receive_json()
            except Exception:
                break
            if msg.get("type") == "file_change":
                change_evt = msg
                break
        assert change_evt is not None, "no file_change event arrived within 5s"
        assert change_evt["kind"] == "rpy"
        assert change_evt["path"] == "game/script.rpy"


# ---------- fallback shape checks ----------------------------------------------


def test_invalid_json_body_returns_422(app_client):
    """FastAPI/Pydantic should reject malformed payloads with 422, not 500."""
    client, _ = app_client
    r = client.put("/api/variables/foo", content="not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    detail = r.json()
    assert isinstance(detail, dict)


def test_unknown_route_returns_404(app_client):
    client, _ = app_client
    r = client.get("/api/does-not-exist")
    assert r.status_code in (404, 405)


def test_response_shape_is_json(app_client):
    """Every API endpoint should return a JSON content-type so the SPA parses it."""
    client, _ = app_client
    for path in ("/api/meta", "/api/overview", "/api/preview"):
        r = client.get(path)
        assert r.headers["content-type"].startswith("application/json"), path
        # Smoke parse to confirm it's valid JSON.
        json.loads(r.content)
