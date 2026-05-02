from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Signal, Qt


class _HistoryInput(QLineEdit):
    """QLineEdit that emits signals on Up/Down arrow keys for history navigation."""

    go_previous = Signal()
    go_next = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.go_previous.emit()
        elif event.key() == Qt.Key_Down:
            self.go_next.emit()
        else:
            super().keyPressEvent(event)


class InputBar(QWidget):
    command_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._history_index: int = -1  # -1 means not navigating (current draft)
        self._draft: str = ""          # preserves typed text while navigating
        self.setFixedHeight(60)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("QWidget { background-color: #0d0f1a; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        # Placeholder attach button for future use
        attach_btn = QPushButton("⊕")
        attach_btn.setFixedSize(36, 36)
        attach_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #45475a; border: none;"
            " font-size: 16pt; }"
            "QPushButton:hover { color: #6c7086; }"
        )

        self._input = _HistoryInput()
        self._input.setPlaceholderText("Digite um comando...")
        self._input.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #cdd6f4;"
            " font-family: Monospace; font-size: 10pt; }"
            "QLineEdit::placeholder { color: #45475a; }"
        )
        self._input.returnPressed.connect(self._submit)
        self._input.go_previous.connect(self._navigate_previous)
        self._input.go_next.connect(self._navigate_next)

        run_btn = QPushButton("▶  Run")
        run_btn.setFixedHeight(36)
        run_btn.setMinimumWidth(88)
        run_btn.setStyleSheet(
            "QPushButton { background: #2ecc71; color: #0d0f1a; border: none;"
            " border-radius: 6px; font-weight: bold; font-size: 10pt;"
            " padding: 0 18px; }"
            "QPushButton:hover { background: #27ae60; }"
            "QPushButton:pressed { background: #1e8449; }"
        )
        run_btn.clicked.connect(self._submit)

        layout.addWidget(attach_btn)
        layout.addWidget(self._input)
        layout.addWidget(run_btn)

    def _submit(self):
        text = self._input.text().strip()
        if text:
            self._history_index = -1
            self.command_submitted.emit(text)
            self._input.clear()

    def _navigate_previous(self):
        """Move to an older command in history (Up arrow)."""
        if not self._history:
            return
        if self._history_index == -1:
            self._draft = self._input.text()
            self._history_index = len(self._history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self._input.setText(self._history[self._history_index])

    def _navigate_next(self):
        """Move to a newer command or restore draft (Down arrow)."""
        if self._history_index == -1:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._input.setText(self._history[self._history_index])
        else:
            self._history_index = -1
            self._input.setText(self._draft)

    def update_history(self, commands: list[str]) -> None:
        self._history = commands

    def update_cwd(self, display_path: str) -> None:
        pass  # cwd is displayed in the sidebar on this layout

    def focus(self):
        self._input.setFocus()
