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
        QMainWindow, QWidget { background-color: #13131f; color: #cdd6f4; }
        QScrollArea { border: none; }
        QLineEdit {
            background-color: #1e1e2e;
            color: #cdd6f4;
            border: 1px solid #313244;
            border-radius: 4px;
            padding: 6px 10px;
            font-family: Monospace;
            font-size: 10pt;
        }
        QLineEdit:focus { border-color: #89b4fa; }
        QPushButton {
            background-color: #89b4fa;
            color: #1e1e2e;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        QPushButton:hover { background-color: #b4befe; }
        QPlainTextEdit {
            background-color: #181825;
            color: #cdd6f4;
            border: none;
            border-radius: 3px;
            font-family: Monospace;
            font-size: 9pt;
        }
        QLabel { color: #cdd6f4; }
        QScrollBar:vertical {
            background: #1e1e2e;
            width: 8px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #45475a;
            border-radius: 4px;
        }
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
