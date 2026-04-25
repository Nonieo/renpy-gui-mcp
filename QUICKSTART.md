# Quick Start

You want to make a visual novel and you've heard "AI" or "MCP" somewhere
but it's all a fog. This page walks you from a blank computer to "I'm
playing my own VN" in about 15 minutes.

If you already know what an MCP server is and just want install
instructions, [README.md](README.md) is shorter.

---

## What this thing actually is

Three pieces, all working together:

1. **[Ren'Py](https://www.renpy.org)** — the actual game engine. You
   download it like any other program. It runs your finished visual
   novel in a window.
2. **renpy-mcp** — a small program that *speaks to other programs* on
   your behalf. It edits Ren'Py's text-based source files for you,
   correctly, so you don't have to learn the syntax.
3. **The RPBuilder GUI** — a browser-based editor that uses renpy-mcp
   under the hood. You see a Story Map, click nodes, type dialogue.
   No code visible.

You only ever interact with the GUI (or with an AI assistant — more on
that below). The GUI talks to renpy-mcp; renpy-mcp talks to Ren'Py.

---

## What you need before starting

Three downloads. Total disk space: about 1 GB.

| Tool | What it is | Where |
|---|---|---|
| **Ren'Py SDK** | The game engine + project template. | <https://www.renpy.org/latest.html> — pick the SDK for your operating system. |
| **Python 3.10+** | Programming language. renpy-mcp is written in it. | <https://www.python.org/downloads/> — installer for your OS. |
| **Node.js 18+** | Needed to build the GUI's frontend (a one-time step). | <https://nodejs.org/> — pick the LTS version. |

You don't need to learn any of these. You just need them installed.

If you're on macOS or Linux, you might already have Python 3 and Node
— check by running `python3 --version` and `node --version` in a
terminal. If both print numbers, skip the installs.

---

## Path A: Just the editor (no AI)

This gets you a working visual novel editor running in your browser.
You'll be able to make a small VN by clicking and typing.

### Step 1 — Get renpy-mcp

```bash
git clone https://github.com/fracturedring/renpy-mcp.git
cd renpy-mcp
```

If you don't have `git`, download the [zip from
GitHub](https://github.com/fracturedring/renpy-mcp/archive/refs/heads/main.zip),
unzip it, and `cd` into the unzipped folder.

### Step 2 — Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .\.venv\Scripts\activate          # Windows PowerShell
pip install -e ".[gui]"
```

The `.venv` is an isolated Python environment — like a workspace just
for this project. `pip install -e ".[gui]"` pulls in everything
renpy-mcp needs, plus the GUI server.

### Step 3 — Run the launcher

```bash
gui/launch.sh
```

That script:

1. Creates the Python virtualenv if it's missing.
2. Installs `renpy-mcp[gui]` if it's missing.
3. Builds the editor's frontend if it's missing (one-time, needs `npm`).
4. Opens **the launcher window**, which asks you for the Ren'Py SDK
   folder and the project folder. Both choices are remembered for next
   time, so subsequent launches are one click.

If you'd rather skip the wrapper, after `pip install -e ".[gui]"` you
can also run `rpbuilder` directly from the activated venv — the
launcher window is the same.

#### What the launcher looks like

| | |
|---|---|
| **Ren'Py SDK** | Browse to the folder named something like `renpy-8.4.2-sdk` (it contains a `renpy.sh` or `renpy.exe`). The launcher validates and shows a green check when it finds one. |
| **Project** | Pick from your recent projects, browse to an existing one, or click *New project* to create an empty one. The launcher creates the bare `game/script.rpy` so the editor has something to bind to; you'll fill it in from the editor. |
| **Launch RPBuilder** | Spawns the editor server, opens it in your browser at <http://127.0.0.1:8765>, and dismisses the launcher. Closing the editor window stops the server. |

Where the launcher remembers your choices:

- Linux/macOS: `~/.config/renpy-mcp/launcher.json`
- Windows: `%APPDATA%\renpy-mcp\launcher.json`

Plain JSON — edit it by hand if you ever need to.

#### Headless or no GUI toolkit?

Run with `--terminal` (or `RPBUILDER_TERMINAL=1`) for a text-prompt
version of the same flow. The launcher also auto-falls-back to text
mode when no display is available.

### Step 4 — Make something

You'll see the RPBuilder editor. The left rail has Story Map, Choice
View, Characters, Assets, and a few others. Click around; everything
updates in real time. The header has a **Preview** button — when you
click it, Ren'Py will open in a separate window playing your VN.

Try this in order:

1. **Characters** → add a character (give them a name and a color).
2. **Story Map** → click "+ Scene" in the toolbar to make your first
   scene label. Click on the new node to open it in the right-side
   Inspector.
3. **Inspector** → type some dialogue using the "Add a dialogue line"
   form. Pick the character you just made.
4. **Story Map** → click "+ Choice" to make a choice node. Drag a port
   (the small "+" on the right edge of a node) from the choice node
   to a target scene to wire up a branch.
5. **Header** → hit Preview. Ren'Py opens. Play through your scene.

That's the loop. Keep adding scenes, characters, and branches. The
**Composers** panel has visual editors for screens, stages (multiple
sprites at once), and image-map menus when you want them.

### Stuck?

- The browser shows nothing? Make sure `gui/run.sh` is still running
  in your terminal. Closing the terminal closes the editor.
- "Preview" button does nothing? Check the terminal where `gui/run.sh`
  is running for errors. Usually the SDK path is wrong.
- The lint button under **Build** shows red errors? Click on each
  error — it'll tell you what's wrong. Usually it's a typo in a label
  name.

---

## Path B: Editor + AI assistant

Same setup as Path A, **plus** you point an AI assistant at the same
project. The AI does the typing; you supervise.

The AI assistant needs to be one that speaks **MCP** (Model Context
Protocol). Currently working ones:

- [Claude Code](https://docs.claude.com/claude-code) — Anthropic's
  CLI, works on macOS / Linux / Windows.
- [Cursor](https://cursor.sh) — code editor with a built-in AI
  panel that supports MCP.
- [hermes-agent](https://github.com/anthropics/hermes-agent) — a
  CLI orchestrator.

### Step 1 — Set up Path A first

Get the GUI running through Path A above. Don't close that terminal.

### Step 2 — Tell the AI assistant about renpy-mcp

For Claude Code, in the project directory create a file called
`.mcp.json` with this content:

```json
{
  "mcpServers": {
    "renpy": {
      "type": "stdio",
      "command": "/path/to/renpy-mcp/.venv/bin/python",
      "args": [
        "-m", "renpy_mcp",
        "--project", "/path/to/your/project",
        "--sdk", "/path/to/your/renpy-sdk"
      ]
    }
  }
}
```

Replace the three paths with real ones. Claude Code will detect this
file when it starts and your AI session will have access to all 72
renpy-mcp tools (named `mcp__renpy__add_say`, `mcp__renpy__create_scene`,
and so on).

### Step 3 — Talk to the AI

Open Claude Code in the same directory and tell it what you want. Try:

> "Make a short visual novel about a lighthouse keeper meeting a selkie.
> Three scenes, one choice that branches into two endings."

Watch the GUI in your browser. You'll see scenes appear on the Story
Map as the AI creates them. The file watcher updates the editor
without needing a refresh.

When the AI finishes, click **Preview** in the GUI. The VN runs.

### What the AI is reading

Two things tell the AI how to do this well:

- [AGENTS.md](AGENTS.md) — the playbook. AI assistants read this on
  startup so they know the right tool order.
- [MEDIA.md](MEDIA.md) — what makes a media file Ren'Py-compatible
  (formats, naming, dimensions, style direction). The AI consults
  this before generating images or audio.

You don't have to read those — but if the AI does something weird,
peek at AGENTS.md to see what it was supposed to do.

---

## Path C: Pure AI, no GUI

Same as Path B but skip step 1. The AI does everything in the
terminal. You only see the finished game when you tell it to launch
the preview.

Best for "I want a VN to exist and I don't care to watch it being
made." Slowest part is the AI's own thinking; the actual editing is
instant.

---

## Where to keep things

renpy-mcp expects this directory layout:

```
~/where-you-keep-projects/
├── games/
│   ├── lighthouse_keeper/      # one Ren'Py project per folder
│   │   └── game/
│   │       ├── script.rpy      # Ren'Py source — do NOT edit by hand
│   │       ├── images/         # PNG/JPG backgrounds + sprites
│   │       └── audio/          # OGG music + SFX
│   └── another_project/
└── renpy-sdk/                  # the engine, downloaded earlier
```

The `games/` folder is the convention. Each subfolder is one VN. The
GUI and AI both create new ones via the **`new_project`** action.

---

## Going further

- Want to make your own art? **[MEDIA.md](MEDIA.md)** covers the four
  invariants (format / dimensions / filename / directory) plus
  VN-shaped style direction. Provider-agnostic — works whether you're
  using fal-ai, Stable Diffusion, hand-painting, or commissioning.
- Want to understand what the AI is doing under the hood? Pop open
  **[AGENTS.md](AGENTS.md)** for the tool playbook and
  **[DESIGN.md](DESIGN.md)** for the architecture.
- Want to peek at the production status? **[ROADMAP.md](ROADMAP.md)**
  shows everything that's shipped (Phases 0–8) and the one tabled
  feature (Monaco editor) waiting on demand.

---

## Common first-week questions

**"What's an MCP?"**
Model Context Protocol — a standard way for AI assistants to talk to
external programs. Anthropic introduced it in late 2024. Think of it
as "USB for AI tools." renpy-mcp is one of those external programs;
it speaks the standard so any MCP-aware AI can use it.

**"Do I need to know Python?"**
No. The GUI requires zero code. Even Path B / Path C, you only type
English at the AI.

**"Do I need an internet connection?"**
For the GUI, no. For an AI assistant, yes — most run in the cloud
(Claude, GPT). Local AI models can also speak MCP but quality varies.

**"Can I make money from a VN built with this?"**
Yes — Ren'Py is BSD-licensed (commercially permissive). renpy-mcp is
AGPL-3.0; the games you produce with it are yours to license however
you like. The AGPL only matters if you fork or run renpy-mcp itself
as a hosted service.

**"What if I don't like a scene the AI made?"**
Edit it in the GUI. Or tell the AI to redo it. Or ask the AI to
delete that label and start over. None of the changes are permanent
until you decide to commit them somewhere.
