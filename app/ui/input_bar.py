from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Signal


class InputBar(QWidget):
    command_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("$ type a command...")
        self._input.returnPressed.connect(self._submit)

        self._btn = QPushButton("Run")
        self._btn.setFixedWidth(64)
        self._btn.clicked.connect(self._submit)

        layout.addWidget(self._input)
        layout.addWidget(self._btn)

    def _submit(self):
        text = self._input.text().strip()
        if text:
            self.command_submitted.emit(text)
            self._input.clear()

    def focus(self):
        self._input.setFocus()
