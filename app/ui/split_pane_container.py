from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QFrame
from PySide6.QtCore import Qt, Signal

from .terminal_panel import TerminalPanel
from ..core.command_executor import BaseExecutor
from ..infra.storage.history_repository import HistoryRepository
from .theme import ThemeManager


class SplitPaneContainer(QWidget):
    """Manages one or more TerminalPanel instances in a splitter tree."""

    cwd_changed       = Signal(str)
    favorite_requested = Signal(str, str, str)
    env_file_detected  = Signal(str, str)

    def __init__(
        self,
        executor: BaseExecutor,
        repository: HistoryRepository,
        parent=None,
    ):
        super().__init__(parent)
        self._executor   = executor
        self._repository = repository
        self._active: TerminalPanel | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # The root widget is either a TerminalPanel (no split) or a QSplitter
        self._root_splitter = QSplitter(Qt.Horizontal)
        self._root_splitter.setHandleWidth(3)
        self._root_splitter.setChildrenCollapsible(False)
        layout.addWidget(self._root_splitter)

        first = self._make_panel()
        self._root_splitter.addWidget(first)
        self._set_active(first)
        self._apply_splitter_style()

        _tm = ThemeManager.instance()
        _tm.theme_changed.connect(lambda p: self._apply_splitter_style())

    def _make_panel(self) -> TerminalPanel:
        panel = TerminalPanel(self._executor, self._repository)
        panel.cwd_changed.connect(lambda cwd, p=panel: self._on_panel_cwd(cwd, p))
        panel.favorite_requested.connect(self.favorite_requested)
        panel.env_file_detected.connect(self.env_file_detected)
        panel.installEventFilter(self)
        # Click on input bar or panel body → make active
        panel._input_bar.installEventFilter(self)
        return panel

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.MouseButtonPress, QEvent.FocusIn):
            panel = self._panel_for_child(obj)
            if panel and panel is not self._active:
                self._set_active(panel)
        return False

    def _panel_for_child(self, obj) -> TerminalPanel | None:
        for panel in self._all_panels():
            if obj is panel or obj is panel._input_bar:
                return panel
        return None

    def _all_panels(self) -> list[TerminalPanel]:
        result = []
        def _collect(widget):
            if isinstance(widget, TerminalPanel):
                result.append(widget)
            elif isinstance(widget, QSplitter):
                for i in range(widget.count()):
                    _collect(widget.widget(i))
        _collect(self._root_splitter)
        return result

    def _set_active(self, panel: TerminalPanel) -> None:
        old = self._active
        self._active = panel
        p = ThemeManager.instance().current
        if old and old is not panel:
            old.setStyleSheet(f"TerminalPanel {{ border: none; }}")
        panel.setStyleSheet(
            f"TerminalPanel {{ border: 1px solid {p.blue}; border-radius: 0px; }}"
        )
        self.cwd_changed.emit(panel.cwd_display)

    def _on_panel_cwd(self, cwd: str, panel: TerminalPanel) -> None:
        if panel is self._active:
            self.cwd_changed.emit(cwd)

    def _apply_splitter_style(self) -> None:
        p = ThemeManager.instance().current
        self._root_splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {p.bg_overlay}; }}"
            f"QSplitter::handle:hover {{ background: {p.blue}; }}"
        )

    # ── split actions ─────────────────────────────────────────────────────────

    def split_horizontal(self) -> None:
        self._split(Qt.Horizontal)

    def split_vertical(self) -> None:
        self._split(Qt.Vertical)

    def _split(self, orientation: Qt.Orientation) -> None:
        if self._active is None:
            return
        # Find which splitter directly contains the active panel
        parent_splitter, idx = self._find_parent(self._active, self._root_splitter)
        if parent_splitter is None:
            return

        if parent_splitter.orientation() == orientation:
            # Just add a new pane at idx+1 in the same splitter
            new_panel = self._make_panel()
            parent_splitter.insertWidget(idx + 1, new_panel)
            # Re-distribute sizes equally
            total = sum(parent_splitter.sizes())
            n = parent_splitter.count()
            parent_splitter.setSizes([total // n] * n)
        else:
            # Need a sub-splitter with the new orientation
            sub = QSplitter(orientation)
            sub.setHandleWidth(3)
            sub.setChildrenCollapsible(False)
            sub.setStyleSheet(self._root_splitter.styleSheet())

            # Remove the active panel from its current position
            sizes = parent_splitter.sizes()
            old_size = sizes[idx]
            # Temporarily re-parent the active panel to sub
            self._active.setParent(None)
            new_panel = self._make_panel()
            sub.addWidget(self._active)
            sub.addWidget(new_panel)
            sub.setSizes([old_size // 2, old_size // 2])
            # Insert sub-splitter where the panel was
            parent_splitter.insertWidget(idx, sub)
            parent_splitter.setSizes(sizes)

        new_panel = self._all_panels()[-1]
        self._set_active(new_panel)
        new_panel.focus_input()

    def _find_parent(self, panel: TerminalPanel, splitter: QSplitter):
        for i in range(splitter.count()):
            w = splitter.widget(i)
            if w is panel:
                return splitter, i
            if isinstance(w, QSplitter):
                result = self._find_parent(panel, w)
                if result[0] is not None:
                    return result
        return None, -1

    def close_active_pane(self) -> None:
        """Close the active pane if more than one exists."""
        panels = self._all_panels()
        if len(panels) <= 1:
            return
        panel = self._active
        parent_splitter, idx = self._find_parent(panel, self._root_splitter)
        if parent_splitter is None:
            return
        panel.deleteLater()
        # If parent splitter is now empty or has 1 widget, collapse it
        # Pick a new active panel
        remaining = [p for p in self._all_panels() if p is not panel]
        if remaining:
            self._set_active(remaining[max(0, idx - 1)])
            self._active.focus_input()

    # ── delegated API (matches TerminalPanel interface) ───────────────────────

    @property
    def cwd_display(self) -> str:
        return self._active.cwd_display if self._active else "~"

    @property
    def _session(self):
        return self._active._session if self._active else None

    def focus_input(self) -> None:
        if self._active:
            self._active.focus_input()

    def set_input_text(self, text: str) -> None:
        if self._active:
            self._active.set_input_text(text)

    def _on_command(self, text: str) -> None:
        if self._active:
            self._active._on_command(text)

    def toggle_search(self) -> None:
        if self._active:
            self._active.toggle_search()

    def toggle_collapse_all(self) -> None:
        if self._active:
            self._active.toggle_collapse_all()

    def clear_blocks(self) -> None:
        if self._active:
            self._active.clear_blocks()
