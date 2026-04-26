from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shlex
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
    parser.add_argument(
        "--print-config",
        choices=["claude-code", "hermes"],
        default=None,
        help=(
            "Print a ready-to-paste MCP-server config snippet for the named "
            "harness, using the current --sdk / --project / --games-root "
            "values, then exit. `claude-code` emits .mcp.json; `hermes` "
            "emits the YAML block to merge into ~/.hermes/config.yaml."
        ),
    )
    args = parser.parse_args()

    if args.print_config:
        return _print_harness_config(args)

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


def _print_harness_config(args: argparse.Namespace) -> int:
    """Emit a ready-to-paste MCP-server config snippet for `args.print_config`.

    Resolves the same default values the server itself would resolve so the
    snippet works without further user editing. Goes to stdout (not stderr —
    this output is meant to be piped into a config file). Never spawns the
    server; just prints and returns 0.
    """
    cwd = Path.cwd()
    # Use sys.executable as-is — resolving the symlink chain on a venv
    # python lands at the system python, which doesn't have renpy_mcp
    # installed. The venv's `bin/python` is the path we want the harness
    # to launch.
    python = Path(sys.executable)
    sdk = args.sdk or _default_sdk()
    games_root = (args.games_root or (cwd / DEFAULT_GAMES_SUBDIR)).resolve()
    project = args.project.resolve() if args.project else None

    extra_args: list[str] = ["-m", "renpy_mcp"]
    if sdk is not None:
        extra_args += ["--sdk", str(sdk.resolve())]
    extra_args += ["--games-root", str(games_root)]
    if project is not None:
        extra_args += ["--project", str(project)]
    if args.tiers != DEFAULT_TIERS:
        extra_args += ["--tiers", ",".join(str(t) for t in sorted(args.tiers))]

    if args.print_config == "claude-code":
        snippet = {
            "mcpServers": {
                "renpy": {
                    "type": "stdio",
                    "command": str(python),
                    "args": extra_args,
                }
            }
        }
        print("// Drop this in .mcp.json next to the directory you open Claude Code in.")
        print("// Auto-loaded on session start; tools register as mcp__renpy__<tool>.")
        print(json.dumps(snippet, indent=2))
        if sdk is None:
            print(
                "// NOTE: --sdk was omitted; set $RENPY_SDK in your shell or "
                "rerun with --sdk PATH so the server can find Ren'Py.",
                file=sys.stderr,
            )
        return 0

    # hermes-agent: YAML block to merge into ~/.hermes/config.yaml.
    yaml_args = "\n      ".join(f"- {shlex.quote(a)}" for a in extra_args)
    print("# Merge into ~/.hermes/config.yaml under `mcp_servers:`. After")
    print("# editing, run `hermes mcp test renpy` to verify the connection.")
    print("mcp_servers:")
    print("  renpy:")
    print(f"    command: {shlex.quote(str(python))}")
    print(f"    args:")
    print(f"      {yaml_args}")
    print("    timeout: 180")
    print("    connect_timeout: 60")
    if sdk is None:
        print(
            "# NOTE: --sdk was omitted; set $RENPY_SDK in hermes' .env or "
            "re-run print-config with --sdk PATH.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
