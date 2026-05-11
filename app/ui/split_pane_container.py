from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Qt, Signal

from .terminal_panel import TerminalPanel
from ..core.command_executor import BaseExecutor
from ..infra.storage.history_repository import HistoryRepository
from .theme import ThemeManager


class SplitPaneContainer(QWidget):
    """Manages one or more TerminalPanel instances in a splitter tree."""

    cwd_changed        = Signal(str)
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

        self._root_splitter = QSplitter(Qt.Horizontal)
        self._root_splitter.setHandleWidth(3)
        self._root_splitter.setChildrenCollapsible(False)
        layout.addWidget(self._root_splitter)

        first = self._make_panel()
        self._root_splitter.addWidget(first)
        self._set_active(first)
        self._apply_splitter_style()

        ThemeManager.instance().theme_changed.connect(lambda p: self._apply_splitter_style())

    # ── panel factory ─────────────────────────────────────────────────────────

    def _make_panel(self) -> TerminalPanel:
        panel = TerminalPanel(self._executor, self._repository)
        panel.cwd_changed.connect(lambda cwd, p=panel: self._on_panel_cwd(cwd, p))
        panel.favorite_requested.connect(self.favorite_requested)
        panel.env_file_detected.connect(self.env_file_detected)
        panel.focused.connect(lambda p=panel: self._on_panel_focused(p))
        return panel

    def _on_panel_focused(self, panel: TerminalPanel) -> None:
        if panel is not self._active:
            self._set_active(panel)

    def _on_panel_cwd(self, cwd: str, panel: TerminalPanel) -> None:
        if panel is self._active:
            self.cwd_changed.emit(cwd)

    def _set_active(self, panel: TerminalPanel) -> None:
        old = self._active
        self._active = panel
        p = ThemeManager.instance().current
        if old and old is not panel:
            old.setStyleSheet("")
        panel.setStyleSheet(
            f"TerminalPanel {{ border: 1px solid {p.blue}; }}"
        )
        self.cwd_changed.emit(panel.cwd_display)

    def _apply_splitter_style(self) -> None:
        p = ThemeManager.instance().current
        style = (
            f"QSplitter::handle {{ background: {p.bg_overlay}; }}"
            f"QSplitter::handle:hover {{ background: {p.blue}; }}"
        )
        self._root_splitter.setStyleSheet(style)
        for splitter in self._all_splitters():
            splitter.setStyleSheet(style)

    def _all_splitters(self) -> list[QSplitter]:
        result: list[QSplitter] = []
        def _collect(w: QWidget) -> None:
            if isinstance(w, QSplitter):
                result.append(w)
                for i in range(w.count()):
                    _collect(w.widget(i))
        _collect(self._root_splitter)
        return result

    # ── tree helpers ──────────────────────────────────────────────────────────

    def _all_panels(self) -> list[TerminalPanel]:
        result: list[TerminalPanel] = []
        def _collect(w: QWidget) -> None:
            if isinstance(w, TerminalPanel):
                result.append(w)
            elif isinstance(w, QSplitter):
                for i in range(w.count()):
                    _collect(w.widget(i))
        _collect(self._root_splitter)
        return result

    def _find_parent(
        self, panel: TerminalPanel, splitter: QSplitter
    ) -> tuple[QSplitter | None, int]:
        for i in range(splitter.count()):
            w = splitter.widget(i)
            if w is panel:
                return splitter, i
            if isinstance(w, QSplitter):
                result = self._find_parent(panel, w)
                if result[0] is not None:
                    return result
        return None, -1

    def _find_parent_splitter(
        self, target: QSplitter
    ) -> tuple[QSplitter | None, int]:
        def _search(s: QSplitter) -> tuple[QSplitter | None, int]:
            for i in range(s.count()):
                w = s.widget(i)
                if w is target:
                    return s, i
                if isinstance(w, QSplitter):
                    result = _search(w)
                    if result[0] is not None:
                        return result
            return None, -1
        return _search(self._root_splitter)

    # ── split actions ─────────────────────────────────────────────────────────

    def split_horizontal(self) -> None:
        self._split(Qt.Horizontal)

    def split_vertical(self) -> None:
        self._split(Qt.Vertical)

    def _split(self, orientation: Qt.Orientation) -> None:
        if self._active is None:
            return
        parent_splitter, idx = self._find_parent(self._active, self._root_splitter)
        if parent_splitter is None:
            return

        new_panel = self._make_panel()

        if parent_splitter.orientation() == orientation:
            parent_splitter.insertWidget(idx + 1, new_panel)
            total = sum(parent_splitter.sizes())
            n = parent_splitter.count()
            parent_splitter.setSizes([total // n] * n)
        else:
            sub = self._make_splitter(orientation)
            sizes = parent_splitter.sizes()
            old_size = sizes[idx] if idx < len(sizes) else 200

            self._active.setParent(None)
            sub.addWidget(self._active)
            sub.addWidget(new_panel)
            sub.setSizes([old_size // 2, old_size - old_size // 2])
            parent_splitter.insertWidget(idx, sub)
            parent_splitter.setSizes(sizes)

        self._set_active(new_panel)
        new_panel.focus_input()

    def _make_splitter(self, orientation: Qt.Orientation) -> QSplitter:
        s = QSplitter(orientation)
        s.setHandleWidth(3)
        s.setChildrenCollapsible(False)
        p = ThemeManager.instance().current
        s.setStyleSheet(
            f"QSplitter::handle {{ background: {p.bg_overlay}; }}"
            f"QSplitter::handle:hover {{ background: {p.blue}; }}"
        )
        return s

    # ── close pane ────────────────────────────────────────────────────────────

    def close_active_pane(self) -> None:
        panels = self._all_panels()
        if len(panels) <= 1:
            return
        panel = self._active
        parent_splitter, idx = self._find_parent(panel, self._root_splitter)
        if parent_splitter is None:
            return

        # Synchronously remove from splitter — setParent(None) is immediate
        panel.setParent(None)
        panel.deleteLater()

        # Collapse parent splitter if it now has only 1 child
        self._collapse_if_single(parent_splitter)

        remaining = self._all_panels()
        if remaining:
            new_idx = min(max(0, idx - 1), len(remaining) - 1)
            self._set_active(remaining[new_idx])
            self._active.focus_input()

    def _collapse_if_single(self, splitter: QSplitter) -> None:
        """Replace a sub-splitter containing 1 child with that child directly."""
        if splitter is self._root_splitter or splitter.count() != 1:
            return
        child = splitter.widget(0)
        parent, idx = self._find_parent_splitter(splitter)
        if parent is None:
            return
        sizes = parent.sizes()
        slot_size = sizes[idx] if idx < len(sizes) else 200
        child.setParent(None)
        parent.insertWidget(idx, child)
        new_sizes = parent.sizes()
        if idx < len(new_sizes):
            new_sizes[idx] = slot_size
            parent.setSizes(new_sizes)
        splitter.setParent(None)
        splitter.deleteLater()

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
