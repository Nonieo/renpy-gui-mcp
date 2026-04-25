"""RPBuilder Launcher.

A novice-friendly entry point. Picks the Ren'Py SDK location and a
project to open, remembers both choices in a per-user config, then
hands off to the existing `renpy-mcp-gui` server.

Two modes:
  * Tkinter window (default — Tk ships with most Python installs)
  * Text-based prompts (fallback when Tk isn't importable, or via
    `--terminal` / `RPBUILDER_TERMINAL=1`)

Config lives at:
  Linux/Mac: $XDG_CONFIG_HOME/renpy-mcp/launcher.json
             (defaults to ~/.config/renpy-mcp/launcher.json)
  Windows:   %APPDATA%/renpy-mcp/launcher.json

The file shape is intentionally trivial so a user can edit it by hand
if it ever gets stuck. No secrets land here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_VERSION = 1
RECENT_LIMIT = 10


# ---------- config persistence ------------------------------------------------


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        return base / "renpy-mcp"
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "renpy-mcp"


def config_path() -> Path:
    return config_dir() / "launcher.json"


@dataclass
class LauncherConfig:
    sdk_path: str | None = None
    recent_projects: list[str] = field(default_factory=list)
    version: int = CONFIG_VERSION

    @classmethod
    def load(cls) -> "LauncherConfig":
        p = config_path()
        if not p.is_file():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(
            sdk_path=data.get("sdk_path") or None,
            recent_projects=[str(x) for x in (data.get("recent_projects") or []) if x],
            version=int(data.get("version", CONFIG_VERSION)),
        )

    def save(self) -> None:
        p = config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sdk_path": self.sdk_path,
            "recent_projects": self.recent_projects,
            "version": CONFIG_VERSION,
        }
        p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def remember_project(self, path: str) -> None:
        path = str(Path(path).resolve())
        self.recent_projects = [path] + [p for p in self.recent_projects if p != path]
        del self.recent_projects[RECENT_LIMIT:]


# ---------- validation --------------------------------------------------------


def sdk_launcher_filename() -> str:
    return "renpy.exe" if sys.platform == "win32" else "renpy.sh"


def validate_sdk(path: str | None) -> bool:
    if not path:
        return False
    p = Path(path).expanduser()
    return p.is_dir() and (p / sdk_launcher_filename()).is_file()


def validate_project(path: str | None) -> bool:
    if not path:
        return False
    p = Path(path).expanduser()
    return p.is_dir() and (p / "game").is_dir()


def scaffold_empty_project(path: Path) -> None:
    """Create the minimum a project needs so renpy-mcp can bind to it.

    The full SDK template is copied lazily by `new_project` once the
    GUI launches; here we just give the launcher a folder it can hand
    off without a "no game/" rejection.
    """
    (path / "game").mkdir(parents=True, exist_ok=True)
    script = path / "game" / "script.rpy"
    if not script.is_file():
        script.write_text(
            "# Empty starter — call the `new_project` MCP tool from\n"
            "# inside the editor to populate this with the SDK template.\n"
            "label start:\n"
            "    \"Welcome to your new project.\"\n"
            "    return\n",
            encoding="utf-8",
        )


# ---------- handoff to the GUI server ----------------------------------------


def spawn_gui(sdk: str, project: str) -> int:
    """Replace the launcher process with the GUI server."""
    args = ["--project", project, "--sdk", sdk]
    # Prefer the installed entry point, fall back to module form.
    candidates = [
        ["renpy-mcp-gui", *args],
        [sys.executable, "-m", "renpy_mcp_gui", *args],
    ]
    last_err: Exception | None = None
    for cmd in candidates:
        try:
            os.execvp(cmd[0], cmd)
        except FileNotFoundError as exc:
            last_err = exc
            continue
    print(f"\nfailed to launch the GUI server: {last_err}", file=sys.stderr)
    return 2


# ---------- terminal launcher -------------------------------------------------


def _bullet(ok: bool) -> str:
    return "✓" if ok else "✗"


def run_terminal_launcher(cfg: LauncherConfig) -> int:
    print()
    print("RPBuilder Launcher")
    print("==================")
    print()
    print(f"(config: {config_path()})")
    print()

    # SDK prompt — keep asking until valid.
    while True:
        prompt = "Ren'Py SDK location"
        if cfg.sdk_path:
            prompt += f" [{cfg.sdk_path}]"
        prompt += ": "
        entry = input(prompt).strip()
        if not entry and cfg.sdk_path:
            entry = cfg.sdk_path
        if not entry:
            print(f"  {_bullet(False)} please enter a path")
            continue
        resolved = str(Path(entry).expanduser().resolve())
        if not validate_sdk(resolved):
            print(f"  {_bullet(False)} no {sdk_launcher_filename()} found at {resolved}")
            continue
        cfg.sdk_path = resolved
        print(f"  {_bullet(True)} SDK at {cfg.sdk_path}")
        break

    print()
    print("Choose a project:")
    annotated: list[tuple[str, bool]] = [
        (p, validate_project(p)) for p in cfg.recent_projects
    ]
    for i, (p, ok) in enumerate(annotated, start=1):
        suffix = "" if ok else "  (path missing — will be skipped if selected)"
        print(f"  {i}. {p}{suffix}")
    browse_n = len(annotated) + 1
    new_n = len(annotated) + 2
    print(f"  {browse_n}. <browse for an existing project>")
    print(f"  {new_n}. <start a new project here>")

    project: str | None = None
    while project is None:
        default_choice = "1" if annotated else str(new_n)
        choice = input(f"\nSelect [1-{new_n}, default {default_choice}]: ").strip() or default_choice
        try:
            n = int(choice)
        except ValueError:
            print(f"  {_bullet(False)} enter a number")
            continue
        if 1 <= n <= len(annotated):
            cand, ok = annotated[n - 1]
            if not ok:
                print(f"  {_bullet(False)} that project no longer exists at {cand}")
                continue
            project = cand
        elif n == browse_n:
            entry = input("  path to existing project: ").strip()
            if not entry:
                continue
            resolved = str(Path(entry).expanduser().resolve())
            if validate_project(resolved):
                project = resolved
            else:
                print(f"  {_bullet(False)} no game/ directory at {resolved}")
        elif n == new_n:
            entry = input("  path for the new project (will be created): ").strip()
            if not entry:
                continue
            resolved = Path(entry).expanduser().resolve()
            scaffold_empty_project(resolved)
            project = str(resolved)
        else:
            print(f"  {_bullet(False)} out of range")

    cfg.remember_project(project)
    cfg.save()
    print(f"\n  {_bullet(True)} launching RPBuilder for {project}")
    print("  (close the editor window to stop the server)\n")
    return spawn_gui(cfg.sdk_path or "", project)


# ---------- Tkinter launcher --------------------------------------------------


def run_tk_launcher(cfg: LauncherConfig) -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("RPBuilder Launcher")
    try:
        root.minsize(620, 460)
    except tk.TclError:
        pass

    sdk_var = tk.StringVar(value=cfg.sdk_path or "")
    sdk_status_var = tk.StringVar()
    project_var = tk.StringVar()
    project_status_var = tk.StringVar()
    launch_state = {"ready": False}

    pad = {"padx": 12, "pady": 6}
    container = ttk.Frame(root)
    container.pack(fill="both", expand=True, **pad)

    ttk.Label(
        container,
        text="RPBuilder",
        font=("TkDefaultFont", 18, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        container,
        text=(
            "Pick the Ren'Py SDK and a project to open. "
            "Both choices are saved for next time."
        ),
        foreground="#555",
    ).pack(anchor="w", pady=(0, 12))

    # ---------- SDK row ----------
    sdk_box = ttk.LabelFrame(container, text="Ren'Py SDK")
    sdk_box.pack(fill="x", pady=4)

    sdk_row = ttk.Frame(sdk_box)
    sdk_row.pack(fill="x", padx=8, pady=8)
    sdk_entry = ttk.Entry(sdk_row, textvariable=sdk_var)
    sdk_entry.pack(side="left", fill="x", expand=True)

    def browse_sdk() -> None:
        chosen = filedialog.askdirectory(
            title="Select your Ren'Py SDK folder",
            initialdir=sdk_var.get() or str(Path.home()),
        )
        if chosen:
            sdk_var.set(str(Path(chosen).resolve()))

    ttk.Button(sdk_row, text="Browse…", command=browse_sdk).pack(side="left", padx=(8, 0))
    ttk.Label(sdk_box, textvariable=sdk_status_var, foreground="#888").pack(
        anchor="w", padx=8, pady=(0, 8)
    )

    # ---------- Project row ----------
    proj_box = ttk.LabelFrame(container, text="Project")
    proj_box.pack(fill="both", expand=True, pady=4)

    list_frame = ttk.Frame(proj_box)
    list_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
    listbox = tk.Listbox(list_frame, height=6, exportselection=False, activestyle="dotbox")
    listbox.pack(side="left", fill="both", expand=True)
    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
    scroll.pack(side="right", fill="y")
    listbox.config(yscrollcommand=scroll.set)

    def populate_recent() -> None:
        listbox.delete(0, "end")
        if not cfg.recent_projects:
            listbox.insert("end", "  (no recent projects yet — Browse or New below)")
            listbox.itemconfig(0, foreground="#999")
            return
        for p in cfg.recent_projects:
            ok = validate_project(p)
            listbox.insert("end", f"  {p}" + ("" if ok else "   (missing)"))
            if not ok:
                listbox.itemconfig("end", foreground="#b00")

    populate_recent()

    def on_pick(_evt=None) -> None:
        idxs = listbox.curselection()
        if not idxs or not cfg.recent_projects:
            return
        idx = idxs[0]
        if idx >= len(cfg.recent_projects):
            return
        candidate = cfg.recent_projects[idx]
        if validate_project(candidate):
            project_var.set(candidate)

    listbox.bind("<<ListboxSelect>>", on_pick)
    listbox.bind("<Double-Button-1>", lambda e: launch())

    btn_row = ttk.Frame(proj_box)
    btn_row.pack(fill="x", padx=8, pady=(0, 4))

    def browse_project() -> None:
        chosen = filedialog.askdirectory(
            title="Select an existing project folder (the one that contains game/)",
            initialdir=project_var.get() or str(Path.home()),
        )
        if chosen:
            project_var.set(str(Path(chosen).resolve()))

    def new_project() -> None:
        chosen = filedialog.askdirectory(
            title="Select a folder for your NEW project (will be created if empty)",
            initialdir=str(Path.home()),
            mustexist=False,
        )
        if not chosen:
            return
        target = Path(chosen).expanduser().resolve()
        try:
            scaffold_empty_project(target)
        except OSError as exc:
            messagebox.showerror("Could not create project", str(exc))
            return
        project_var.set(str(target))

    ttk.Button(btn_row, text="Browse…", command=browse_project).pack(side="left")
    ttk.Button(btn_row, text="New project…", command=new_project).pack(side="left", padx=(8, 0))

    ttk.Label(proj_box, text="Selected:").pack(anchor="w", padx=8, pady=(8, 0))
    ttk.Label(
        proj_box,
        textvariable=project_var,
        foreground="#333",
        font=("TkFixedFont", 10),
    ).pack(anchor="w", padx=8)
    ttk.Label(proj_box, textvariable=project_status_var, foreground="#888").pack(
        anchor="w", padx=8, pady=(0, 8)
    )

    # ---------- footer ----------
    footer = ttk.Frame(container)
    footer.pack(fill="x", pady=(12, 0))

    ttk.Label(
        footer,
        text=f"Config: {config_path()}",
        foreground="#888",
        font=("TkDefaultFont", 9),
    ).pack(side="left")

    cancel_btn = ttk.Button(footer, text="Cancel", command=root.destroy)
    cancel_btn.pack(side="right")
    launch_btn = ttk.Button(footer, text="Launch RPBuilder")
    launch_btn.pack(side="right", padx=(0, 6))
    launch_btn.state(["disabled"])

    # ---------- live validation + launch ----------
    def refresh_validation(*_args) -> None:
        sdk_ok = validate_sdk(sdk_var.get())
        sdk_status_var.set(
            f"{_bullet(True)} found {sdk_launcher_filename()}"
            if sdk_ok
            else f"{_bullet(False)} pick the folder that contains {sdk_launcher_filename()}"
        )
        proj_ok = validate_project(project_var.get())
        if not project_var.get():
            project_status_var.set("")
        else:
            project_status_var.set(
                f"{_bullet(True)} project ready"
                if proj_ok
                else f"{_bullet(False)} that folder has no game/ subdirectory"
            )
        launch_state["ready"] = sdk_ok and proj_ok
        launch_btn.state(["!disabled"] if launch_state["ready"] else ["disabled"])

    sdk_var.trace_add("write", refresh_validation)
    project_var.trace_add("write", refresh_validation)
    refresh_validation()

    def launch() -> None:
        if not launch_state["ready"]:
            return
        cfg.sdk_path = str(Path(sdk_var.get()).expanduser().resolve())
        cfg.remember_project(project_var.get())
        cfg.save()
        # Detach so closing the launcher doesn't kill the server, then
        # exit the launcher cleanly. We use Popen rather than execvp
        # because Tk's mainloop has already initialized resources we'd
        # rather not inherit.
        cmd = ["renpy-mcp-gui", "--project", project_var.get(), "--sdk", cfg.sdk_path]
        try:
            subprocess.Popen(cmd, start_new_session=True)
        except FileNotFoundError:
            subprocess.Popen(
                [sys.executable, "-m", "renpy_mcp_gui", *cmd[1:]],
                start_new_session=True,
            )
        root.destroy()

    launch_btn.configure(command=launch)
    root.bind("<Return>", lambda e: launch() if launch_state["ready"] else None)
    root.bind("<Escape>", lambda e: root.destroy())

    root.mainloop()
    return 0


# ---------- entry point -------------------------------------------------------


def main() -> int:
    cfg = LauncherConfig.load()

    # Force terminal mode when requested OR when no display is available.
    force_terminal = (
        "--terminal" in sys.argv
        or os.environ.get("RPBUILDER_TERMINAL") == "1"
    )
    if not force_terminal and sys.platform != "win32" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        # Headless Linux box — Tk would crash trying to open a display.
        force_terminal = True

    if force_terminal:
        return run_terminal_launcher(cfg)

    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("Tkinter is not available; falling back to terminal mode.", file=sys.stderr)
        return run_terminal_launcher(cfg)

    try:
        return run_tk_launcher(cfg)
    except Exception as exc:  # noqa: BLE001 — Tk failures shouldn't be fatal
        print(f"Tk launcher crashed: {exc}", file=sys.stderr)
        return run_terminal_launcher(cfg)


if __name__ == "__main__":
    sys.exit(main())
