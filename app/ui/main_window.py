from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QFrame,
)
from PySide6.QtGui import QKeySequence, QShortcut

from .sidebar import Sidebar
from .tab_bar import TabBar
from .terminal_panel import TerminalPanel
from .theme import Palette, ThemeManager
from ..core.command_executor import BaseExecutor
from ..infra.storage.history_repository import HistoryRepository
from ..services.favorites_service import FavoritesService


class MainWindow(QMainWindow):
    def __init__(
        self,
        executor: BaseExecutor,
        repository: HistoryRepository,
        favorites_service: FavoritesService,
    ):
        super().__init__()
        self._executor           = executor
        self._repository         = repository
        self._favorites_service  = favorites_service
        self._panels: list[TerminalPanel] = []
        self._active_index  = 0

        self.setWindowTitle("Blocksh")
        self.resize(1100, 700)
        self._build_ui()
        self._setup_shortcuts()
        self._add_tab()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.history_open_requested.connect(self._load_history)
        self._sidebar.command_selected.connect(self._on_history_command_selected)
        self._sidebar.theme_selected.connect(lambda name: ThemeManager.instance().set_theme(name))
        self._sidebar.favorites_open_requested.connect(self._load_favorites)
        self._sidebar.favorite_command_selected.connect(self._on_favorite_command_selected)
        self._sidebar.favorite_rename_requested.connect(self._on_favorite_rename)
        self._sidebar.favorite_delete_requested.connect(self._on_favorite_delete)
        root.addWidget(self._sidebar)

        self._v_sep = QFrame()
        self._v_sep.setFrameShape(QFrame.VLine)
        root.addWidget(self._v_sep)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._tab_bar = TabBar()
        self._tab_bar.tab_add_requested.connect(self._add_tab)
        self._tab_bar.tab_close_requested.connect(self._close_tab)
        self._tab_bar.tab_switched.connect(self._switch_tab)
        self._tab_bar.search_requested.connect(self._toggle_search)
        self._tab_bar.collapse_all_requested.connect(self._toggle_collapse_all)

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)
        right_layout.addWidget(self._tab_bar)

        self._h_sep = QFrame()
        self._h_sep.setFrameShape(QFrame.HLine)
        right_layout.addWidget(self._h_sep)

        self._stack = QStackedWidget()
        right_layout.addWidget(self._stack)

        root.addWidget(right)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._add_tab)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(
            lambda: self._close_tab(self._active_index)
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._toggle_search)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._clear_active)

    # ── tab management ────────────────────────────────────────────────────────

    def _add_tab(self) -> None:
        panel = TerminalPanel(self._executor, self._repository)
        panel.cwd_changed.connect(lambda cwd, p=panel: self._on_panel_cwd_changed(cwd, p))
        panel.favorite_requested.connect(self._on_favorite_requested)
        self._panels.append(panel)
        self._stack.addWidget(panel)
        self._tab_bar.add_tab(f"Terminal {len(self._panels)}")
        self._switch_tab(len(self._panels) - 1)

    def _close_tab(self, index: int) -> None:
        if len(self._panels) <= 1:
            return
        panel = self._panels.pop(index)
        self._stack.removeWidget(panel)
        panel.deleteLater()
        self._tab_bar.remove_tab(index)

        if self._active_index > index:
            self._active_index -= 1
        self._active_index = min(self._active_index, len(self._panels) - 1)

        self._tab_bar.set_active(self._active_index)
        self._stack.setCurrentIndex(self._active_index)
        self._panels[self._active_index].focus_input()
        self._sidebar.update_cwd(self._panels[self._active_index].cwd_display)
        self._update_title()

    def _switch_tab(self, index: int) -> None:
        if index < 0 or index >= len(self._panels):
            return
        self._active_index = index
        self._tab_bar.set_active(index)
        self._stack.setCurrentIndex(index)
        self._panels[index].focus_input()
        self._sidebar.update_cwd(self._panels[index].cwd_display)
        self._update_title()

    # ── active panel actions ──────────────────────────────────────────────────

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(f"QMainWindow, QWidget {{ background-color: {p.bg}; color: {p.fg}; }}")
        if hasattr(self, "_v_sep"):
            self._v_sep.setStyleSheet(
                f"QFrame {{ color: {p.bg_overlay}; background: {p.bg_overlay}; max-width: 1px; }}"
            )
        if hasattr(self, "_h_sep"):
            self._h_sep.setStyleSheet(
                f"QFrame {{ color: {p.bg_overlay}; background: {p.bg_overlay}; max-height: 1px; }}"
            )

    def _toggle_search(self) -> None:
        if self._panels:
            self._panels[self._active_index].toggle_search()

    def _toggle_collapse_all(self) -> None:
        if self._panels:
            self._panels[self._active_index].toggle_collapse_all()

    def _clear_active(self) -> None:
        if self._panels:
            self._panels[self._active_index].clear_blocks()

    # ── cwd / title ───────────────────────────────────────────────────────────

    def _on_panel_cwd_changed(self, cwd: str, panel: TerminalPanel) -> None:
        if panel in self._panels and self._panels.index(panel) == self._active_index:
            self._sidebar.update_cwd(cwd)
            self._update_title()

    def _update_title(self) -> None:
        if self._panels:
            cwd = self._panels[self._active_index].cwd_display
            self.setWindowTitle(f"Blocksh — {cwd}")

    # ── history ───────────────────────────────────────────────────────────────

    def _load_history(self) -> None:
        blocks = self._repository.load_recent()
        self._sidebar.show_history(blocks)

    def _on_history_command_selected(self, text: str) -> None:
        if self._panels:
            self._panels[self._active_index].set_input_text(text)
            self._panels[self._active_index].focus_input()

    # ── favorites ─────────────────────────────────────────────────────────────

    def _on_favorite_requested(self, name: str, command_text: str, cwd: str) -> None:
        self._favorites_service.add(name, command_text, cwd)

    def _load_favorites(self) -> None:
        favorites = self._favorites_service.all()
        self._sidebar.show_favorites(favorites)

    def _on_favorite_command_selected(self, text: str) -> None:
        if self._panels:
            self._panels[self._active_index].set_input_text(text)
            self._panels[self._active_index].focus_input()

    def _on_favorite_rename(self, fav_id: str, name: str) -> None:
        self._favorites_service.rename(fav_id, name)
        self._load_favorites()

    def _on_favorite_delete(self, fav_id: str) -> None:
        self._favorites_service.remove(fav_id)
        self._load_favorites()
