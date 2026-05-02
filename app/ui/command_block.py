from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton,
    QWidget, QApplication,
)
from PySide6.QtGui import QFont
from ..domain.block import Block


class CommandBlock(QFrame):
    def __init__(self, block: Block, parent=None):
        super().__init__(parent)
        self._block = block
        self._expanded = True
        self._output_widget: QPlainTextEdit | None = None
        self._toggle_btn: QPushButton | None = None
        self._build_ui()

    def _build_ui(self):
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        layout.addWidget(self._build_header())

        output = self._block.stdout or self._block.stderr
        if output.strip():
            self._output_widget = self._build_output(output)
            layout.addWidget(self._output_widget)

        accent = "#2ecc71" if self._block.exit_code == 0 else "#e74c3c"
        self.setStyleSheet(
            f"QFrame {{ border-left: 3px solid {accent}; "
            f"background-color: #1e1e2e; border-radius: 4px; }}"
        )

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        cmd_font = QFont("Monospace", 10)
        cmd_font.setBold(True)
        cmd_label = QLabel(f"$ {self._block.command.text}")
        cmd_label.setFont(cmd_font)
        layout.addWidget(cmd_label)

        layout.addStretch()

        # Execution timestamp
        timestamp = self._block.command.created_at.strftime("%H:%M:%S")
        time_label = QLabel(timestamp)
        time_label.setStyleSheet("color: #6c7086; font-size: 8pt;")
        layout.addWidget(time_label)

        # Exit code — green check or red cross with code
        if self._block.exit_code == 0:
            exit_label = QLabel("✓")
            exit_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
        else:
            exit_label = QLabel(f"✗ {self._block.exit_code}")
            exit_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        layout.addWidget(exit_label)

        # Copy command to clipboard
        copy_cmd = self._make_button("copy cmd")
        copy_cmd.clicked.connect(
            lambda: QApplication.clipboard().setText(self._block.command.text)
        )
        layout.addWidget(copy_cmd)

        # Copy output and toggle collapse — only when there is output
        output = self._block.stdout or self._block.stderr
        if output.strip():
            copy_out = self._make_button("copy out")
            copy_out.clicked.connect(
                lambda: QApplication.clipboard().setText(output.rstrip())
            )
            layout.addWidget(copy_out)

            self._toggle_btn = self._make_button("▼")
            self._toggle_btn.setFixedWidth(28)
            self._toggle_btn.clicked.connect(self._toggle_output)
            layout.addWidget(self._toggle_btn)

        return header

    def _build_output(self, text: str) -> QPlainTextEdit:
        out = QPlainTextEdit()
        out.setReadOnly(True)
        out.setPlainText(text.rstrip())
        out.setFont(QFont("Monospace", 9))
        line_count = text.count("\n") + 1
        out.setFixedHeight(min(300, line_count * 20 + 16))
        return out

    def _toggle_output(self):
        if self._output_widget is None or self._toggle_btn is None:
            return
        self._expanded = not self._expanded
        self._output_widget.setVisible(self._expanded)
        self._toggle_btn.setText("▼" if self._expanded else "▶")

    @staticmethod
    def _make_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(22)
        btn.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; border-radius: 3px;"
            " font-size: 8pt; padding: 0 6px; border: none; }"
            "QPushButton:hover { background: #45475a; }"
        )
        return btn
