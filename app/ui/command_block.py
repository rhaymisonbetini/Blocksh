import os
import re
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton,
    QApplication, QMenu,
)
from PySide6.QtGui import (
    QFont, QFontMetrics,
    QSyntaxHighlighter, QTextCharFormat, QColor,
)
from PySide6.QtCore import Signal, Qt
from ..domain.block import Block

# ── Colour palette for output highlighting ────────────────────────────────────
_C_DIR      = "#89b4fa"   # blue  — directories
_C_SYMLINK  = "#94e2d5"   # cyan  — symlinks
_C_EXEC     = "#a6e3a1"   # green — executables
_C_TOTAL    = "#45475a"   # grey  — "total N" header line
_C_ERROR    = "#f38ba8"   # red   — stderr output
# ─────────────────────────────────────────────────────────────────────────────


def _display_cwd(cwd: str) -> str:
    if not cwd:
        return ""
    home = str(Path.home())
    if cwd == home:
        return "~"
    if cwd.startswith(home + "/"):
        return "~" + cwd[len(home):]
    return cwd


def _is_ls_long(cmd: str) -> bool:
    """True when the command is any ls variant with the -l flag."""
    return bool(re.search(r"\bls\b[^|;]*-[a-zA-Z]*l", cmd))


def _is_ls(cmd: str) -> bool:
    """True for any ls invocation."""
    c = cmd.strip()
    return c == "ls" or c.startswith("ls ") or c.startswith("ls\t")


class _OutputHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter for command output.

    Strategies:
      • ls -l / ls -la  → permission string first char (d/l/-) decides colour
      • ls (plain)      → os.path.isdir/islink against block.cwd for each entry
      • stderr output   → entire block coloured as error
    """

    def __init__(self, document, command: str, cwd: str, is_stderr: bool):
        super().__init__(document)
        self._cwd        = cwd
        self._is_stderr  = is_stderr
        self._ls_long    = _is_ls_long(command)
        self._ls_plain   = (not self._ls_long) and _is_ls(command)

    def highlightBlock(self, text: str) -> None:
        if self._is_stderr:
            self._fmt(text, _C_ERROR)
            return

        if self._ls_long:
            self._highlight_long(text)
        elif self._ls_plain:
            self._highlight_plain(text)

    def _highlight_long(self, text: str) -> None:
        """Colour based on the permission-string first character."""
        if text.startswith("total "):
            self._fmt(text, _C_TOTAL)
        elif text.startswith("d"):
            self._fmt(text, _C_DIR, bold=True)
        elif text.startswith("l"):
            self._fmt(text, _C_SYMLINK)
        elif text.startswith("-") and len(text) > 3 and "x" in text[:10]:
            self._fmt(text, _C_EXEC)

    def _highlight_plain(self, text: str) -> None:
        """Check each entry against the filesystem using block.cwd."""
        entry = text.strip()
        if not entry or not self._cwd:
            return
        full = os.path.join(self._cwd, entry)
        if os.path.islink(full):
            self._fmt(text, _C_SYMLINK)
        elif os.path.isdir(full):
            self._fmt(text, _C_DIR, bold=True)
        elif os.access(full, os.X_OK) and os.path.isfile(full):
            self._fmt(text, _C_EXEC)

    def _fmt(self, text: str, color: str, bold: bool = False) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        self.setFormat(0, len(text), fmt)


class CommandBlock(QWidget):
    remove_requested = Signal(object)

    def __init__(self, block: Block, parent=None):
        super().__init__(parent)
        self._block = block
        self._expanded = True
        self._output_widget: QPlainTextEdit | None = None
        self._card: QFrame | None = None
        self._build_ui()

    @property
    def searchable_text(self) -> str:
        output = self._block.stdout or self._block.stderr
        return f"{self._block.command.text} {output}".lower()

    def set_search_highlight(self, active: bool) -> None:
        if self._card is None:
            return
        if active:
            self._card.setStyleSheet(
                "QFrame { background-color: #1e2a3a; border-radius: 8px;"
                " border: 1px solid #89b4fa; }"
            )
        else:
            self._card.setStyleSheet(
                "QFrame { background-color: #161926; border-radius: 8px; border: none; }"
            )

    def _build_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        row.addWidget(self._build_status_circle(), alignment=Qt.AlignTop | Qt.AlignHCenter)
        row.addWidget(self._build_card())

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
        self._card = card  # keep reference for search highlighting
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

        cwd_text = _display_cwd(self._block.cwd)
        if cwd_text:
            cwd_lbl = QLabel(cwd_text)
            cwd_lbl.setStyleSheet(
                "color: #89b4fa; font-family: Monospace; font-size: 9pt; background: transparent;"
            )
            layout.addWidget(cwd_lbl)

        prompt = QLabel("$")
        prompt.setStyleSheet(
            "color: #a6e3a1; font-family: Monospace; font-size: 10pt;"
            " font-weight: bold; background: transparent;"
        )
        layout.addWidget(prompt)

        cmd_font = QFont("Monospace", 10)
        cmd_font.setBold(True)
        cmd_lbl = QLabel(self._block.command.text)
        cmd_lbl.setFont(cmd_font)
        cmd_lbl.setStyleSheet("color: #cdd6f4; background: transparent;")
        layout.addWidget(cmd_lbl)

        layout.addStretch()

        ts_lbl = QLabel(self._block.command.created_at.strftime("%H:%M:%S"))
        ts_lbl.setStyleSheet("color: #45475a; font-size: 8pt; background: transparent;")
        layout.addWidget(ts_lbl)

        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(22, 22)
        menu_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #45475a; border: none; font-size: 13pt; }"
            "QPushButton:hover { color: #cdd6f4; }"
        )
        menu_btn.clicked.connect(self._show_menu)
        layout.addWidget(menu_btn)

        return header

    def _build_output(self, text: str) -> QPlainTextEdit:
        font = QFont("Monospace", 9)
        out = QPlainTextEdit()
        out.setReadOnly(True)
        out.setFont(font)
        out.document().setDocumentMargin(4)
        out.setPlainText(text.rstrip())
        out.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none;"
            " color: #cdd6f4; selection-background-color: #313244; }"
        )
        out.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        out.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Attach highlighter (ls directory/file colouring, stderr error colouring)
        is_stderr = bool(self._block.stderr) and not self._block.stdout
        _OutputHighlighter(
            out.document(),
            self._block.command.text,
            self._block.cwd,
            is_stderr,
        )

        # Height: fit content exactly, capped at 300px
        line_h = QFontMetrics(font).lineSpacing()
        line_count = text.rstrip().count("\n") + 1
        # document margin (4px * 2) + 4px breathing room
        content_h = line_count * line_h + 12
        out.setFixedHeight(min(300, max(line_h + 12, content_h)))

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
