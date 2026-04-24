"""Compute a label/jump graph from the project for the Story Map panel.

We don't have a Tier 1 `get_branch_graph` tool yet, so the GUI backend
orchestrates `list_labels` + `read_label` and parses the source for
outgoing edges. When the underlying MCP server grows that tool, this
module shrinks to one call.
"""

from __future__ import annotations

import re
from typing import Any

from .mcp_client import RenpyMcpClient

# Outgoing-edge patterns inside a label body. Word-boundary so `e jumping`
# doesn't match `jump`.
_JUMP_RE = re.compile(r"^\s*jump\s+(\w+)\s*$")
_CALL_RE = re.compile(r"^\s*call\s+(\w+)\b.*$")
_MENU_CHOICE_JUMP_RE = re.compile(r"^\s*jump\s+(\w+)\s*$")


async def compute_branch_graph(client: RenpyMcpClient) -> dict[str, Any]:
    """Return a {nodes, edges} graph derived from every label in the project."""
    listing = await client.call("list_labels", {})
    labels = listing.get("labels", [])

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for label in labels:
        nodes.append(
            {
                "id": label["name"],
                "file": label["file"],
                "start_line": label["start_line"],
                "end_line": label["end_line"],
                "say_count": label["say_count"],
            }
        )

        body = await client.call("read_label", {"name": label["name"]})
        source = body.get("source", "")
        for line in source.splitlines()[1:]:  # skip the header
            for pattern, kind in (
                (_JUMP_RE, "jump"),
                (_CALL_RE, "call"),
                (_MENU_CHOICE_JUMP_RE, "menu_jump"),
            ):
                m = pattern.match(line)
                if m:
                    target = m.group(1)
                    key = (label["name"], target, kind)
                    if key not in seen_edges:
                        seen_edges.add(key)
                        edges.append({"from": label["name"], "to": target, "kind": kind})
                    break

    return {"nodes": nodes, "edges": edges}
