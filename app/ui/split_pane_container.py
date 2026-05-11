from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, QLabel,
)
from PySide6.QtCore import Qt, Signal

from .terminal_panel import TerminalPanel
from ..core.command_executor import BaseExecutor
from ..infra.storage.history_repository import HistoryRepository
from .theme import ThemeManager, Palette


class _PaneWrapper(QWidget):
    """TerminalPanel + thin header with a close button."""

    close_requested = Signal(object)  # emits self

    def __init__(self, panel: TerminalPanel, parent=None):
        super().__init__(parent)
        self.panel = panel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QWidget()
        self._header.setFixedHeight(22)
        h_layout = QHBoxLayout(self._header)
        h_layout.setContentsMargins(8, 0, 4, 0)
        h_layout.setSpacing(4)

        self._title_lbl = QLabel("Terminal")
        self._title_lbl.setStyleSheet(
            "font-size: 8pt; background: transparent;"
        )
        h_layout.addWidget(self._title_lbl, 1)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(18, 18)
        self._close_btn.setToolTip("Close pane (Ctrl+Shift+W)")
        self._close_btn.clicked.connect(lambda: self.close_requested.emit(self))
        h_layout.addWidget(self._close_btn)

        layout.addWidget(self._header)
        layout.addWidget(panel)

        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._refresh_style()

    def show_header(self, visible: bool) -> None:
        self._header.setVisible(visible)

    def apply_theme(self, p: Palette) -> None:
        self._palette = p
        self._refresh_style()

    def _refresh_style(self) -> None:
        try:
            p = self._palette
        except AttributeError:
            p = ThemeManager.instance().current

        active = getattr(self, "_active", False)
        border_color = p.blue if active else p.bg_overlay
        header_bg = p.bg_active if active else p.bg_panel

        self._header.setStyleSheet(
            f"QWidget {{ background: {header_bg};"
            f" border-bottom: 1px solid {border_color}; }}"
        )
        self._title_lbl.setStyleSheet(
            f"color: {p.fg_muted if not active else p.fg};"
            f" font-size: 8pt; background: transparent;"
        )
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted};"
            f" border: none; border-radius: 3px; font-size: 9pt; }}"
            f"QPushButton:hover {{ background: {p.red}; color: {p.bg}; }}"
        )
        # Draw a left border on the active pane
        self.setStyleSheet(
            f"_PaneWrapper {{ border-left: 2px solid {p.blue}; }}"
            if active else ""
        )


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

        first_wrapper = self._make_pane()
        self._root_splitter.addWidget(first_wrapper)
        self._set_active(first_wrapper.panel)
        self._update_headers()
        self._apply_splitter_style()

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self._on_theme_changed)

    # ── pane factory ─────────────────────────────────────────────────────────

    def _make_pane(self) -> _PaneWrapper:
        panel = TerminalPanel(self._executor, self._repository)
        panel.cwd_changed.connect(lambda cwd, p=panel: self._on_panel_cwd(cwd, p))
        panel.favorite_requested.connect(self.favorite_requested)
        panel.env_file_detected.connect(self.env_file_detected)
        panel.focused.connect(lambda p=panel: self._on_panel_focused(p))

        wrapper = _PaneWrapper(panel)
        wrapper.close_requested.connect(self._on_close_requested)
        p = ThemeManager.instance().current
        wrapper.apply_theme(p)
        return wrapper

    def _on_close_requested(self, wrapper: _PaneWrapper) -> None:
        self._close_pane_by_panel(wrapper.panel)

    def _on_panel_focused(self, panel: TerminalPanel) -> None:
        if panel is not self._active:
            self._set_active(panel)

    def _on_panel_cwd(self, cwd: str, panel: TerminalPanel) -> None:
        if panel is self._active:
            self.cwd_changed.emit(cwd)

    # ── active state ─────────────────────────────────────────────────────────

    def _set_active(self, panel: TerminalPanel) -> None:
        old_wrapper = self._wrapper_for(self._active) if self._active else None
        if old_wrapper:
            old_wrapper.set_active(False)

        self._active = panel

        new_wrapper = self._wrapper_for(panel)
        if new_wrapper:
            new_wrapper.set_active(True)

        self.cwd_changed.emit(panel.cwd_display)

    # ── tree traversal ────────────────────────────────────────────────────────

    def _all_wrappers(self) -> list[_PaneWrapper]:
        result: list[_PaneWrapper] = []
        def _collect(w: QWidget) -> None:
            if isinstance(w, _PaneWrapper):
                result.append(w)
            elif isinstance(w, QSplitter):
                for i in range(w.count()):
                    _collect(w.widget(i))
        _collect(self._root_splitter)
        return result

    def _all_panels(self) -> list[TerminalPanel]:
        return [wr.panel for wr in self._all_wrappers()]

    def _wrapper_for(self, panel: TerminalPanel) -> _PaneWrapper | None:
        for wr in self._all_wrappers():
            if wr.panel is panel:
                return wr
        return None

    def _find_parent(
        self, target: QWidget, splitter: QSplitter
    ) -> tuple[QSplitter | None, int]:
        for i in range(splitter.count()):
            w = splitter.widget(i)
            if w is target:
                return splitter, i
            if isinstance(w, QSplitter):
                result = self._find_parent(target, w)
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
                    r = _search(w)
                    if r[0] is not None:
                        return r
            return None, -1
        return _search(self._root_splitter)

    # ── split ─────────────────────────────────────────────────────────────────

    def split_horizontal(self) -> None:
        self._split(Qt.Horizontal)

    def split_vertical(self) -> None:
        self._split(Qt.Vertical)

    def _split(self, orientation: Qt.Orientation) -> None:
        if self._active is None:
            return
        wrapper = self._wrapper_for(self._active)
        if wrapper is None:
            return
        parent_splitter, idx = self._find_parent(wrapper, self._root_splitter)
        if parent_splitter is None:
            return

        new_wrapper = self._make_pane()

        if parent_splitter.orientation() == orientation:
            parent_splitter.insertWidget(idx + 1, new_wrapper)
            total = sum(parent_splitter.sizes())
            n = parent_splitter.count()
            parent_splitter.setSizes([total // n] * n)
        else:
            sub = self._make_splitter(orientation)
            sizes = parent_splitter.sizes()
            old_size = sizes[idx] if idx < len(sizes) else 200

            wrapper.setParent(None)
            sub.addWidget(wrapper)
            sub.addWidget(new_wrapper)
            sub.setSizes([old_size // 2, old_size - old_size // 2])
            parent_splitter.insertWidget(idx, sub)
            parent_splitter.setSizes(sizes)

        self._update_headers()
        self._set_active(new_wrapper.panel)
        new_wrapper.panel.focus_input()

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

    def _close_pane_by_panel(self, panel: TerminalPanel) -> None:
        panels = self._all_panels()
        if len(panels) <= 1:
            return

        wrapper = self._wrapper_for(panel)
        if wrapper is None:
            return

        parent_splitter, idx = self._find_parent(wrapper, self._root_splitter)
        if parent_splitter is None:
            return

        wrapper.setParent(None)
        wrapper.deleteLater()

        self._collapse_if_single(parent_splitter)

        remaining = self._all_panels()
        if remaining:
            new_idx = min(max(0, idx - 1), len(remaining) - 1)
            self._set_active(remaining[new_idx])
            self._active.focus_input()

        self._update_headers()

    def close_active_pane(self) -> None:
        if self._active:
            self._close_pane_by_panel(self._active)

    def _collapse_if_single(self, splitter: QSplitter) -> None:
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

    # ── headers / theme ───────────────────────────────────────────────────────

    def _update_headers(self) -> None:
        wrappers = self._all_wrappers()
        multi = len(wrappers) > 1
        for wr in wrappers:
            wr.show_header(multi)

    def _apply_splitter_style(self) -> None:
        p = ThemeManager.instance().current
        style = (
            f"QSplitter::handle {{ background: {p.bg_overlay}; }}"
            f"QSplitter::handle:hover {{ background: {p.blue}; }}"
        )
        for s in self._all_splitters():
            s.setStyleSheet(style)

    def _all_splitters(self) -> list[QSplitter]:
        result: list[QSplitter] = []
        def _collect(w: QWidget) -> None:
            if isinstance(w, QSplitter):
                result.append(w)
                for i in range(w.count()):
                    _collect(w.widget(i))
        _collect(self._root_splitter)
        return result

    def _on_theme_changed(self, p: Palette) -> None:
        for wr in self._all_wrappers():
            wr.apply_theme(p)
        self._apply_splitter_style()

    # ── delegated API ─────────────────────────────────────────────────────────

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
