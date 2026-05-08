from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QFrame, QLabel, QPushButton, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from .sidebar import Sidebar
from .tab_bar import TabBar
from .terminal_panel import TerminalPanel
from .theme import Palette, ThemeManager
from .settings_panel import SettingsPanel
from ..core.command_executor import BaseExecutor
from ..infra.storage.history_repository import HistoryRepository
from ..services.favorites_service import FavoritesService
from ..services.project_service import ProjectService


class MainWindow(QMainWindow):
    def __init__(
        self,
        executor: BaseExecutor,
        repository: HistoryRepository,
        favorites_service: FavoritesService,
        project_service: ProjectService,
        favorites_repo=None,
        project_repo=None,
    ):
        super().__init__()
        self._executor           = executor
        self._repository         = repository
        self._favorites_service  = favorites_service
        self._project_service    = project_service
        self._favorites_repo     = favorites_repo
        self._project_repo       = project_repo
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
        self._sidebar.settings_requested.connect(self._open_settings)
        self._sidebar.terminal_requested.connect(self._close_settings)
        self._sidebar.history_open_requested.connect(self._load_history)
        self._sidebar.command_selected.connect(self._on_history_command_selected)
        self._sidebar.theme_selected.connect(lambda name: ThemeManager.instance().set_theme(name))
        self._sidebar.favorites_open_requested.connect(self._load_favorites)
        self._sidebar.favorite_command_selected.connect(self._on_favorite_command_selected)
        self._sidebar.favorite_rename_requested.connect(self._on_favorite_rename)
        self._sidebar.favorite_delete_requested.connect(self._on_favorite_delete)
        self._sidebar.projects_open_requested.connect(self._load_projects)
        self._sidebar.project_selected.connect(self._on_project_selected)
        self._sidebar.project_add_requested.connect(self._on_project_add)
        self._sidebar.project_rename_requested.connect(self._on_project_rename)
        self._sidebar.project_delete_requested.connect(self._on_project_delete)
        root.addWidget(self._sidebar)

        self._v_sep = QFrame()
        self._v_sep.setFrameShape(QFrame.VLine)
        root.addWidget(self._v_sep)

        # ── right side: QStackedWidget with terminal view (0) + settings (1) ──
        self._right_stack = QStackedWidget()

        # Page 0 — terminal view
        terminal_view = QWidget()
        tv_layout = QVBoxLayout(terminal_view)
        tv_layout.setContentsMargins(0, 0, 0, 0)
        tv_layout.setSpacing(0)

        self._tab_bar = TabBar()
        self._tab_bar.tab_add_requested.connect(self._add_tab)
        self._tab_bar.tab_close_requested.connect(self._close_tab)
        self._tab_bar.tab_switched.connect(self._switch_tab)
        self._tab_bar.search_requested.connect(self._toggle_search)
        self._tab_bar.collapse_all_requested.connect(self._toggle_collapse_all)
        self._tab_bar.settings_requested.connect(self._open_settings)
        tv_layout.addWidget(self._tab_bar)

        self._h_sep = QFrame()
        self._h_sep.setFrameShape(QFrame.HLine)
        tv_layout.addWidget(self._h_sep)

        self._stack = QStackedWidget()
        tv_layout.addWidget(self._stack)

        self._right_stack.addWidget(terminal_view)   # index 0

        # Page 1 — settings full-width view
        self._right_stack.addWidget(self._build_settings_view())  # index 1

        root.addWidget(self._right_stack, 1)

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    def _build_settings_view(self) -> QWidget:
        p = ThemeManager.instance().current
        page = QWidget()
        page.setStyleSheet(f"QWidget {{ background-color: {p.bg}; }}")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # header bar
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(
            f"QWidget {{ background-color: {p.bg_panel}; border-bottom: 1px solid {p.border}; }}"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)
        h_layout.setSpacing(12)

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(30)
        back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none;"
            f" font-size: 9pt; padding: 0 8px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        back_btn.clicked.connect(self._close_settings)

        title_lbl = QLabel("⚙  Settings")
        title_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: 11pt; font-weight: bold; background: transparent;"
        )

        h_layout.addWidget(back_btn)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        layout.addWidget(header)

        # settings content in a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        conn = self._repository._conn if hasattr(self._repository, "_conn") else None
        self._settings_panel = SettingsPanel(
            repository=self._repository,
            favorites_repo=self._favorites_repo,
            project_repo=self._project_repo,
            conn=conn,
        )
        self._settings_panel.data_cleared.connect(self._on_data_cleared)

        scroll.setWidget(self._settings_panel)
        layout.addWidget(scroll, 1)

        self._settings_header = header
        self._settings_back_btn = back_btn
        self._settings_title_lbl = title_lbl

        return page

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._add_tab)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(
            lambda: self._close_tab(self._active_index)
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._toggle_search)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._clear_active)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._esc_settings)

    # ── settings navigation ───────────────────────────────────────────────────

    def _open_settings(self) -> None:
        self._right_stack.setCurrentIndex(1)

    def _close_settings(self) -> None:
        self._right_stack.setCurrentIndex(0)
        if self._panels:
            self._panels[self._active_index].focus_input()

    def _esc_settings(self) -> None:
        if self._right_stack.currentIndex() == 1:
            self._close_settings()

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

    # ── theme ─────────────────────────────────────────────────────────────────

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
        if hasattr(self, "_settings_header"):
            self._settings_header.setStyleSheet(
                f"QWidget {{ background-color: {p.bg_panel};"
                f" border-bottom: 1px solid {p.border}; }}"
            )
            self._settings_back_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none;"
                f" font-size: 9pt; padding: 0 8px; }}"
                f"QPushButton:hover {{ color: {p.fg}; }}"
            )
            self._settings_title_lbl.setStyleSheet(
                f"color: {p.fg}; font-size: 11pt; font-weight: bold; background: transparent;"
            )

    # ── panel actions ─────────────────────────────────────────────────────────

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
        if cwd:
            self._project_service.auto_register(cwd)

    def _update_title(self) -> None:
        if self._panels:
            cwd = self._panels[self._active_index].cwd_display
            self.setWindowTitle(f"Blocksh — {cwd}")

    # ── history ───────────────────────────────────────────────────────────────

    def _on_data_cleared(self) -> None:
        self._load_history()
        self._load_favorites()
        self._load_projects()

    def _load_history(self) -> None:
        from ..services.settings_service import SettingsService
        limit = SettingsService.instance().get().history_limit
        blocks = self._repository.load_recent(limit=limit)
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

    # ── projects ──────────────────────────────────────────────────────────────

    def _load_projects(self) -> None:
        projects = self._project_service.all()
        with_history = [
            (p, self._project_service.history_for(p, self._repository))
            for p in projects
        ]
        self._sidebar.show_projects(with_history)

    def _on_project_selected(self, path: str) -> None:
        if self._panels:
            self._panels[self._active_index].set_input_text(f"cd {path}")
            self._panels[self._active_index].focus_input()
        self._project_service.touch(path)

    def _on_project_add(self) -> None:
        if not self._panels:
            return
        from PySide6.QtWidgets import QInputDialog
        cwd = self._panels[self._active_index]._session.cwd
        name, ok = QInputDialog.getText(
            self, "Add Project", "Project name:", text=cwd.split("/")[-1] or cwd
        )
        if ok and name.strip():
            self._project_service.register(cwd, name.strip())
            self._load_projects()

    def _on_project_rename(self, project_id: str, name: str) -> None:
        self._project_service.rename(project_id, name)
        self._load_projects()

    def _on_project_delete(self, project_id: str) -> None:
        self._project_service.remove(project_id)
        self._load_projects()
