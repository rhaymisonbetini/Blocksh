import sys
from PySide6.QtWidgets import QApplication
from .ui.main_window import MainWindow
from .ui.theme import Palette, ThemeManager
from .core.command_executor import SubprocessExecutor
from .infra.storage.database import get_connection, initialize_schema
from .infra.storage.history_repository import HistoryRepository


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

    conn = get_connection()
    initialize_schema(conn)
    repository = HistoryRepository(conn)
    executor = SubprocessExecutor()

    window = MainWindow(executor, repository)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
