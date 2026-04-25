"""Compute a label/jump graph from the project for the Story Map panel.

Backed by `read_label_tree` (Phase 0) — each label's typed body gives us
both the inferred `kind` (start/scene/choice/ending) for badges and the
deduplicated `outgoing_targets` for edges. Walking the tree directly via
`iter_statements` further down lets us tag each edge by its statement
kind (`jump` / `call`) so the frontend can render call edges
distinctly.
"""

from __future__ import annotations

from typing import Any

from .mcp_client import RenpyMcpClient


async def compute_branch_graph(client: RenpyMcpClient) -> dict[str, Any]:
    """Return a {nodes, edges} graph derived from every label in the project."""
    listing = await client.call("list_labels", {})
    labels = listing.get("labels", [])

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for label in labels:
        tree = await client.call("read_label_tree", {"name": label["name"]})
        if "error" in tree:
            # A duplicate-name label or transient I/O error; surface a node
            # without a kind so the frontend can still place it.
            nodes.append(
                {
                    "id": label["name"],
                    "file": label["file"],
                    "start_line": label["start_line"],
                    "end_line": label["end_line"],
                    "say_count": label["say_count"],
                    "kind": "scene",
                }
            )
            continue

        nodes.append(
            {
                "id": label["name"],
                "file": label["file"],
                "start_line": label["start_line"],
                "end_line": label["end_line"],
                "say_count": label["say_count"],
                "kind": tree.get("kind", "scene"),
            }
        )

        # Extract jump/call edges by walking the body statements. Each
        # edge carries the source line so the Story Map can call
        # `redirect_jump(file, line, new_target)` when an edge is dragged.
        for stmt in _iter_jump_call(tree.get("body", [])):
            target = stmt["target"]
            kind = stmt["kind"]  # "jump" or "call"
            line = stmt["line"]
            key = (label["name"], target, kind, line)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(
                {
                    "from": label["name"],
                    "to": target,
                    "kind": kind,
                    "from_file": label["file"],
                    "from_line": line,
                }
            )

    return {"nodes": nodes, "edges": edges}


def _iter_jump_call(body: list[dict[str, Any]]):
    """Depth-first walk over a parsed body, yielding only jump/call nodes.

    Mirrors the recursion shape of `project.label_tree.iter_statements`
    so the GUI backend doesn't depend on importing the MCP server's
    internals — the body shape is part of the read_label_tree contract.
    """
    for node in body:
        if node["kind"] in ("jump", "call"):
            yield node
        elif node["kind"] == "menu":
            for choice in node["choices"]:
                yield from _iter_jump_call(choice["body"])
        elif node["kind"] == "if":
            for branch in node["branches"]:
                yield from _iter_jump_call(branch["body"])
