import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame,
)
from PySide6.QtCore import Signal, QPoint

from .command_block import CommandBlock
from .completion_popup import CompletionPopup
from .input_bar import InputBar
from .search_bar import SearchBar
from ..core.command_executor import BaseExecutor
from ..core.shell_session import ShellSession
from ..domain.command import Command
from ..domain.block import Block
from ..services.history_service import HistoryService
from ..infra.storage.history_repository import HistoryRepository


class TerminalPanel(QWidget):
    """
    Self-contained terminal tab: owns ShellSession, HistoryService,
    the blocks scroll area, SearchBar, InputBar and CompletionPopup.
    """

    cwd_changed = Signal(str)   # emits cwd_display after every command

    def __init__(self, executor: BaseExecutor, repository: HistoryRepository, parent=None):
        super().__init__(parent)
        self._executor  = executor
        self._session   = ShellSession()
        self._history   = HistoryService(repository)

        self._match_blocks: list[CommandBlock] = []
        self._match_index:  int = 0

        self._build_ui()
        self._wire_completion()

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def cwd_display(self) -> str:
        return self._session.cwd_display()

    def focus_input(self) -> None:
        self._input_bar.focus()

    def set_input_text(self, text: str) -> None:
        self._input_bar.set_text(text)

    def toggle_search(self) -> None:
        visible = not self._search_bar.isVisible()
        self._search_bar.setVisible(visible)
        if visible:
            self._search_bar.focus()
        else:
            self._clear_highlights()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
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
        self._blocks_layout.setContentsMargins(20, 16, 20, 16)
        self._blocks_layout.setSpacing(12)
        self._blocks_layout.addStretch()

        self._scroll.setWidget(self._blocks_container)
        self._scroll.verticalScrollBar().rangeChanged.connect(
            lambda _min, maximum: self._scroll.verticalScrollBar().setValue(maximum)
        )
        layout.addWidget(self._scroll)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame { color: #1e2235; background: #1e2235; max-height: 1px; }")
        layout.addWidget(sep)

        self._input_bar = InputBar()
        self._input_bar.command_submitted.connect(self._on_command)
        layout.addWidget(self._input_bar)

        # Popup is a child of this panel — overlaps siblings, no top-level issues
        self._completion_popup = CompletionPopup(self)
        self._completion_popup.item_activated.connect(self._on_completion_activated)

    def _wire_completion(self):
        self._input_bar.tab_pressed.connect(self._on_tab_pressed)
        self._input_bar.esc_pressed.connect(self._close_completion)
        self._input_bar.completion_up.connect(self._completion_popup.select_prev)
        self._input_bar.completion_down.connect(self._completion_popup.select_next)
        self._input_bar.completion_accepted.connect(self._accept_completion)
        self._input_bar.text_changed.connect(self._on_input_text_changed)

    # ── command handling ──────────────────────────────────────────────────────

    def _on_command(self, text: str) -> None:
        self._close_completion()

        if text.strip() == "clear":
            self.clear_blocks()
            return

        command = Command(text=text)

        if self._session.try_cd(text):
            command.status = "done"
            block = Block(command=command, stdout="", stderr="", exit_code=0, cwd=self._session.cwd)
        else:
            block = self._executor.execute(command, cwd=self._session.cwd, env=self._session.env)

        self._history.add(block)
        self._add_block(block)
        self._input_bar.update_history(self._history.commands())
        self.cwd_changed.emit(self._session.cwd_display())

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
            return sorted(matches, key=lambda x: (not x[1], x[0].lower()))
        except (PermissionError, FileNotFoundError, OSError):
            return []

    # ── block management ──────────────────────────────────────────────────────

    def _add_block(self, block: Block) -> None:
        widget = CommandBlock(block)
        widget.remove_requested.connect(self._remove_block)
        self._blocks_layout.insertWidget(self._blocks_layout.count() - 1, widget)

    def _remove_block(self, widget: QWidget) -> None:
        self._blocks_layout.removeWidget(widget)
        widget.deleteLater()
        if self._search_bar.isVisible():
            self._on_search(self._search_bar.query())

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
