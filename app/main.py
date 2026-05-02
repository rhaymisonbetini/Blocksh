import sys
from PySide6.QtWidgets import QApplication
from .ui.main_window import MainWindow
from .core.command_executor import SubprocessExecutor
from .core.shell_session import ShellSession
from .domain.command import Command
from .services.history_service import HistoryService
from .infra.storage.database import get_connection, initialize_schema
from .infra.storage.history_repository import HistoryRepository


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QMainWindow, QWidget { background-color: #0d0f1a; color: #cdd6f4; }
        QScrollArea  { border: none; background: transparent; }
        QScrollBar:vertical {
            background: #0d0f1a;
            width: 6px;
            border-radius: 3px;
        }
        QScrollBar::handle:vertical {
            background: #1e2235;
            border-radius: 3px;
            min-height: 24px;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical { height: 0; }
        QLabel       { color: #cdd6f4; background: transparent; }
        QPlainTextEdit {
            background: transparent;
            color: #cdd6f4;
            border: none;
            font-family: Monospace;
            font-size: 9pt;
        }
        QMenu {
            background: #1e2235;
            color: #cdd6f4;
            border: 1px solid #313244;
            border-radius: 6px;
        }
        QMenu::item:selected { background: #2a3f6e; }
    """)

    # Infrastructure
    conn = get_connection()
    initialize_schema(conn)
    repository = HistoryRepository(conn)

    # Core
    executor = SubprocessExecutor()
    session = ShellSession()
    history = HistoryService(repository)

    # UI
    window = MainWindow()
    window.update_cwd(session.cwd_display())

    def on_command(text: str):
        # Update cwd tracker before executing (handles `cd` built-in)
        session.try_cd(text)

        command = Command(text=text)
        block = executor.execute(command, cwd=session.cwd, env=session.env)

        history.add(block)
        window.add_block(block)
        window.update_input_history(history.commands())
        window.update_cwd(session.cwd_display())

    window.command_submitted.connect(on_command)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
