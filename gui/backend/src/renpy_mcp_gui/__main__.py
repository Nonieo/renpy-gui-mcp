"""CLI entry point for the renpy-mcp-gui backend."""

from __future__ import annotations

import argparse
import logging
import sys
import webbrowser
from pathlib import Path

import uvicorn

from .app import build_app


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="renpy-mcp-gui")
    parser.add_argument("--project", type=Path, required=True, help="Ren'Py project root (contains game/)")
    parser.add_argument("--sdk", type=Path, required=True, help="Ren'Py SDK root (contains renpy.sh / renpy.exe)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--static-dir",
        type=Path,
        help="Path to a built frontend (Vite `dist/`). If omitted, only the API is served.",
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser on startup.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    project = args.project.resolve()
    sdk = args.sdk.resolve()
    if not (project / "game").is_dir():
        print(f"renpy-mcp-gui: not a Ren'Py project (no game/ subdir): {project}", file=sys.stderr)
        return 2
    if not (sdk / "renpy.sh").is_file() and not (sdk / "renpy.exe").is_file():
        print(f"renpy-mcp-gui: SDK root missing renpy.sh/renpy.exe: {sdk}", file=sys.stderr)
        return 2

    static_dir = args.static_dir.resolve() if args.static_dir else None
    app = build_app(project, sdk, static_dir)

    if not args.no_browser:
        url = f"http://{args.host}:{args.port}/"
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
