#!/usr/bin/env python3
"""Drive the renpy-mcp tool surface against a project that ships REAL assets.

Differs from `integration_drive.py` in one important way: the project
already has fal-generated `bg harbor`, `mara neutral` (sprite), and
`harbor_theme.ogg` (BGM) before we author. The driver references those
assets through MCP tools and verifies that lint comes back CLEAN —
i.e. the missing-asset signal is reliable when assets actually exist.

Usage:
    RENPY_SDK=/home/alex/renpy-sdk \
    python scripts/real_vn_drive.py /tmp/real_vn_workspace/test_vn

Expects the project to already contain:
    game/images/bg_harbor.jpg
    game/images/mara neutral.png
    game/audio/harbor_theme.ogg
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scaffold import scaffold_project
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import lifecycle, tier1_read, tier2_write, tier3_intents
from renpy_mcp.tools.registry import ToolRegistry


async def call(reg: ToolRegistry, name: str, args: dict | None = None) -> dict:
    contents = await reg.call(name, args or {})
    assert len(contents) == 1
    return json.loads(contents[0].text)


def expect(label: str, ok_cond: bool, payload) -> bool:
    """Print a one-line status. Returns True on pass, False on fail."""
    if ok_cond:
        print(f"  PASS  {label}")
        return True
    print(f"  FAIL  {label}")
    print(f"        payload: {payload}")
    return False


async def main(project: Path) -> int:
    sdk_root = Path(os.environ.get("RENPY_SDK", str(Path.home() / "renpy-sdk")))
    if not (sdk_root / "renpy.sh").is_file():
        print(f"FATAL: no renpy.sh at {sdk_root}/renpy.sh")
        return 2

    # Verify the assets are present BEFORE we scaffold/author.
    assets = {
        "bg_harbor.jpg": project / "game" / "images" / "bg_harbor.jpg",
        "mara neutral.png": project / "game" / "images" / "mara neutral.png",
        "harbor_theme.ogg": project / "game" / "audio" / "harbor_theme.ogg",
    }
    print(f"\nproject: {project}")
    for name, path in assets.items():
        if not path.is_file():
            print(f"FATAL: missing asset `{name}` at {path}")
            return 2
        print(f"  asset present: {name} ({path.stat().st_size:,} bytes)")

    print("\n=== 1. Scaffold preserves existing assets ===")
    scaffold_project(project, display_name="Harbor Test", sdk_root=sdk_root)
    failures = 0
    for name, path in assets.items():
        if not expect(f"asset survived scaffold: {name}", path.is_file(), path):
            failures += 1

    cfg = ServerConfig(project_root=project.resolve(), sdk_root=sdk_root.resolve())
    idx = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, idx)
    tier2_write.register(reg, cfg, idx)
    tier3_intents.register(reg, cfg, idx)
    lifecycle.register(reg, cfg, idx)
    lifecycle._preview_proc = None  # type: ignore[attr-defined]
    lifecycle._warp_temp_active = False  # type: ignore[attr-defined]

    print("\n=== 2. Auto-detect picks up the asset filenames ===")
    images = await call(reg, "list_images", {})
    auto_names = {
        i["name"] for i in images.get("images", []) if i.get("kind") == "auto"
    }
    if not expect("`bg harbor` auto-detected", "bg harbor" in auto_names, auto_names):
        failures += 1
    if not expect("`mara neutral` auto-detected", "mara neutral" in auto_names, auto_names):
        failures += 1

    print("\n=== 3. Author a small VN referencing the real assets ===")
    out = await call(
        reg,
        "add_character",
        {"var": "mara", "display_name": "Mara", "color": "#5a8c4f"},
    )
    if not expect("add_character → Mara", "summary" in out, out):
        failures += 1

    out = await call(
        reg,
        "create_scene",
        {
            "name": "harbor_intro",
            "background": "bg harbor",
            "music": "audio/harbor_theme.ogg",
            "characters": ["mara neutral"],
            "dialogue": [
                {"character": "mara", "text": "The boats came back early tonight."},
                {"character": "mara", "text": "That hasn't happened since you left."},
            ],
            "ends_with": "return",
        },
    )
    if not expect("create_scene harbor_intro (real bg + sprite + music)", "summary" in out, out):
        failures += 1

    # The SDK template's `start` body references `bg room` / `eileen happy`
    # — assets that aren't shipped with the scaffold. Just rewiring the
    # terminator (add_jump start replace_terminator=True) leaves those
    # broken references in place. Cleanest tool-driven fix is to delete
    # `start` (it has no incoming jump/call refs — it's the engine entry
    # point) and re-create it as a one-line redirect.
    out = await call(reg, "delete_label", {"label": "start"})
    if not expect("delete_label start (clean of template body)", "summary" in out, out):
        failures += 1
    out = await call(
        reg,
        "add_label",
        {"name": "start", "body": ["jump harbor_intro"]},
    )
    if not expect("add_label start → jump harbor_intro", "summary" in out, out):
        failures += 1

    print("\n=== 4. Diagnostics confirm zero missing assets ===")
    diag = await call(reg, "find_missing_assets", {})
    if not expect(
        f"find_missing_assets clean (count={diag['count']})",
        diag["count"] == 0,
        diag,
    ):
        failures += 1

    print("\n=== 5. Lint confirms a runnable game ===")
    lint = await call(reg, "get_lint_report", {})
    rc = lint.get("returncode")
    if not expect(f"lint exit code {rc}", rc == 0, lint.get("summary")):
        failures += 1

    print("\n=== 6. Inspector tree reflects the real-asset references ===")
    tree = await call(reg, "read_label_tree", {"name": "harbor_intro"})
    body_kinds = [n["kind"] for n in tree.get("body", [])]
    if not expect(
        f"intro body has scene + play + show + says: {body_kinds}",
        "scene" in body_kinds
        and "play" in body_kinds
        and "show" in body_kinds
        and body_kinds.count("say") == 2,
        body_kinds,
    ):
        failures += 1
    if not expect(
        f"shorthand.background = `bg harbor`",
        tree.get("shorthand", {}).get("background") == "bg harbor",
        tree.get("shorthand"),
    ):
        failures += 1
    if not expect(
        f"shorthand.music = `audio/harbor_theme.ogg`",
        tree.get("shorthand", {}).get("music") == "audio/harbor_theme.ogg",
        tree.get("shorthand"),
    ):
        failures += 1

    print("\n=== 7. Build a real distribution ===")
    out = await call(reg, "build_distribution", {"targets": ["pc"]})
    if not expect(
        f"renpy distribute exit={out.get('returncode')}",
        out.get("returncode") == 0,
        out.get("stderr", "")[:200],
    ):
        failures += 1

    artifacts: list[Path] = []
    parent = project.parent
    if parent.is_dir():
        for d in parent.iterdir():
            if d.is_dir() and d.name.endswith("-dists"):
                for f in d.iterdir():
                    if f.suffix.lower() in (".zip", ".bz2"):
                        artifacts.append(f)
    if not expect(
        f"distribute artifact(s): {[a.name for a in artifacts]}",
        bool(artifacts),
        parent,
    ):
        failures += 1

    # Verify the artifact is real bytes (not a 0-byte stub).
    for a in artifacts:
        size_mb = a.stat().st_size / 1_000_000
        if not expect(
            f"{a.name} is {size_mb:.2f} MB (>= 0.5 MB suggests real assets baked in)",
            size_mb >= 0.5,
            a.stat().st_size,
        ):
            failures += 1

    print()
    if failures:
        print(f"FAIL: {failures} step(s) failed")
        return 1
    print("ALL GREEN — real-asset VN authored, lint clean, distribute produced a real artifact.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: real_vn_drive.py <project_path>")
        sys.exit(2)
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
