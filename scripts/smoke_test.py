#!/usr/bin/env python3
"""Smoke test for a renpy-mcp install.

Spawns the server over stdio against a Ren'Py project, runs a handful of
read-only tools, and prints PASS / FAIL with an explanation. Intended for
new installs to verify the bare wiring before touching real projects.

Usage:
    python scripts/smoke_test.py --project <path> --sdk <path>
    # or after `pip install -e .`, override the spawn command:
    python scripts/smoke_test.py --project <path> --sdk <path> --command renpy-mcp
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _print_pass(label: str, detail: str = "") -> None:
    print(f"  PASS  {label}{(' — ' + detail) if detail else ''}")


def _print_fail(label: str, detail: str) -> None:
    print(f"  FAIL  {label} — {detail}")


async def _run(project: Path, sdk: Path, command: str | None) -> int:
    if command:
        params = StdioServerParameters(
            command=command,
            args=["--project", str(project), "--sdk", str(sdk)],
        )
    else:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "renpy_mcp", "--project", str(project), "--sdk", str(sdk)],
        )

    failures = 0

    print("renpy-mcp smoke test")
    print(f"  project: {project}")
    print(f"  sdk:     {sdk}")
    print(f"  command: {command or f'{sys.executable} -m renpy_mcp'}")
    print()

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                tool_names = {t.name for t in tools}
                _print_pass(f"server handshake completed; {len(tools)} tools registered")

                required = {"get_project_overview", "list_labels", "read_label"}
                missing = required - tool_names
                if missing:
                    _print_fail("required Tier 1 tools present", f"missing {sorted(missing)}")
                    failures += 1
                else:
                    _print_pass("required Tier 1 tools present")

                r = await session.call_tool("get_project_overview", {})
                payload = json.loads(r.content[0].text)
                if "counts" in payload:
                    _print_pass(
                        "get_project_overview",
                        f"{payload['counts']['labels']} labels, "
                        f"{payload['counts']['characters']} characters, "
                        f"{len(payload['files'])} files",
                    )
                else:
                    _print_fail("get_project_overview", payload.get("error", "no counts in response"))
                    failures += 1

                r = await session.call_tool("list_labels", {})
                payload = json.loads(r.content[0].text)
                if "labels" in payload:
                    _print_pass("list_labels", f"count={payload['count']}")
                else:
                    _print_fail("list_labels", payload.get("error", "no labels in response"))
                    failures += 1
    except Exception as exc:
        _print_fail("server startup", repr(exc))
        return 1

    print()
    if failures:
        print(f"FAILED ({failures} check{'s' if failures != 1 else ''})")
        return 1
    print("PASS — server is wired correctly.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="smoke_test.py")
    parser.add_argument("--project", type=Path, required=True, help="Ren'Py project root (contains game/)")
    parser.add_argument("--sdk", type=Path, required=True, help="Ren'Py SDK root (contains renpy.sh / renpy.exe)")
    parser.add_argument(
        "--command",
        help="Override the server command. Default spawns `python -m renpy_mcp`.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.project.resolve(), args.sdk.resolve(), args.command))


if __name__ == "__main__":
    sys.exit(main())
