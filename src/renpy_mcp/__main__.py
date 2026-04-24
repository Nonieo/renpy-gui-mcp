from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import DEFAULT_TIERS, ServerConfig
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="renpy-mcp")
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="path to a Ren'Py project root (the dir containing game/)",
    )
    parser.add_argument(
        "--sdk",
        type=Path,
        required=True,
        help="path to the Ren'Py SDK (the dir containing renpy.sh)",
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

    config = ServerConfig(
        project_root=args.project.resolve(),
        sdk_root=args.sdk.resolve(),
        tiers=args.tiers,
    )
    try:
        config.validate()
    except ValueError as exc:
        log.error("startup: %s", exc)
        return 2

    log.info(
        "starting stdio server | project=%s sdk=%s tiers=%s",
        config.project_root,
        config.sdk_root,
        sorted(config.tiers),
    )
    asyncio.run(run_stdio(config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
