import os
import shlex
import shutil
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame,
)
from PySide6.QtCore import Signal, QPoint, Qt
from PySide6.QtGui import QShortcut, QKeySequence

from .ai_permission_banner import AiPermissionBanner
from .command_block import CommandBlock
from .completion_popup import CompletionPopup
from .input_bar import InputBar
from .pty_widget import PtyWidget
from .search_bar import SearchBar
from .theme import Palette, ThemeManager
from ..core.command_executor import BaseExecutor, CommandThread
from ..core.shell_session import ShellSession
from ..domain.command import Command
from ..domain.block import Block
from ..services.history_service import HistoryService
from ..infra.storage.history_repository import HistoryRepository

# Commands that always need a PTY regardless of arguments
_ALWAYS_INTERACTIVE = frozenset({
    "nano", "vi", "vim", "nvim", "emacs", "pico", "micro", "hx",
    "less", "more", "man",
    "htop", "top", "btop", "bpytop", "glances",
    "ssh", "tmux", "screen",
    "lazygit", "tig", "gitui",
    "claude", "codex", "aider",
    "mysql", "psql", "mongosh", "redis-cli",
    "sudo",
})

# Commands that are interactive only when called with no arguments
_INTERACTIVE_NO_ARGS = frozenset({
    "bash", "sh", "zsh", "fish", "dash",
    "python", "python3", "ipython", "bpython",
    "node", "deno",
    "irb", "pry",
    "sqlite3",
})


