<div align="center">

<img src="img_samples/banner.svg" alt="Blocksh" width="100%">

<br><br>

[![Python](https://img.shields.io/badge/Python-3.10%2B-89b4fa?style=for-the-badge&logo=python&logoColor=white&labelColor=0d0f1a)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-a6e3a1?style=for-the-badge&logo=qt&logoColor=white&labelColor=0d0f1a)](https://pypi.org/project/PySide6/)
[![pyte](https://img.shields.io/badge/pyte-0.8%2B-94e2d5?style=for-the-badge&labelColor=0d0f1a)](https://pypi.org/project/pyte/)
[![SQLite](https://img.shields.io/badge/SQLite-Persistent%20History-f38ba8?style=for-the-badge&logo=sqlite&logoColor=white&labelColor=0d0f1a)](https://sqlite.org)
[![Platform](https://img.shields.io/badge/Linux-Compatible-a6e3a1?style=for-the-badge&logo=linux&logoColor=white&labelColor=0d0f1a)](https://kernel.org)
[![Theme](https://img.shields.io/badge/Catppuccin-Mocha-cba6f7?style=for-the-badge&labelColor=0d0f1a)](https://catppuccin.com)
[![PTY](https://img.shields.io/badge/PTY-Full%20Support-89dceb?style=for-the-badge&labelColor=0d0f1a)](https://en.wikipedia.org/wiki/Pseudoterminal)
[![Version](https://img.shields.io/badge/version-v0.9.2-fab387?style=for-the-badge&labelColor=0d0f1a)](https://github.com/rhaymisonbetini/Blocksh/releases)

<br>

<p>
  A <strong>Warp-inspired</strong>, block-based terminal emulator with full PTY support,<br>
  SSH manager, command workflows, split panes, and a streaming AI assistant.
</p>

<br>

[![Download AppImage](https://img.shields.io/badge/Download-Blocksh--x86__64.AppImage-89b4fa?style=for-the-badge&logo=linux&logoColor=white&labelColor=0d0f1a)](https://github.com/rhaymisonbetini/Blocksh/releases/latest/download/Blocksh-x86_64.AppImage)

</div>

---

## Install

### One-line install (recommended)

Installs Blocksh, creates the app icon and adds it to your system menu:

```bash
curl -fsSL https://raw.githubusercontent.com/rhaymisonbetini/Blocksh/main/install.sh | bash
```

After running, search **Blocksh** in your app launcher (GNOME Activities, KDE, etc.) — the icon will be there.

### Manual install

```bash
# 1. Download
wget https://github.com/rhaymisonbetini/Blocksh/releases/latest/download/Blocksh-x86_64.AppImage

# 2. Make executable
chmod +x Blocksh-x86_64.AppImage

# 3. Run
./Blocksh-x86_64.AppImage
```

> **No dependencies required.** Python, PySide6, Qt6 and everything else are bundled inside the AppImage.  
> All user data is stored in `~/.blocksh/` — created fresh and clean on first launch.

### Uninstall

```bash
rm ~/.local/bin/Blocksh.AppImage \
   ~/.local/share/icons/hicolor/256x256/apps/blocksh.png \
   ~/.local/share/applications/blocksh.desktop
```

---

## Table of Contents

- [Install](#install)
- [What is Blocksh?](#what-is-blocksh)
- [Screenshots](#screenshots)
- [Features](#features)
- [AI Assistant](#ai-assistant)
- [SSH Manager](#ssh-manager)
- [Command Workflows](#command-workflows)
- [Split Panes](#split-panes)
- [Command Palette](#command-palette)
- [Clickable URLs & Paths](#clickable-urls--paths)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Interactive PTY Mode](#interactive-pty-mode)
- [Settings](#settings)
- [Theming](#theming)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)

---

## What is Blocksh?

**Blocksh** reimagines the terminal by wrapping each executed command in its own isolated **block** — a visual card that captures stdout, stderr, exit codes, timestamps, and working directory context. Inspired by [Warp](https://warp.dev), it combines the familiarity of a traditional shell with a modern, structured UI built natively on Qt6.

Built entirely in Python with **PySide6**, Blocksh runs as a native desktop application on Linux with full **PTY (pseudo-terminal)** support for interactive programs: `vim`, `htop`, `ssh`, and AI agents like `claude`.

Since v0.2.0, Blocksh has shipped many more features across subsequent releases:
- **AI Assistant** (v0.3.0 → v0.9.0) — streaming multi-turn agent with file reading, directory listing, search, and command execution; powered by Ollama, Anthropic, or OpenAI
- **Command Palette** (v0.5.0) — `Ctrl+P` fuzzy search across full command history
- **Clickable URLs & paths** (v0.5.1) — click any URL or file path in output to open it
- **`.env` auto-loading** (v0.5.2) — per-project environment variables loaded automatically on `cd`
- **SSH Manager** (v0.5.3) — save, organize, and one-click connect to SSH servers from the sidebar
- **Command Workflows** (v0.6.0) — reusable command sequences with variable substitution
- **Split Panes** (v0.7.0) — divide any tab into horizontal or vertical panes, each with its own shell

> *"Not just a terminal. A workspace for the command line."*

---

## Screenshots

<div align="center">

<table>
<tr>
<td align="center" width="50%">

**AI Assistant — Clean Chat Interface**

<img src="img_samples/Screenshot%20from%202026-05-13%2014-53-24.png" alt="Blocksh — AI Assistant redesigned panel" width="100%">

*Redesigned floating panel with tool call rows, user bubbles, streaming responses and auto-collapsed sidebar*

</td>
<td align="center" width="50%">

**Navigation Sidebar + Empty State**

<img src="img_samples/Screenshot%20from%202026-05-13%2014-53-32.png" alt="Blocksh — Sidebar and empty state" width="100%">

*All 7 sidebar pages — Terminal · History · Favorites · Projects · SSH · Workflows — with quick-action empty state*

</td>
</tr>
<tr>
<td align="center" width="50%">

**Block-Based Terminal Output**

<img src="img_samples/Screenshot%20from%202026-05-13%2014-53-59.png" alt="Blocksh — Terminal command blocks with ANSI output" width="100%">

*Uniform typography scale — prompt, command and output all at 12–13 px with full ANSI color rendering*

</td>
<td align="center" width="50%">

**Settings + Theme Creator**

<img src="img_samples/Screenshot%20from%202026-05-13%2014-54-05.png" alt="Blocksh — Settings panel with theme creator" width="100%">

*Appearance controls, terminal behavior and live 24-token color picker; sidebar auto-collapses when Settings opens*

</td>
</tr>
</table>

</div>

---

## Features

### Block-Based Output
Every command runs in its own **block** — a self-contained card with:
- Command text and exit status indicator
- Full stdout/stderr with ANSI color rendering
- Timestamp and working directory
- Collapsible / expandable toggle
- Stop button (automatically appears after 10 seconds for long-running commands)

### Multi-Tab Workflow
- Open unlimited terminal sessions with `Ctrl+T`
- Each tab owns an independent `ShellSession` with isolated cwd and environment
- Close tabs with `Ctrl+W`; labeled tabs in the TabBar

### Full PTY Support
Interactive programs are automatically routed to a real **PTY canvas**:
- Covers `vim`, `nano`, `htop`, `ssh`, `claude`, Python REPL, Node.js, and more
- Direct `QPainter`-based cell rendering — no HTML, no Qt layout engine overhead
- Powered by `pyte` for accurate VT100/VT220 terminal emulation
- Exit banner shown on PTY close with full scrollback history captured

### Persistent History
- All commands stored in `~/.blocksh/history.db` (SQLite)
- Browsable in the sidebar History panel
- Per-project command sub-history in the Projects panel
- Configurable retention policy (7 / 30 / 90 days or forever)

### Favorites & Projects
- **Favorites** — pin reusable commands with a name and cwd; edit, rename, and delete via the ⋮ menu
- **Projects** — auto-detected from directory markers:
  - `.git` → Git
  - `package.json` → Node.js
  - `pyproject.toml` → Python
  - `Cargo.toml` → Rust
  - `go.mod` → Go
  - `composer.json` → PHP

### Collapsible Sidebar
The sidebar can be collapsed to a **48px icon-only strip** by clicking the `«` button:
- Smooth 200ms ease animation
- All nav icons remain clickable with tooltips
- Sub-pages auto-expand the sidebar before navigating
- Click `»` to restore full width

### Settings Panel
A full-width settings workspace with five sections:

| Section | What you can configure |
|---------|----------------------|
| **Appearance** | Font family (monospace filter), terminal/output font size, cursor style (block / underline / beam), output text color override, profile photo |
| **Terminal Behavior** | Default shell, scrollback lines, history load limit, auto-scroll, history retention, `.env` file loading policy |
| **AI Assistant** | Enable/disable AI, backend (Ollama / Anthropic / OpenAI), host URL, model name, live status check |
| **Theme Creator** | 24-field color picker with live preview, save/delete user themes |
| **Data Management** | Clear history / favorites / projects / all data, export history to JSON |

### Profile Photo & Avatar
- Set a profile photo in **Settings → Appearance → Profile photo**
- The circular avatar in the top-right TabBar updates instantly
- Clicking the avatar also opens Settings

---

## AI Assistant

The **AI Assistant** is a floating panel that opens over the terminal. It runs a full multi-turn agent loop with access to your filesystem — not just a chatbot.

### How to open

Click the robot icon (`🤖`) in the TabBar, or use the keyboard shortcut (configurable in Settings).

### What it can do

| Capability | Example prompt |
|-----------|---------------|
| **Read files** | "explain app/services/ai_service.py" |
| **List directories** | "what files are in the app/ui folder?" |
| **Search code** | "find all usages of PtyProcess" |
| **Run commands** | "run the tests and show me the output" |
| **Multi-turn conversation** | "now look at the same pattern in pty_widget.py" |

The agent uses **tool calls** to perform each action — you see the tool name and result inline as it works, before the final answer appears.

### Streaming

Responses stream word by word as the model generates them. Tool calls appear immediately when invoked, with their result shown before the model continues reasoning. The input bar is disabled during streaming and re-enabled automatically.

### Backends

Configure in **Settings → AI Assistant**:

| Backend | When to use |
|---------|------------|
| **Ollama (offline)** | Local models — `llama3.2`, `codellama`, etc. No API key required |
| **Anthropic** | Claude models — requires `ANTHROPIC_API_KEY` |
| **OpenAI** | GPT models — requires `OPENAI_API_KEY` |

The status indicator shows green when the backend is reachable.

### Conversation persistence

Each terminal tab has its own `AgentSession`. The message history is preserved across panel open/close within the same session. Click **New** to start a fresh conversation.

---

## SSH Manager

Save SSH server configurations and connect with one click — no more typing `ssh user@host -p 2222 -i ~/.ssh/key` every time.

### Adding a connection

1. Open the **SSH** page in the sidebar
2. Click the `+` button
3. Fill in: name, host, user, port (default 22), optional key path, optional group
4. Click **Save**

### Connecting

Click any saved connection — Blocksh launches a full PTY session with the correct `ssh` command including keepalive options (`ConnectTimeout=30`, `ServerAliveInterval=15`).

### Managing connections

Right-click any connection (or click ⋮) for **Edit** and **Delete** options.

### Grouping

Assign connections to groups (e.g., `production`, `staging`) to visually organize them in the list.

---

## Command Workflows

**Workflows** are named sequences of shell commands that you can save, parameterize, and replay with one click.

### Creating a workflow

1. Open the **Workflows** page in the sidebar
2. Click `+` and give the workflow a name
3. Add one or more command steps — each step can contain `${VARIABLE}` placeholders
4. Optionally configure each step's `on_error` behavior: `stop`, `continue`, or `ask`
5. Save

### Running a workflow

Click any workflow — if it has variables, a dialog prompts you to fill in the values. Then each step runs as its own `CommandBlock` in the active terminal, in order.

### Managing workflows

Click ⋮ on any workflow for **Edit**, **Duplicate**, and **Delete** options.

---

## Split Panes

Divide any terminal tab into multiple independent panels — each with its own shell session, cwd, and command history.

### Splitting

| Shortcut | Action |
|----------|--------|
| `Ctrl+\` | Split current pane **vertically** (side by side) |
| `Ctrl+-` | Split current pane **horizontally** (top / bottom) |

### Navigating

- Click any pane to make it active (highlighted border)
- `Ctrl+←` / `Ctrl+→` — move focus between panes

### Closing

- `Ctrl+Shift+W` — close the active pane
- Click the `✕` button in the pane header

Panes resize freely by dragging the splitter handle. When only one pane remains, the header disappears automatically.

---

## Command Palette

Press `Ctrl+P` to open the **Command Palette** — a fuzzy-search overlay over the entire window that lets you find and re-run any past command instantly.

- Searches the full SQLite command history in real time as you type
- Results ranked by recency and frequency; boosted if cwd matches current directory
- `Enter` — insert the selected command into the active input bar
- `Ctrl+Enter` — insert and execute immediately
- Results show command text, working directory, timestamp, and exit status

---

## Clickable URLs & Paths

Command block output is scanned for URLs and file paths. Detected items are **underlined** and the cursor changes to a pointer on hover.

| Pattern | Action on click |
|---------|----------------|
| `https://...` / `http://...` | Opens in default browser |
| `http://localhost:PORT` | Opens in browser (highlighted distinctly) |
| `/absolute/path/to/file.py` | Opens in `$EDITOR` / `xdg-open` |
| `File "path.py", line N` (Python tracebacks) | Opens file at the exact line |

No configuration required — detection is always on.

---

## `.env` Auto-loading

When you `cd` into a directory that contains a `.env`, `.env.local`, or `.env.development` file, Blocksh can automatically load those variables into the current tab's shell environment.

Configure the behavior in **Settings → Terminal Behavior → .env file loading**:

| Option | Behaviour |
|--------|-----------|
| **Ask each time** | A prompt appears once per project |
| **Always load** | Variables loaded silently on every `cd` |
| **Never load** | Feature disabled |

The decision is stored per-project path in SQLite — "Ask" only fires once per project, not on every navigation.

---

## Architecture

### Layer Overview

```
┌────────────────────────────────────────────────────────────────┐
│                          app/ui/                               │
│   MainWindow · Sidebar · TabBar · TerminalPanel(s)             │
│   SplitPaneContainer · PtyWidget · AiPanel · ThemeManager      │
│   SettingsPanel · ANSI renderers                               │
├────────────────────────────────────────────────────────────────┤
│                       app/services/                            │
│   HistoryService · FavoritesService · ProjectService           │
│   SshService · WorkflowService · AiService (AgentSession)      │
│   SettingsService (singleton, emits settings_changed)          │
├────────────────────────────────────────────────────────────────┤
│                        app/core/                               │
│   ShellSession · BaseExecutor · CommandThread · PtyProcess     │
├────────────────────────────────────────────────────────────────┤
│                        app/infra/                              │
│   SQLite repositories · settings.py (paths) · DB_PATH         │
│   SettingsRepository · SshRepository · WorkflowRepository      │
├────────────────────────────────────────────────────────────────┤
│                       app/domain/                              │
│   Command · Block · Favorite · Project · AppSettings           │
│   SshConnection · Workflow · WorkflowStep                      │
└────────────────────────────────────────────────────────────────┘
```

### UI Component Hierarchy

```
MainWindow
├── Sidebar                    (collapsible: 180px expanded / 48px icons-only)
│   ├── page 0: nav buttons    (Terminal · History · Favorites · Projects · SSH · Workflows · ⚙ Settings · Themes)
│   ├── page 1: history list
│   ├── page 2: themes list
│   ├── page 3: favorites list
│   ├── page 4: projects list  (collapsible, with command sub-history)
│   ├── page 5: SSH list       (saved connections + one-click connect)
│   └── page 6: workflows list (saved command sequences)
├── TabBar                     (+ tab · tab labels · ⌕ search · ⊟ collapse-all · ⚙ settings · avatar)
└── QStackedWidget (_right_stack)
    ├── page 0: terminal view
    │   └── SplitPaneContainer  (one per tab — manages 1…N panes in a QSplitter tree)
    │       └── _PaneWrapper(s) (header + close button per pane when >1 pane)
    │           └── TerminalPanel  (owns ShellSession + HistoryService)
    │               ├── SearchBar       (hidden, Ctrl+F)
    │               ├── QScrollArea → blocks_container
    │               │   └── CommandBlock(s)
    │               ├── separator QFrame
    │               ├── InputBar        (QPlainTextEdit + Run button)
    │               ├── CompletionPopup (floating Tab-completion overlay)
    │               └── PtyWidget       (floating PTY overlay, raised over layout)
    ├── page 1: settings view
    │   └── SettingsPanel
    │       ├── AppearanceSection
    │       ├── TerminalSection (+ .env policy)
    │       ├── AiSection       (backend · host · model · status)
    │       ├── ThemeCreatorSection
    │       └── DataManagementSection
    └── AiPanel                 (floating overlay, independent of tab layout)
        ├── conversation view   (streaming message list)
        └── input bar           (disabled during streaming)
```

### AI Agent Loop

```
AiPanel — user sends message
    └─ AgentWorker (QThread)
         └─ AgentSession.send(text)   ← AsyncGenerator
              ├─ backend.stream(messages, system, tools)
              │    ├─ text_delta      → AiPanel appends streaming text
              │    └─ tool_call       → AiPanel shows tool call row
              ├─ tool_executor.run(tool_call)
              │    ├─ read_file       → returns file content with line numbers
              │    ├─ list_dir        → returns directory listing
              │    ├─ search_files    → grep/rg across codebase
              │    ├─ run_command     → subprocess with timeout
              │    └─ ask_user        → pauses loop, waits for UI response
              └─ tool_result appended as user message → loop continues
```

### PTY Rendering Pipeline

```
PtyProcess (QThread)
    └─ data_ready(bytes) signal
         └─ PtyWidget._on_data()
              └─ pyte.ByteStream.feed()
                   └─ QTimer.singleShot(33 ms, _render)
                        └─ _PtyCanvas.update()
                             └─ _PtyCanvas.paintEvent(QPainter)
                                  cell-by-cell: col × char_w, row × char_h
```

> `_PtyCanvas` uses `WA_OpaquePaintEvent` and direct cell rendering. On PTY exit, the full scrollback history (`screen.history.top`) is captured alongside the visible screen and emitted via `session_finished`.

### Settings Data Flow

```
SettingsPanel control change
    └─ SettingsService.update(**kwargs)
         ├─ dataclasses.replace(current, **kwargs)
         ├─ SettingsRepository.save()  →  ~/.blocksh/settings.json
         └─ settings_changed(AppSettings) signal
              ├─ PtyWidget._on_settings_changed()   (font · cursor · shell · scrollback)
              ├─ CommandBlock._build_output()        (output font · fg color override)
              └─ TabBar._refresh_avatar()            (circular avatar display)
```

### ANSI Rendering — Two Paths

| Context | Implementation | Mechanism |
|---------|---------------|-----------|
| `CommandBlock` (non-interactive) | `app/ui/ansi_renderer.py` | `render_ansi()` → `(text, QTextCharFormat)` segments inserted into `QTextEdit` cursor |
| PTY canvas | `app/ui/ansi_colors.py` + `pyte` screen buffer | Color attributes from pyte cell, resolved via `_resolve_color()` / `_256_to_hex()` |

### Data Storage

```
~/.blocksh/
├── history.db           ← SQLite: sessions · blocks · favorites · projects · ssh_connections · workflows
├── settings.json        ← AppSettings (font, cursor, shell, avatar_path, ai_backend, …)
├── theme_pref.json      ← Active theme name (persisted across restarts)
└── themes/
    └── *.json           ← User-defined theme files (all Palette fields required)
```

---

## Getting Started

### Prerequisites

| Requirement | Minimum Version | Notes |
|-------------|----------------|-------|
| Python      | 3.10           | Required for `match` statements and `dataclasses` features |
| pip         | any            | For installing dependencies |
| Linux       | any modern     | PTY requires Unix `/dev/pts`; macOS untested |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/rhaymisonbetini/Blocksh.git
cd Blocksh

# 2. Create an isolated virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch
python run.py
```

No build step. No compiled assets. No database migrations — `~/.blocksh/` and all required files are created automatically on first launch.

### Dependencies

| Package | Version | Role |
|---------|---------|------|
| `PySide6` | ≥ 6.6.0 | Qt6 bindings — entire UI layer, signals, QThread |
| `pyte`    | ≥ 0.8.0 | VT100/VT220 screen emulation for PTY mode |
| `anthropic` | ≥ 0.25 | Anthropic Claude API (optional — AI Assistant) |

> Ollama and OpenAI backends use only the standard library (`urllib`) — no extra packages required.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+T` | Open new terminal tab |
| `Ctrl+W` | Close current tab |
| `Ctrl+F` | Toggle search bar |
| `Ctrl+L` | Clear all command blocks |
| `Ctrl+\` | Split active pane vertically |
| `Ctrl+-` | Split active pane horizontally |
| `Ctrl+Shift+W` | Close active split pane |
| `Ctrl+←` / `Ctrl+→` | Navigate between split panes |
| `Escape` | Close Settings panel (if open) |
| `Tab`    | Trigger path / file completion |
| `↑` / `↓` | Navigate command history in the input bar |
| `Enter`  | Execute command |

---

## Interactive PTY Mode

Blocksh automatically detects when a command requires a real pseudo-terminal and launches `PtyWidget` instead of a `CommandBlock`.

**Always PTY-routed** (`_ALWAYS_INTERACTIVE` in `terminal_panel.py`):

```
nano   vim    nvim   vi     emacs   helix
htop   top    btop   less   more    man
ssh    sftp   ftp    mysql  psql    redis-cli  sqlite3
claude  ...
```

**PTY on bare call** (no arguments — REPL detection via `_INTERACTIVE_NO_ARGS`):

```
python  python3  ipython
node    irb      php
bash    sh       zsh    fish
```

**Shell alias detection:** a short `bash -i` subprocess resolves shell aliases that map to PTY commands before routing.

The `PtyWidget` overlays the entire `TerminalPanel` via `setGeometry(self.rect()) + raise_()` — not inserted into the Qt layout. `resizeEvent` on `TerminalPanel` keeps the overlay geometry in sync.

---

## Settings

The Settings panel is opened via the `⚙` button or avatar in the TabBar, or the **Settings** entry in the sidebar. It replaces the terminal area while open; press `← Back`, click **Terminal** in the sidebar, or press `Escape` to return.

All settings are persisted immediately to `~/.blocksh/settings.json` on every change and broadcast via `SettingsService.settings_changed` so widgets update live without restart.

### AppSettings Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `font_family` | `str` | `"Monospace"` | Terminal font family (monospace fonts only) |
| `font_size_terminal` | `int` | `10` | PTY canvas font size (pt) |
| `font_size_output` | `int` | `11` | CommandBlock output font size (pt) |
| `cursor_style` | `str` | `"block"` | `"block"` · `"underline"` · `"beam"` |
| `output_fg_override` | `str` | `""` | Hex color for CommandBlock text; empty = use theme `fg` |
| `default_shell` | `str` | `"bash"` | Shell used for PTY sessions (sourced from `/etc/shells`) |
| `scrollback_lines` | `int` | `2000` | `pyte.HistoryScreen` history depth |
| `history_limit` | `int` | `200` | Max blocks loaded in the History sidebar panel |
| `auto_scroll` | `bool` | `True` | Scroll to latest output on new command |
| `history_retention_days` | `int` | `0` | Days to keep history (0 = forever) |
| `avatar_path` | `str` | `""` | Absolute path to profile photo (PNG/JPG/WebP) |
| `ai_enabled` | `bool` | `True` | Enable or disable the AI Assistant |
| `ai_backend` | `str` | `"ollama"` | `"ollama"` · `"anthropic"` · `"openai"` |
| `ai_host` | `str` | `"http://localhost:11434"` | Base URL for Ollama |
| `ai_model` | `str` | `"llama3.2"` | Model name for the selected backend |
| `ai_api_key` | `str` | `""` | API key for Anthropic / OpenAI backends |

> Shell and scrollback changes take effect on new terminal tabs; existing tabs are not affected.

### Theme Creator

The **Theme Creator** section in Settings lets you build a fully custom theme:

1. All 24 color fields are displayed as clickable swatches grouped by role (Backgrounds, Foreground, Semantic, PTY canvas, Borders)
2. Click any swatch to open the system color picker
3. Enter a name and click **Save theme** — saved to `~/.blocksh/themes/<name>.json`, immediately available in the Themes sidebar
4. Existing user themes listed below with **Delete** button (built-in themes cannot be deleted)

---

## Theming

Blocksh uses a **`Palette` dataclass** as the single source of truth for all colors. The `ThemeManager` singleton emits `theme_changed(Palette)` and every widget subscribes via `apply_theme(p: Palette)`.

### Built-in Themes

| Theme | Base Palette |
|-------|-------------|
| `dark`  | [Catppuccin Mocha](https://catppuccin.com) |
| `light` | [Catppuccin Latte](https://catppuccin.com) |

### Color Reference — Dark Theme

| Token | Hex | Role |
|-------|-----|------|
| `bg` | `#0d0f1a` | Main window background |
| `bg_panel` | `#12141f` | Sidebar and tab bar background |
| `bg_surface` | `#161926` | Cards, command blocks |
| `bg_overlay` | `#1e2235` | Hover / active overlays |
| `fg` | `#cdd6f4` | Primary text |
| `fg_muted` | `#6c7086` | Secondary text, timestamps |
| `fg_dim` | `#45475a` | Dimmed / disabled text |
| `blue` | `#89b4fa` | Accents, active states, links |
| `green` | `#a6e3a1` | Success indicators (exit 0) |
| `red` | `#f38ba8` | Error text |
| `red_ui` | `#e64553` | Danger buttons, destructive actions |
| `cyan` | `#94e2d5` | PTY cursor, highlights |
| `border` | `#313244` | Panel / card borders |
| `pty_bg` | `#0d0f1a` | PTY canvas background |
| `pty_fg` | `#cdd6f4` | PTY canvas default foreground |
| `pty_cursor_bg` | `#cdd6f4` | PTY cursor fill |
| `pty_cursor_fg` | `#0d0f1a` | PTY cursor text |

### Custom Themes

The easiest way is the in-app **Theme Creator** (Settings → Theme Creator). Alternatively, drop a `.json` file into `~/.blocksh/themes/` containing every `Palette` field:

```json
{
  "name": "my-theme",
  "bg": "#1a1a2e",
  "bg_panel": "#16213e",
  "bg_surface": "#0f3460",
  "bg_overlay": "#1a1a40",
  "bg_hover": "#162040",
  "bg_hover2": "#1e2850",
  "bg_active": "#0f3460",
  "bg_selected": "#1a3a70",
  "bg_highlight": "#1a2850",
  "fg": "#e0e0e0",
  "fg_muted": "#888888",
  "fg_dim": "#555555",
  "blue": "#4fc3f7",
  "green": "#81c784",
  "red": "#e57373",
  "red_ui": "#e53935",
  "cyan": "#4dd0e1",
  "border": "#2a2a5a",
  "pty_bg": "#1a1a2e",
  "pty_fg": "#e0e0e0",
  "pty_cursor_bg": "#e0e0e0",
  "pty_cursor_fg": "#1a1a2e"
}
```

Activate via **Themes** in the sidebar — no restart required.

---

## Project Structure

```
.
├── run.py                        ← Entry point: python run.py
├── requirements.txt              ← PySide6, pyte, anthropic
└── app/
    ├── main.py                   ← Bootstrap: DI wiring, QApplication launch
    ├── domain/                   ← Pure data models (zero external dependencies)
    │   ├── command.py
    │   ├── block.py
    │   ├── favorite.py
    │   ├── project.py
    │   ├── settings.py           ← AppSettings (font, cursor, shell, ai_backend, …)
    │   ├── ssh_connection.py     ← SshConnection(name, host, user, port, key_path, group)
    │   └── workflow.py           ← Workflow + WorkflowStep(command_template, on_error)
    ├── core/
    │   ├── shell_session.py
    │   ├── command_executor.py
    │   └── pty_process.py
    ├── services/
    │   ├── history_service.py
    │   ├── favorites_service.py
    │   ├── project_service.py
    │   ├── settings_service.py
    │   ├── ssh_service.py        ← CRUD + to_command() builder
    │   ├── workflow_service.py   ← CRUD + execute(workflow, variables)
    │   └── ai_service.py        ← AgentSession · AgentWorker · backends (Ollama/Anthropic/OpenAI)
    ├── infra/
    │   ├── config/
    │   │   └── settings.py       ← APP_DIR · DB_PATH · THEMES_DIR · SETTINGS_PATH
    │   └── storage/
    │       ├── database.py
    │       ├── history_repository.py
    │       ├── favorites_repository.py
    │       ├── project_repository.py
    │       ├── settings_repository.py
    │       ├── ssh_repository.py
    │       └── workflow_repository.py
    └── ui/
        ├── main_window.py
        ├── sidebar.py            ← 7 pages: nav · history · themes · favorites · projects · SSH · workflows
        ├── tab_bar.py
        ├── terminal_panel.py
        ├── split_pane_container.py  ← QSplitter tree + _PaneWrapper per pane
        ├── command_block.py
        ├── pty_widget.py
        ├── ai_panel.py           ← Floating AI conversation overlay
        ├── input_bar.py
        ├── search_bar.py
        ├── completion_popup.py
        ├── settings_panel.py
        ├── theme.py
        ├── ansi_renderer.py
        └── ansi_colors.py
```

---

## Roadmap

| Version | Focus | Status |
|---------|-------|--------|
| v0.0.x  | PTY core — arrow keys, Ctrl mapping, alternate screen, bracketed paste, streaming output | ✅ Done |
| v0.1.x  | Input & shell — readline shortcuts, history dedup, PATH completion, performance, polish | ✅ Done |
| v0.2.0  | Settings panel, Theme Creator, AppSettings, collapsible sidebar, profile avatar | ✅ Done |
| v0.3.0  | AI agent with filesystem access, ASK tool, interactive PTY banner | ✅ Done |
| v0.4.0  | Native tool-calling agent — proper multi-turn message history, Anthropic/OpenAI/Ollama | ✅ Done |
| v0.5.0  | Command Palette (`Ctrl+P`) — fuzzy search over full history | ✅ Done |
| v0.5.1  | Clickable URLs and file paths in command block output | ✅ Done |
| v0.5.2  | `.env` auto-loading — per-project environment variables on `cd` | ✅ Done |
| v0.5.3  | SSH Connection Manager — saved connections, one-click connect | ✅ Done |
| v0.6.0  | Command Workflows — named sequences with `${VAR}` substitution | ✅ Done |
| v0.7.x  | Split Panes — horizontal/vertical splits, active tracking, splitter collapse | ✅ Done |
| v0.8.x  | CRUD visibility — ⋮ buttons always visible; PTY overlay fix; font size fix; sidebar scroll fix | ✅ Done |
| v0.9.0  | AI Agent rewrite — streaming `AgentSession`, floating `AiPanel`, multi-turn context | ✅ Done |
| v0.9.1  | Typography scale — Ubuntu Mono, px-based tokens, visual polish across all panels | ✅ Done |
| v0.9.2  | AI panel redesign — clean chat UI, tool call cards, sidebar auto-collapse on AI/Settings | ✅ Done |

---

<div align="center">

<br>

[![Made with Python](https://img.shields.io/badge/Made%20with-Python-89b4fa?style=flat-square&logo=python&logoColor=white&labelColor=0d0f1a)](https://python.org)
[![Powered by Qt6](https://img.shields.io/badge/Powered%20by-Qt6-a6e3a1?style=flat-square&logo=qt&logoColor=white&labelColor=0d0f1a)](https://qt.io)
[![Catppuccin](https://img.shields.io/badge/Theme-Catppuccin-cba6f7?style=flat-square&labelColor=0d0f1a)](https://catppuccin.com)

<br>

<sub>Built with precision. Designed for the terminal.<br>
<em>Blocksh — because every great command deserves its own stage.</em></sub>

<br><br>

</div>
