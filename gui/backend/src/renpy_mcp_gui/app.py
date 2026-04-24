"""FastAPI app wiring the MCP client + REST + WebSocket into one process.

REST routes are thin: validate input, call into the MCP client, return
the JSON the MCP tool produced (with light reshaping for the panels
that need it). WebSocket pushes filesystem-change events so the frontend
can refetch live.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .graph import compute_branch_graph
from .mcp_client import RenpyMcpClient
from .watcher import FileEvent, ProjectWatcher

log = logging.getLogger("renpy_mcp_gui.app")


class AppState:
    client: RenpyMcpClient
    watcher: ProjectWatcher
    project_root: Path
    sdk_root: Path
    ws_clients: set[WebSocket]
    fanout_task: asyncio.Task | None = None


state = AppState()


class AddCharacter(BaseModel):
    var: str
    display_name: str
    color: str | None = None
    image_tag: str | None = None
    extra_kwargs: dict[str, str] | None = None
    file: str | None = None


class UpdateCharacter(BaseModel):
    display_name: str | None = None
    color: str | None = None


class AddDialogueLine(BaseModel):
    character: str | None = None  # omit for narration
    text: str


class SwapBackground(BaseModel):
    new_background: str


class SetSceneMusic(BaseModel):
    asset: str  # empty string emits `stop music`
    fadein: float | None = None
    loop: bool = False
    validate_asset: bool = True


class SetVariableDefault(BaseModel):
    value: str
    file: str | None = None


def _make_lifespan(project_root: Path, sdk_root: Path):
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        state.project_root = project_root
        state.sdk_root = sdk_root
        state.ws_clients = set()
        state.client = RenpyMcpClient(project_root, sdk_root)
        await state.client.start()
        state.watcher = ProjectWatcher(project_root)
        state.watcher.start(asyncio.get_running_loop())
        state.fanout_task = asyncio.create_task(_fanout_file_events())
        try:
            yield
        finally:
            if state.fanout_task is not None:
                state.fanout_task.cancel()
            state.watcher.stop()
            await state.client.stop()

    return lifespan


async def _fanout_file_events() -> None:
    """Forward watcher events to every connected WebSocket client."""
    try:
        while True:
            evt: FileEvent = await state.watcher.queue.get()
            payload = json.dumps({"type": "file_change", "kind": evt.kind, "action": evt.action, "path": evt.path})
            for ws in list(state.ws_clients):
                try:
                    await ws.send_text(payload)
                except Exception:
                    state.ws_clients.discard(ws)
    except asyncio.CancelledError:
        pass


def build_app(project_root: Path, sdk_root: Path, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="renpy-mcp-gui",
        version="0.1.0",
        lifespan=_make_lifespan(project_root, sdk_root),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # local dev only
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------- read endpoints ----------

    @app.get("/api/overview")
    async def overview() -> Any:
        return await state.client.call("get_project_overview")

    @app.get("/api/labels")
    async def list_labels() -> Any:
        return await state.client.call("list_labels")

    @app.get("/api/labels/{name}")
    async def read_label(name: str) -> Any:
        payload = await state.client.call("read_label", {"name": name})
        if "error" in payload:
            raise HTTPException(404, payload["error"])
        return payload

    @app.get("/api/graph")
    async def branch_graph() -> Any:
        return await compute_branch_graph(state.client)

    @app.get("/api/characters")
    async def list_characters() -> Any:
        return await state.client.call("list_characters")

    @app.get("/api/images")
    async def list_images() -> Any:
        return await state.client.call("list_images")

    @app.get("/api/audio")
    async def list_audio() -> Any:
        return await state.client.call("list_audio")

    @app.get("/api/variables")
    async def list_variables() -> Any:
        return await state.client.call("list_variables")

    @app.get("/api/screens")
    async def list_screens() -> Any:
        return await state.client.call("list_screens")

    @app.get("/api/lint")
    async def lint() -> Any:
        return await state.client.call("get_lint_report")

    # ---------- write endpoints ----------

    @app.post("/api/characters")
    async def add_character(body: AddCharacter = Body(...)) -> Any:
        return await state.client.call("add_character", body.model_dump(exclude_none=True))

    @app.patch("/api/characters/{var}")
    async def update_character(var: str, body: UpdateCharacter = Body(...)) -> Any:
        args = {"var": var, **body.model_dump(exclude_none=True)}
        return await state.client.call("update_character", args)

    @app.post("/api/labels/{name}/dialogue")
    async def append_dialogue(name: str, body: AddDialogueLine = Body(...)) -> Any:
        args: dict[str, Any] = {"label": name, "text": body.text}
        if body.character is not None:
            args["character"] = body.character
        return await state.client.call("add_say", args)

    @app.post("/api/labels/{name}/background")
    async def swap_label_background(name: str, body: SwapBackground = Body(...)) -> Any:
        return await state.client.call(
            "swap_background", {"label": name, "new_background": body.new_background}
        )

    @app.post("/api/labels/{name}/music")
    async def set_label_music(name: str, body: SetSceneMusic = Body(...)) -> Any:
        args: dict[str, Any] = {
            "label": name,
            "asset": body.asset,
            "loop": body.loop,
            "validate_asset": body.validate_asset,
        }
        if body.fadein is not None:
            args["fadein"] = body.fadein
        return await state.client.call("set_scene_music", args)

    @app.put("/api/variables/{name}")
    async def upsert_variable_default(name: str, body: SetVariableDefault = Body(...)) -> Any:
        args: dict[str, Any] = {"name": name, "value": body.value}
        if body.file is not None:
            args["file"] = body.file
        return await state.client.call("set_variable_default", args)

    # Asset upload — copy a user-supplied file into the project's assets dir.
    # Kept tiny on purpose; the MCP server doesn't have an asset-upload tool.
    from fastapi import UploadFile, File, Form

    @app.post("/api/assets/upload")
    async def upload_asset(
        kind: str = Form(...),  # "image" | "audio"
        upload: UploadFile = File(...),
    ) -> Any:
        if kind not in ("image", "audio"):
            raise HTTPException(400, "kind must be `image` or `audio`")
        subdir = "images" if kind == "image" else "audio"
        target_dir = project_root / "game" / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        if not upload.filename:
            raise HTTPException(400, "upload missing a filename")
        target = target_dir / Path(upload.filename).name
        target.write_bytes(await upload.read())
        return {"asset_path": f"game/{subdir}/{target.name}", "size_bytes": target.stat().st_size}

    # ---------- websocket ----------

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        state.ws_clients.add(websocket)
        try:
            await websocket.send_json({"type": "ready", "project_root": str(project_root)})
            while True:
                # Drain anything the client sends; we don't act on it but we need to
                # keep the receive side alive so we notice disconnects promptly.
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            state.ws_clients.discard(websocket)

    # ---------- meta ----------

    @app.get("/api/meta")
    async def meta() -> Any:
        return {
            "project_root": str(project_root),
            "sdk_root": str(sdk_root),
        }

    # ---------- static frontend ----------

    if static_dir is not None and static_dir.is_dir():
        # Serve the production build (`vite build`'s `dist/`) under /.
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(path: str = ""):
            # Anything that doesn't look like an /api/* call falls through to index.html
            # so client-side routing can take over.
            if path.startswith("api/") or path.startswith("ws"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            target = static_dir / path
            if path and target.is_file():
                return FileResponse(target)
            return FileResponse(static_dir / "index.html")

    return app
