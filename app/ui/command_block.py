from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton,
    QApplication, QMenu,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Signal, Qt
from ..domain.block import Block


def _display_cwd(cwd: str) -> str:
    if not cwd:
        return ""
    home = str(Path.home())
    if cwd == home:
        return "~"
    if cwd.startswith(home + "/"):
        return "~" + cwd[len(home):]
    return cwd


class CommandBlock(QWidget):
    remove_requested = Signal(object)

    def __init__(self, block: Block, parent=None):
        super().__init__(parent)
        self._block = block
        self._expanded = True
        self._output_widget: QPlainTextEdit | None = None
        self._build_ui()

    def _build_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        row.addWidget(self._build_status_circle(), alignment=Qt.AlignTop | Qt.AlignHCenter)

        card = self._build_card()
        row.addWidget(card)

    def _build_status_circle(self) -> QPushButton:
        color = "#2ecc71" if self._block.exit_code == 0 else "#e74c3c"
        btn = QPushButton("▶")
        btn.setFixedSize(28, 28)
        btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: #0d0f1a; border: none;"
            f" border-radius: 14px; font-size: 8pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {color}cc; }}"
        )
        btn.clicked.connect(self._toggle_output)
        return btn

    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.NoFrame)
        card.setStyleSheet(
            "QFrame { background-color: #161926; border-radius: 8px; border: none; }"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        layout.addWidget(self._build_header())

        output = self._block.stdout or self._block.stderr
        if output.strip():
            self._output_widget = self._build_output(output)
            layout.addWidget(self._output_widget)

        layout.addWidget(self._build_footer())
        return card

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("QWidget { background: transparent; }")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # cwd label
        cwd_text = _display_cwd(self._block.cwd)
        if cwd_text:
            cwd_lbl = QLabel(cwd_text)
            cwd_lbl.setStyleSheet(
                "color: #89b4fa; font-family: Monospace; font-size: 9pt;"
                " background: transparent;"
            )
            layout.addWidget(cwd_lbl)

        # prompt symbol
        prompt = QLabel("$")
        prompt.setStyleSheet(
            "color: #a6e3a1; font-family: Monospace; font-size: 10pt;"
            " font-weight: bold; background: transparent;"
        )
        layout.addWidget(prompt)

        # command text
        cmd_font = QFont("Monospace", 10)
        cmd_font.setBold(True)
        cmd_lbl = QLabel(self._block.command.text)
        cmd_lbl.setFont(cmd_font)
        cmd_lbl.setStyleSheet("color: #cdd6f4; background: transparent;")
        layout.addWidget(cmd_lbl)

        layout.addStretch()

        # timestamp
        ts = self._block.command.created_at.strftime("%H:%M:%S")
        ts_lbl = QLabel(ts)
        ts_lbl.setStyleSheet("color: #45475a; font-size: 8pt; background: transparent;")
        layout.addWidget(ts_lbl)

        # three-dot context menu
        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(22, 22)
        menu_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #45475a; border: none;"
            " font-size: 13pt; }"
            "QPushButton:hover { color: #cdd6f4; }"
        )
        menu_btn.clicked.connect(self._show_menu)
        layout.addWidget(menu_btn)

        return header

    def _build_output(self, text: str) -> QPlainTextEdit:
        out = QPlainTextEdit()
        out.setReadOnly(True)
        out.setPlainText(text.rstrip())
        out.setFont(QFont("Monospace", 9))
        out.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none;"
            " color: #cdd6f4; selection-background-color: #313244; }"
        )
        line_count = text.count("\n") + 1
        out.setFixedHeight(min(300, line_count * 20 + 16))
        return out

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet("QWidget { background: transparent; }")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch()

        copy_cmd = self._make_button("Copiar comando")
        copy_cmd.clicked.connect(
            lambda: QApplication.clipboard().setText(self._block.command.text)
        )
        layout.addWidget(copy_cmd)

        output = self._block.stdout or self._block.stderr
        if output.strip():
            copy_out = self._make_button("Copiar saída")
            copy_out.clicked.connect(
                lambda: QApplication.clipboard().setText(output.rstrip())
            )
            layout.addWidget(copy_out)

        return footer

    def _toggle_output(self):
        if self._output_widget is None:
            return
        self._expanded = not self._expanded
        self._output_widget.setVisible(self._expanded)

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e2235; color: #cdd6f4; border: 1px solid #313244;"
            " border-radius: 6px; padding: 4px; }"
            "QMenu::item { padding: 6px 16px; border-radius: 4px; }"
            "QMenu::item:selected { background: #2a3f6e; }"
        )
        output = self._block.stdout or self._block.stderr

        menu.addAction("Copiar comando",
                       lambda: QApplication.clipboard().setText(self._block.command.text))
        if output.strip():
            menu.addAction("Copiar saída",
                           lambda: QApplication.clipboard().setText(output.rstrip()))
        menu.addSeparator()
        menu.addAction("Remover bloco", lambda: self.remove_requested.emit(self))

        menu.exec(self.cursor().pos())

    @staticmethod
    def _make_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(24)
        btn.setStyleSheet(
            "QPushButton { background: #1e2235; color: #6c7086; border-radius: 4px;"
            " font-size: 8pt; padding: 0 12px; border: none; }"
            "QPushButton:hover { background: #252840; color: #cdd6f4; }"
        )
        return btn
