from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from .config import DEFAULT_GAMES_SUBDIR, DEFAULT_PROJECT_SLUG, DEFAULT_TIERS, ServerConfig
from .project.scaffold import scaffold_project
from .server import run_stdio


def _configure_logging(verbose: bool) -> None:
    """Send all logging to stderr — stdout is reserved for the MCP wire."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_tiers(raw: str) -> frozenset[int]:
    tiers = {int(x) for x in raw.split(",") if x.strip()}
    bad = tiers - {1, 2, 3, 4}
    if bad:
        raise argparse.ArgumentTypeError(f"unknown tiers: {sorted(bad)}; pick from 1-4")
    return frozenset(tiers)


def _default_sdk() -> Path | None:
    """Return the SDK path from $RENPY_SDK if set, else None."""
    env = os.environ.get("RENPY_SDK")
    return Path(env).resolve() if env else None


def main() -> int:
    parser = argparse.ArgumentParser(prog="renpy-mcp")
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help=(
            "Path to a Ren'Py project root (the dir containing game/). "
            "Optional: if omitted, defaults to "
            f"`<cwd>/{DEFAULT_GAMES_SUBDIR}/{DEFAULT_PROJECT_SLUG}/` and is "
            "auto-scaffolded when missing."
        ),
    )
    parser.add_argument(
        "--games-root",
        type=Path,
        default=None,
        help=(
            "Directory under which `new_project` drops new projects. "
            f"Defaults to `<cwd>/{DEFAULT_GAMES_SUBDIR}/`."
        ),
    )
    parser.add_argument(
        "--sdk",
        type=Path,
        default=None,
        help=(
            "Path to the Ren'Py SDK (the dir containing renpy.sh). "
            "Optional: falls back to $RENPY_SDK when unset."
        ),
    )
    parser.add_argument(
        "--tiers",
        type=_parse_tiers,
        default=DEFAULT_TIERS,
        help="comma-separated tier list to load (default: 1,2,3)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG-level stderr logging")
    args = parser.parse_args()

    _configure_logging(args.verbose)
    log = logging.getLogger("renpy_mcp")

    cwd = Path.cwd()
    games_root = (args.games_root or (cwd / DEFAULT_GAMES_SUBDIR)).resolve()
    sdk_root = (args.sdk or _default_sdk())
    if sdk_root is None:
        log.error(
            "startup: --sdk is required (or set $RENPY_SDK); point it at the Ren'Py SDK directory"
        )
        return 2

    project_root = (args.project or (games_root / DEFAULT_PROJECT_SLUG)).resolve()
    if not (project_root / "game").is_dir():
        games_root.mkdir(parents=True, exist_ok=True)
        summary = scaffold_project(project_root, sdk_root=sdk_root.resolve())
        log.info("startup: %s", summary)

    config = ServerConfig(
        project_root=project_root,
        sdk_root=sdk_root.resolve(),
        tiers=args.tiers,
        games_root=games_root,
    )
    try:
        config.validate()
    except ValueError as exc:
        log.error("startup: %s", exc)
        return 2

    log.info(
        "starting stdio server | project=%s games_root=%s sdk=%s tiers=%s",
        config.project_root,
        config.games_root,
        config.sdk_root,
        sorted(config.tiers),
    )
    asyncio.run(run_stdio(config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
