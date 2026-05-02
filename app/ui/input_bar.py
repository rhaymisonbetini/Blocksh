from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel
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
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)

        self._cwd_label = QLabel("~")
        self._cwd_label.setStyleSheet(
            "color: #89b4fa; font-family: Monospace; font-size: 10pt;"
            " padding-right: 4px;"
        )

        self._prompt_label = QLabel("$")
        self._prompt_label.setStyleSheet(
            "color: #a6e3a1; font-family: Monospace; font-size: 10pt;"
            " font-weight: bold; padding-left: 4px; padding-right: 8px;"
        )

        self._input = _HistoryInput()
        self._input.setPlaceholderText("type a command...")
        self._input.returnPressed.connect(self._submit)
        self._input.go_previous.connect(self._navigate_previous)
        self._input.go_next.connect(self._navigate_next)

        self._btn = QPushButton("Run")
        self._btn.setFixedWidth(64)
        self._btn.clicked.connect(self._submit)

        layout.addWidget(self._cwd_label)
        layout.addWidget(self._prompt_label)
        layout.addWidget(self._input)
        layout.addSpacing(8)
        layout.addWidget(self._btn)

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
        self._cwd_label.setText(display_path)

    def focus(self):
        self._input.setFocus()
