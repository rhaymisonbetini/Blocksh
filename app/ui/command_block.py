from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPlainTextEdit
from PySide6.QtGui import QFont
from ..domain.block import Block

_FONT_HEADER = QFont("Monospace", 10)
_FONT_OUTPUT = QFont("Monospace", 9)


class CommandBlock(QFrame):
    def __init__(self, block: Block, parent=None):
        super().__init__(parent)
        self._block = block
        self._build_ui()

    def _build_ui(self):
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header_font = QFont("Monospace", 10)
        header_font.setBold(True)
        header = QLabel(f"$ {self._block.command.text}")
        header.setFont(header_font)
        layout.addWidget(header)

        output = self._block.stdout or self._block.stderr
        if output.strip():
            out = QPlainTextEdit()
            out.setReadOnly(True)
            out.setPlainText(output.rstrip())
            out.setFont(_FONT_OUTPUT)
            line_count = output.count("\n") + 1
            out.setFixedHeight(min(300, line_count * 20 + 16))
            layout.addWidget(out)

        accent = "#2ecc71" if self._block.exit_code == 0 else "#e74c3c"
        self.setStyleSheet(
            f"QFrame {{ border-left: 3px solid {accent}; "
            f"background-color: #1e1e2e; border-radius: 4px; }}"
        )
