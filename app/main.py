import sys
from PySide6.QtWidgets import QApplication
from .ui.main_window import MainWindow
from .ui.theme import Palette, ThemeManager
from .core.command_executor import SubprocessExecutor
from .infra.storage.database import get_connection, initialize_schema
from .infra.storage.history_repository import HistoryRepository
from .infra.storage.favorites_repository import FavoritesRepository
from .services.favorites_service import FavoritesService
from .infra.storage.project_repository import ProjectRepository
from .services.project_service import ProjectService
from .services.settings_service import SettingsService
from .infra.storage.ssh_repository import SshRepository
from .services.ssh_service import SshService
from .infra.storage.workflow_repository import WorkflowRepository
from .services.workflow_service import WorkflowService


def _build_global_qss(p: Palette) -> str:
    return f"""
        QMainWindow, QWidget {{ background-color: {p.bg}; color: {p.fg}; }}
        QScrollArea  {{ border: none; background: transparent; }}
        QScrollBar:vertical {{
            background: {p.bg};
            width: 6px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.bg_overlay};
            border-radius: 3px;
            min-height: 24px;
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{ height: 0; }}
        QLabel       {{ color: {p.fg}; background: transparent; }}
        QPlainTextEdit {{
            background: transparent;
            color: {p.fg};
            border: none;
            font-family: Monospace;
            font-size: 9pt;
        }}
        QMenu {{
            background: {p.bg_overlay};
            color: {p.fg};
            border: 1px solid {p.border};
            border-radius: 6px;
        }}
        QMenu::item:selected {{ background: {p.bg_selected}; }}
    """


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    ThemeManager.instance()   # init singleton, loads persisted preference

    def _apply_global(p: Palette) -> None:
        app.setStyleSheet(_build_global_qss(p))

    ThemeManager.instance().theme_changed.connect(_apply_global)
    _apply_global(ThemeManager.instance().current)

    SettingsService.instance()   # init singleton before any widget loads

    conn = get_connection()
    initialize_schema(conn)
    repository         = HistoryRepository(conn)
    favorites_repo     = FavoritesRepository(conn)
    favorites_service  = FavoritesService(favorites_repo)
    project_repo       = ProjectRepository(conn)
    project_service    = ProjectService(project_repo)
    ssh_repo           = SshRepository(conn)
    ssh_service        = SshService(ssh_repo)
    workflow_repo      = WorkflowRepository(conn)
    workflow_service   = WorkflowService(workflow_repo)
    executor           = SubprocessExecutor()

    _s = SettingsService.instance().get()
    if _s.history_retention_days > 0:
        repository.clear_older_than(_s.history_retention_days)

    window = MainWindow(executor, repository, favorites_service, project_service,
                        favorites_repo=favorites_repo, project_repo=project_repo,
                        ssh_service=ssh_service, workflow_service=workflow_service)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
