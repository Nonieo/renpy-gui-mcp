"""Cross-tier registry guards.

The registry's `add` raises ValueError on duplicate names, so building a
registry with every tier already enforces uniqueness at the collection
level. These tests assert the same property at the *module* level so a
drift like "Tier 2 and Tier 3 both define `set_scene_music`" gets caught
with a tier-aware error message instead of an opaque "duplicate tool
name" from the registry.
"""

from __future__ import annotations

from renpy_mcp.config import ServerConfig
from renpy_mcp.project.scanner import ProjectIndex
from renpy_mcp.tools import (
    lifecycle,
    tier1_read,
    tier2_write,
    tier3_intents,
    tier4_escape,
)
from renpy_mcp.tools.registry import ToolRegistry

from .conftest import FIXTURE_ROOT, SDK_ROOT


def _names_for(register_fn) -> set[str]:
    cfg = ServerConfig(project_root=FIXTURE_ROOT.resolve(), sdk_root=SDK_ROOT)
    reg = ToolRegistry()
    register_fn(reg, cfg, ProjectIndex(cfg))
    return set(reg._tools.keys())


def test_no_name_collisions_across_tiers():
    cfg = ServerConfig(project_root=FIXTURE_ROOT.resolve(), sdk_root=SDK_ROOT)
    index = ProjectIndex(cfg)

    per_tier: dict[str, set[str]] = {}
    for label, register in [
        ("tier1", tier1_read.register),
        ("lifecycle", lifecycle.register),
        ("tier2", tier2_write.register),
        ("tier3", tier3_intents.register),
        ("tier4", tier4_escape.register),
    ]:
        reg = ToolRegistry()
        register(reg, cfg, index)
        per_tier[label] = set(reg._tools.keys())

    seen: dict[str, str] = {}
    collisions: list[str] = []
    for label, names in per_tier.items():
        for name in names:
            if name in seen:
                collisions.append(f"`{name}` registered in both {seen[name]} and {label}")
            else:
                seen[name] = label
    assert not collisions, "tier name collisions:\n  " + "\n  ".join(collisions)


def test_full_registry_accepts_every_tier():
    """Building one registry with all tiers must not raise."""
    cfg = ServerConfig(
        project_root=FIXTURE_ROOT.resolve(),
        sdk_root=SDK_ROOT,
        tiers=frozenset({1, 2, 3, 4}),
    )
    index = ProjectIndex(cfg)
    reg = ToolRegistry()
    tier1_read.register(reg, cfg, index)
    lifecycle.register(reg, cfg, index)
    tier2_write.register(reg, cfg, index)
    tier3_intents.register(reg, cfg, index)
    tier4_escape.register(reg, cfg, index)
    assert "add_condition_branch" in reg._tools
    assert reg._tools["add_condition_branch"].input_schema["required"] == ["label", "branches"]
