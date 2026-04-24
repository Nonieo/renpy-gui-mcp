from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_TIERS = frozenset({1, 2, 3})


def sdk_launcher_name() -> str:
    """Return the SDK launcher script appropriate for the current OS."""
    return "renpy.exe" if platform.system() == "Windows" else "renpy.sh"


@dataclass(frozen=True)
class ServerConfig:
    project_root: Path
    sdk_root: Path
    tiers: frozenset[int] = field(default_factory=lambda: DEFAULT_TIERS)

    @property
    def game_dir(self) -> Path:
        return self.project_root / "game"

    @property
    def sdk_launcher(self) -> Path:
        return self.sdk_root / sdk_launcher_name()

    def validate(self) -> None:
        if not self.project_root.is_dir():
            raise ValueError(f"project root does not exist: {self.project_root}")
        if not self.game_dir.is_dir():
            raise ValueError(
                f"project root is not a Ren'Py project (no game/ subdir): {self.project_root}"
            )
        if not self.sdk_launcher.is_file():
            raise ValueError(
                f"SDK root missing launcher `{sdk_launcher_name()}`: {self.sdk_root}"
            )