class TerminalPanel(QWidget):
    """
    Self-contained terminal tab: owns ShellSession, HistoryService,
    the blocks scroll area, SearchBar, InputBar and CompletionPopup.
    """

    cwd_changed        = Signal(str)          # emits cwd_display after every command
    favorite_requested = Signal(str, str, str)  # name, command_text, cwd
    env_file_detected  = Signal(str, str)     # (cwd, env_file_path)
    focused            = Signal()             # emitted when any child area is clicked

    def __init__(self, executor: BaseExecutor, repository: HistoryRepository, parent=None):
        super().__init__(parent)
        self._executor  = executor
        self._session   = ShellSession()
        self._history   = HistoryService(repository)

        self._match_blocks:    list[CommandBlock] = []
        self._match_index:     int = 0
        self._pty_widget:      PtyWidget | None = None
        self._active_cmd:      Command   | None = None
        self._running_thread:  CommandThread | None = None
        self._ai_workers:      list = []
        self._agent_worker     = None   # current AgentWorker (if running)

        self._build_ui()
        self._wire_completion()
        self._scroll.installEventFilter(self)
        self._blocks_container.installEventFilter(self)

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def cwd_display(self) -> str:
        return self._session.cwd_display()

    def focus_input(self) -> None:
        self._input_bar.focus()

    def set_input_text(self, text: str) -> None:
        self._input_bar.set_text(text)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.focused.emit()

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.MouseButtonPress, QEvent.FocusIn):
            self.focused.emit()
        return False

    def toggle_search(self) -> None:
        visible = not self._search_bar.isVisible()
        self._search_bar.setVisible(visible)
        if visible:
            self._search_bar.focus()
        else:
            self._clear_highlights()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        layout = self._layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._search_bar = SearchBar()
        self._search_bar.setVisible(False)
        self._search_bar.search_changed.connect(self._on_search)
        self._search_bar.navigate_next.connect(self._search_next)
        self._search_bar.navigate_prev.connect(self._search_prev)
        self._search_bar.closed.connect(self._close_search)
        layout.addWidget(self._search_bar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._blocks_container = QWidget()
        self._blocks_container.setStyleSheet("QWidget { background: transparent; }")
        self._blocks_layout = QVBoxLayout(self._blocks_container)
        self._blocks_layout.setContentsMargins(16, 8, 16, 8)
        self._blocks_layout.setSpacing(6)
        self._blocks_layout.addStretch()

        self._scroll.setWidget(self._blocks_container)
        self._scroll.verticalScrollBar().rangeChanged.connect(
            lambda _min, maximum: self._scroll.verticalScrollBar().setValue(maximum)
        )
        layout.addWidget(self._scroll)

        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._sep)

        self._permission_banner = AiPermissionBanner()
        layout.addWidget(self._permission_banner)

        self._input_bar = InputBar()
        self._input_bar.command_submitted.connect(self._on_command)
        layout.addWidget(self._input_bar)

        # Popup is a child of this panel — overlaps siblings, no top-level issues
        self._completion_popup = CompletionPopup(self)
        self._completion_popup.item_activated.connect(self._on_completion_activated)

        # Global Ctrl+C shortcut — kills the running thread regardless of which child has focus.
        # Enabled only during execution so normal Ctrl+C (clear input) still works when idle.
        self._ctrl_c_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self._ctrl_c_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._ctrl_c_shortcut.activated.connect(self._on_ctrl_c)
        self._ctrl_c_shortcut.setEnabled(False)

    def _wire_completion(self):
        self._input_bar.tab_pressed.connect(self._on_tab_pressed)
        self._input_bar.esc_pressed.connect(self._close_completion)
        self._input_bar.completion_up.connect(self._completion_popup.select_prev)
        self._input_bar.completion_down.connect(self._completion_popup.select_next)
        self._input_bar.completion_accepted.connect(self._accept_completion)
        self._input_bar.text_changed.connect(self._on_input_text_changed)
        self._input_bar.ctrl_c_pressed.connect(self._on_ctrl_c)

    # ── command handling ──────────────────────────────────────────────────────

    def _on_command(self, text: str) -> None:
        self._close_completion()

        if text.strip() == "clear":
            self.clear_blocks()
            return

        if text.startswith("> "):
            self._agent_chat(text[2:].strip())
            return

        command = Command(text=text)

        if self._session.try_cd(text):
            command.status = "done"
            block = Block(command=command, stdout="", stderr="", exit_code=0, cwd=self._session.cwd)
            self._history.add(block)
            self._add_block(block)
            self._input_bar.update_history(self._history.commands())
            self.cwd_changed.emit(self._session.cwd_display())
            self._check_env_files()
        elif self._is_interactive(text):
            self._start_pty_session(text, command)
        else:
            initial_block = Block(
                command=command, stdout="", stderr="", exit_code=-1, cwd=self._session.cwd
            )
            block_widget = CommandBlock(initial_block)
            block_widget.remove_requested.connect(self._remove_block)
            block_widget.favorite_requested.connect(self.favorite_requested)
            block_widget.fix_requested.connect(self._on_fix_requested)
            self._blocks_layout.insertWidget(self._blocks_layout.count() - 1, block_widget)

            thread = CommandThread(command, self._session.cwd, self._session.env)
            self._running_thread = thread
            thread.output_received.connect(block_widget.append_output)
            thread.finished.connect(lambda b, w=block_widget: self._on_command_finished(b, w))

            self._input_bar.set_running(True)
            self._ctrl_c_shortcut.setEnabled(True)
            thread.start()

    # ── interactive / PTY session ─────────────────────────────────────────────

    def _is_interactive(self, text: str) -> bool:
        parts = text.strip().split()
        if not parts:
            return False
        cmd = os.path.basename(parts[0])
        if cmd in _ALWAYS_INTERACTIVE:
            return True
        if cmd in _INTERACTIVE_NO_ARGS and len(parts) == 1:
            return True
        # If cmd is not a binary in PATH it may be a shell alias (e.g. dimonaserver → ssh).
        # Resolve it so that SSH aliases get routed to the PTY overlay correctly.
        env_path = (self._session.env or os.environ).get("PATH", "")
        if not shutil.which(cmd, path=env_path):
            resolved = self._resolve_alias(cmd)
            if resolved in _ALWAYS_INTERACTIVE:
                return True
            if resolved in _INTERACTIVE_NO_ARGS and len(parts) == 1:
                return True
        return False

    def _resolve_alias(self, cmd: str) -> str:
        """Return the first command name a bash alias expands to, or cmd itself."""
        try:
            out = subprocess.run(
                ["bash", "-i", "-c", f"alias {shlex.quote(cmd)} 2>/dev/null"],
                capture_output=True, text=True, timeout=1,
                stdin=subprocess.DEVNULL, env=self._session.env,
                preexec_fn=os.setsid,
            ).stdout.strip()
            # output: alias dimonaserver='ssh -i key.pem ubuntu@1.2.3.4'
            if "=" in out:
                val = out.split("=", 1)[1].strip().strip("'\"")
                first = val.split()[0] if val else ""
                return os.path.basename(first) if first else cmd
        except Exception:
            pass
        return cmd

    def _on_command_finished(self, block: Block, block_widget: CommandBlock) -> None:
        self._running_thread = None
        self._ctrl_c_shortcut.setEnabled(False)
        self._input_bar.set_running(False)
        block_widget.finalize(block.exit_code)
        self._history.add(block)
        self._input_bar.update_history(self._history.commands())
        self.cwd_changed.emit(self._session.cwd_display())
        self._input_bar.focus()

    def _on_ctrl_c(self) -> None:
        if self._running_thread is not None:
            self._running_thread.stop()

    def _start_pty_session(self, text: str, command: Command) -> None:
        if self._pty_widget is not None:
            return   # already running an interactive session

        self._active_cmd = command

        # Commands in _ALWAYS_INTERACTIVE are system binaries (ssh, vim, htop…).
        # Run them directly without a bash -i -c wrapper: this avoids bash startup
        # latency and TTY-mode interference that can prevent password/prompt output.
        parts = text.strip().split()
        cmd_name = os.path.basename(parts[0]) if parts else ""
        direct = cmd_name in _ALWAYS_INTERACTIVE

        # Overlay the PTY widget over the full panel geometry instead of
        # inserting it into the layout — this guarantees pixel-perfect coverage
        # with no leftover sliver from hidden siblings.
        self._pty_widget = PtyWidget(
            text, self._session.cwd, self._session.env, parent=self, direct=direct
        )
        self._pty_widget.session_finished.connect(self._on_pty_finished)
        self._pty_widget.setGeometry(self.rect())
        self._pty_widget.show()
        self._pty_widget.raise_()
        self._pty_widget.setFocus()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._pty_widget:
            self._pty_widget.setGeometry(self.rect())

    def _on_pty_finished(self, exit_code: int, final_text: str) -> None:
        if self._pty_widget:
            self._pty_widget.hide()
            self._pty_widget.deleteLater()
            self._pty_widget = None

        self._scroll.setVisible(True)
        self._sep.setVisible(True)
        self._input_bar.setVisible(True)
        self._input_bar.focus()

        if self._active_cmd:
            self._active_cmd.status = "done" if exit_code == 0 else "error"
            block = Block(
                command=self._active_cmd,
                stdout=final_text,
                stderr="",
                exit_code=exit_code,
                cwd=self._session.cwd,
            )
            self._history.add(block)
            self._add_block(block)
            self._input_bar.update_history(self._history.commands())
            self.cwd_changed.emit(self._session.cwd_display())
            self._active_cmd = None

    # ── tab completion ────────────────────────────────────────────────────────

    def _on_tab_pressed(self):
        if self._completion_popup.isVisible():
            self._accept_completion()   # Tab accepts current item
        else:
            self._trigger_completion()

    def _trigger_completion(self):
        base, path_prefix, name_prefix = self._input_bar.get_completion_context()
        if not name_prefix and not path_prefix:
            return

        matches = self._get_completions(path_prefix, name_prefix)
        if not matches:
            return

        if len(matches) == 1:
            self._input_bar.apply_completion(base, matches[0][0])
            return

        self._completion_popup.update_items(matches)
        self._position_completion_popup()
        self._completion_popup.show()
        self._completion_popup.raise_()
        self._input_bar.set_popup_open(True)

    def _on_input_text_changed(self, _text: str):
        base, path_prefix, name_prefix = self._input_bar.get_completion_context()

        # Need at least 1 char of the filename being typed to show suggestions
        if not name_prefix and not path_prefix:
            self._close_completion()
            return

        matches = self._get_completions(path_prefix, name_prefix)
        if matches:
            self._completion_popup.update_items(matches)
            self._position_completion_popup()
            self._completion_popup.show()
            self._completion_popup.raise_()
            self._input_bar.set_popup_open(True)
        else:
            self._close_completion()

    def _on_completion_activated(self, text: str):
        base, _, _ = self._input_bar.get_completion_context()
        self._input_bar.apply_completion(base, text)
        self._close_completion()
        self._input_bar.focus()

    def _accept_completion(self):
        text = self._completion_popup.current_text()
        if text:
            base, _, _ = self._input_bar.get_completion_context()
            self._input_bar.apply_completion(base, text)
        self._close_completion()

    def _close_completion(self):
        self._completion_popup.hide()
        self._input_bar.set_popup_open(False)

    def _position_completion_popup(self):
        # Map the input field's top-left corner into TerminalPanel coordinates
        field_rect = self._input_bar.input_field_rect()
        field_origin = self._input_bar.mapTo(self, QPoint(field_rect.x(), 0))

        popup_h = self._completion_popup.height()
        popup_w = max(220, field_rect.width())

        x = field_origin.x()
        y = self._input_bar.y() - popup_h - 4

        self._completion_popup.setFixedWidth(popup_w)
        self._completion_popup.move(x, y)

    def _get_completions(self, path_prefix: str, name_prefix: str) -> list[tuple[str, bool]]:
        cwd = self._session.cwd

        if path_prefix:
            if path_prefix.startswith("~"):
                search_dir = str(Path.home()) + path_prefix[1:]
            elif os.path.isabs(path_prefix):
                search_dir = path_prefix
            else:
                search_dir = os.path.join(cwd, path_prefix)
        else:
            search_dir = cwd

        try:
            matches = []
            with os.scandir(search_dir) as entries:
                for entry in entries:
                    if entry.name.startswith(name_prefix):
                        is_dir = entry.is_dir()
                        matches.append((path_prefix + entry.name + ("/" if is_dir else ""), is_dir))

            # #43: also complete executables from PATH when no path separator typed
            if not path_prefix:
                seen = {m[0] for m in matches}
                env_path = os.environ.get("PATH", "")
                for path_dir in env_path.split(os.pathsep):
                    try:
                        with os.scandir(path_dir) as bin_entries:
                            for entry in bin_entries:
                                if (entry.name.startswith(name_prefix)
                                        and entry.name not in seen
                                        and entry.is_file(follow_symlinks=True)
                                        and os.access(entry.path, os.X_OK)):
                                    matches.append((entry.name, False))
                                    seen.add(entry.name)
                    except (PermissionError, FileNotFoundError, OSError):
                        continue

            return sorted(matches, key=lambda x: (not x[1], x[0].lower()))
        except (PermissionError, FileNotFoundError, OSError):
            return []

    # ── AI handlers ───────────────────────────────────────────────────────────

    def _on_fix_requested(self, command_text: str, stderr: str, cwd: str) -> None:
        from ..services.ai_service import AiService
        if not AiService.instance().is_enabled():
            return
        self._input_bar.set_thinking(True)
        block = Block(
            command=Command(text=command_text),
            stdout="",
            stderr=stderr,
            exit_code=1,
            cwd=cwd,
        )
        worker = AiService.instance().fix(block)

        def _done(text: str) -> None:
            self._input_bar.set_thinking(False)
            self._input_bar.set_text(text)

        worker.result_ready.connect(_done)
        worker.error_occurred.connect(lambda _: self._input_bar.set_thinking(False))
        self._ai_workers.append(worker)
        worker.start()

    def _agent_chat(self, request: str) -> None:
        from ..services.ai_service import AiService, AgentWorker
        if not AiService.instance().is_enabled():
            return

        # Cancel any running agent
        if self._agent_worker is not None:
            self._agent_worker.cancel()
            self._agent_worker = None

        self._input_bar.set_thinking(True)

        # Create a visible block for the AI conversation
        from ..domain.command import Command
        from ..domain.block import Block
        cmd  = Command(text=f"> {request}")
        blk  = Block(command=cmd, stdout="", stderr="", exit_code=-1, cwd=self._session.cwd)
        bw   = CommandBlock(blk)
        bw.remove_requested.connect(self._remove_block)
        self._blocks_layout.insertWidget(self._blocks_layout.count() - 1, bw)

        worker = AiService.instance().agent_chat(request, self._session.cwd)
        self._agent_worker = worker

        def _on_tool(tool: str, arg: str) -> None:
            icons = {
                "read_file":   "📄",
                "list_dir":    "📂",
                "run_command": "⚙",
                "ask_user":    "💬",
            }
            bw.append_output(f"{icons.get(tool, '🔧')} {tool}: {arg}\n")

        def _on_tool_result(tool: str, arg: str, preview: str) -> None:
            bw.append_output(f"   ↳ {preview}\n")

        def _on_permission(command: str) -> None:
            bw.append_output(f"⚠  Asking permission to run: {command}\n")
            banner = self._permission_banner
            banner.show_request(command)
            # Use one-shot lambdas via a local variable to avoid signal accumulation.
            def _allow():
                try: banner.allowed.disconnect(_allow)
                except RuntimeError: pass
                try: banner.denied.disconnect(_deny)
                except RuntimeError: pass
                worker.grant_permission(True)
            def _deny():
                try: banner.allowed.disconnect(_allow)
                except RuntimeError: pass
                try: banner.denied.disconnect(_deny)
                except RuntimeError: pass
                worker.grant_permission(False)
            banner.allowed.connect(_allow)
            banner.denied.connect(_deny)

        def _on_ask(question: str) -> None:
            bw.append_output(f"💬 ASK: {question}\n")
            banner = self._permission_banner
            banner.show_question(question)
            def _send(answer: str):
                try: banner.answered.disconnect(_send)
                except RuntimeError: pass
                bw.append_output(f"   ↳ User: {answer}\n")
                worker.answer_question(answer)
            banner.answered.connect(_send)

        def _on_final(text: str) -> None:
            self._input_bar.set_thinking(False)
            bw.append_output(f"\n💡 {text}")
            bw.finalize(0)
            self._agent_worker = None

        def _on_command(cmd_text: str) -> None:
            self._input_bar.set_thinking(False)
            bw.append_output(f"\n→ {cmd_text}")
            bw.finalize(0)
            self._input_bar.set_text(cmd_text)
            self._agent_worker = None

        def _on_error(msg: str) -> None:
            self._input_bar.set_thinking(False)
            bw.append_output(f"\n⚠  {msg}")
            bw.finalize(1)
            self._agent_worker = None

        worker.tool_called.connect(_on_tool)
        worker.tool_result_ready.connect(_on_tool_result)
        worker.permission_needed.connect(_on_permission)
        worker.ask_user.connect(_on_ask)
        worker.final_answer.connect(_on_final)
        worker.command_ready.connect(_on_command)
        worker.error_occurred.connect(_on_error)
        self._ai_workers.append(worker)
        worker.start()

    # ── .env detection ────────────────────────────────────────────────────────

    def _check_env_files(self) -> None:
        from ..services.settings_service import SettingsService
        policy = SettingsService.instance().get().auto_load_env
        if policy == "never":
            return
        env_files = self._session.detect_env_files()
        if not env_files:
            return
        cwd = self._session.cwd
        if policy == "always":
            variables = self._session.load_env_file(env_files[0])
            self._session.apply_env(variables)
            return
        # policy == "ask" — emit signal; MainWindow handles dialog
        self.env_file_detected.emit(cwd, str(env_files[0]))

    # ── block management ──────────────────────────────────────────────────────

    def _add_block(self, block: Block) -> None:
        widget = CommandBlock(block)
        widget.remove_requested.connect(self._remove_block)
        widget.favorite_requested.connect(self.favorite_requested)
        widget.fix_requested.connect(self._on_fix_requested)
        self._blocks_layout.insertWidget(self._blocks_layout.count() - 1, widget)

    def _remove_block(self, widget: QWidget) -> None:
        self._blocks_layout.removeWidget(widget)
        widget.deleteLater()
        if self._search_bar.isVisible():
            self._on_search(self._search_bar.query())

    def apply_theme(self, p: Palette) -> None:
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {p.bg}; }}"
        )
        self._blocks_container.setStyleSheet(f"QWidget {{ background: {p.bg}; }}")
        self._sep.setStyleSheet(
            f"QFrame {{ color: {p.bg_overlay}; background: {p.bg_overlay}; max-height: 1px; }}"
        )

    def toggle_collapse_all(self) -> None:
        blocks = self._all_blocks()
        any_expanded = any(b._expanded for b in blocks if b._output_widget)
        for b in blocks:
            b.collapse() if any_expanded else b.expand()

    def clear_blocks(self) -> None:
        while self._blocks_layout.count() > 1:
            item = self._blocks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._match_blocks.clear()

    def _all_blocks(self) -> list[CommandBlock]:
        blocks = []
        for i in range(self._blocks_layout.count() - 1):
            item = self._blocks_layout.itemAt(i)
            if item and isinstance(item.widget(), CommandBlock):
                blocks.append(item.widget())
        return blocks

    # ── search ────────────────────────────────────────────────────────────────

    def _on_search(self, query: str) -> None:
        self._clear_highlights()
        self._match_blocks.clear()
        self._match_index = 0

        if not query.strip():
            self._search_bar.update_count(0)
            return

        q = query.lower()
        for block in self._all_blocks():
            if q in block.searchable_text:
                self._match_blocks.append(block)

        self._search_bar.update_count(len(self._match_blocks), 0)

        if self._match_blocks:
            self._highlight_current()
            self._scroll_to_block(self._match_blocks[0])

    def _search_next(self) -> None:
        if not self._match_blocks:
            return
        self._match_index = (self._match_index + 1) % len(self._match_blocks)
        self._highlight_current()
        self._scroll_to_block(self._match_blocks[self._match_index])
        self._search_bar.update_count(len(self._match_blocks), self._match_index)

    def _search_prev(self) -> None:
        if not self._match_blocks:
            return
        self._match_index = (self._match_index - 1) % len(self._match_blocks)
        self._highlight_current()
        self._scroll_to_block(self._match_blocks[self._match_index])
        self._search_bar.update_count(len(self._match_blocks), self._match_index)

    def _highlight_current(self) -> None:
        for i, block in enumerate(self._match_blocks):
            block.set_search_highlight(i == self._match_index)

    def _clear_highlights(self) -> None:
        for block in self._match_blocks:
            block.set_search_highlight(False)

    def _close_search(self) -> None:
        self._search_bar.setVisible(False)
        self._clear_highlights()
        self._match_blocks.clear()

    def _scroll_to_block(self, block: CommandBlock) -> None:
        self._scroll.ensureWidgetVisible(block)
