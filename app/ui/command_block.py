import os
import re
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton,
    QApplication, QMenu, QInputDialog,
)
from PySide6.QtGui import (
    QFont, QFontMetrics,
    QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor,
)
from PySide6.QtCore import Signal, Qt
from ..domain.block import Block
from .theme import Palette, ThemeManager

# Matches ANSI/VT100 escape sequences: CSI (ESC[…), and other single-char ESC sequences
_ANSI_RE = re.compile(r'\x1b(?:\[[0-9;?]*[A-Za-z]|[^[])')


def _clean_output(text: str) -> str:
    """Strip ANSI codes and simulate carriage-return overwrites."""
    text = _ANSI_RE.sub('', text)
    lines = []
    for line in text.split('\n'):
        if '\r' in line:
            segments = line.split('\r')
            buf = list(segments[0])
            for seg in segments[1:]:
                for i, ch in enumerate(seg):
                    if i < len(buf):
                        buf[i] = ch
                    else:
                        buf.append(ch)
            line = ''.join(buf).rstrip()
        lines.append(line)
    return '\n'.join(lines)


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
    return bool(re.search(r"\bls\b[^|;]*-[a-zA-Z]*l", cmd))


def _is_ls(cmd: str) -> bool:
    c = cmd.strip()
    return c == "ls" or c.startswith("ls ") or c.startswith("ls\t")


class _OutputHighlighter(QSyntaxHighlighter):
    def __init__(self, document, command: str, cwd: str, is_stderr: bool):
        super().__init__(document)
        self._cwd        = cwd
        self._is_stderr  = is_stderr
        self._ls_long    = _is_ls_long(command)
        self._ls_plain   = (not self._ls_long) and _is_ls(command)
        self._update_colors()

    def _update_colors(self) -> None:
        p = ThemeManager.instance().current
        self._c_dir     = p.blue
        self._c_symlink = p.cyan
        self._c_exec    = p.green
        self._c_total   = p.fg_dim
        self._c_error   = p.red

    def highlightBlock(self, text: str) -> None:
        self._update_colors()
        if self._is_stderr:
            self._fmt(text, self._c_error)
            return
        if self._ls_long:
            self._highlight_long(text)
        elif self._ls_plain:
            self._highlight_plain(text)

    def _highlight_long(self, text: str) -> None:
        if text.startswith("total "):
            self._fmt(text, self._c_total)
        elif text.startswith("d"):
            self._fmt(text, self._c_dir, bold=True)
        elif text.startswith("l"):
            self._fmt(text, self._c_symlink)
        elif text.startswith("-") and len(text) > 3 and "x" in text[:10]:
            self._fmt(text, self._c_exec)

    def _highlight_plain(self, text: str) -> None:
        entry = text.strip()
        if not entry or not self._cwd:
            return
        full = os.path.join(self._cwd, entry)
        if os.path.islink(full):
            self._fmt(text, self._c_symlink)
        elif os.path.isdir(full):
            self._fmt(text, self._c_dir, bold=True)
        elif os.access(full, os.X_OK) and os.path.isfile(full):
            self._fmt(text, self._c_exec)

    def _fmt(self, text: str, color: str, bold: bool = False) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        self.setFormat(0, len(text), fmt)


class CommandBlock(QWidget):
    remove_requested   = Signal(object)
    favorite_requested = Signal(str, str, str)  # name, command_text, cwd

    def __init__(self, block: Block, parent=None):
        super().__init__(parent)
        self._block = block
        self._expanded = True
        self._output_widget: QPlainTextEdit | None = None
        self._card: QFrame | None = None
        # themed header/footer widgets — stored so apply_theme can reach them
        self._toggle_btn: QPushButton | None = None
        self._cwd_lbl:    QLabel | None      = None
        self._prompt_lbl: QLabel | None      = None
        self._cmd_lbl:    QLabel | None      = None
        self._ts_lbl:     QLabel | None      = None
        self._menu_btn:   QPushButton | None = None
        self._footer:     QWidget | None     = None
        self._stop_btn:   QPushButton | None = None
        self._footer_btns: list[QPushButton] = []
        self._raw_output: str = ""
        self._copy_out_added: bool = False
        self._build_ui()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    @property
    def searchable_text(self) -> str:
        output = self._raw_output or self._block.stdout or self._block.stderr
        return f"{self._block.command.text} {output}".lower()

    def set_search_highlight(self, active: bool) -> None:
        if self._card is None:
            return
        p = ThemeManager.instance().current
        if active:
            self._card.setStyleSheet(
                f"QFrame {{ background-color: {p.bg_highlight}; border-radius: 8px;"
                f" border: 1px solid {p.blue}; }}"
            )
        else:
            self._card.setStyleSheet(
                f"QFrame {{ background-color: {p.bg_surface}; border-radius: 8px; border: none; }}"
            )

    def collapse(self) -> None:
        if self._output_widget:
            self._expanded = False
            self._output_widget.setVisible(False)
            if self._toggle_btn:
                self._toggle_btn.setText("▸")

    def expand(self) -> None:
        if self._output_widget:
            self._expanded = True
            self._output_widget.setVisible(True)
            if self._toggle_btn:
                self._toggle_btn.setText("▾")

    def apply_theme(self, p: Palette) -> None:
        if self._card:
            self._card.setStyleSheet(
                f"QFrame {{ background-color: {p.bg_surface}; border-radius: 8px; border: none; }}"
            )
        if self._output_widget:
            self._output_widget.setStyleSheet(
                f"QPlainTextEdit {{ background: transparent; border: none;"
                f" color: {p.fg}; selection-background-color: {p.bg_overlay}; }}"
            )
        if self._cwd_lbl:
            self._cwd_lbl.setStyleSheet(
                f"color: {p.blue}; font-family: Monospace; font-size: 9pt; background: transparent;"
            )
        if self._prompt_lbl:
            self._prompt_lbl.setStyleSheet(
                f"color: {p.green}; font-family: Monospace; font-size: 10pt;"
                f" font-weight: bold; background: transparent;"
            )
        if self._cmd_lbl:
            self._cmd_lbl.setStyleSheet(f"color: {p.fg}; background: transparent;")
        if self._ts_lbl:
            self._ts_lbl.setStyleSheet(f"color: {p.fg_dim}; font-size: 8pt; background: transparent;")
        if self._menu_btn:
            self._menu_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {p.fg_dim}; border: none; font-size: 13pt; }}"
                f"QPushButton:hover {{ color: {p.fg}; }}"
            )
        btn_style = (
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg_muted}; border-radius: 4px;"
            f" font-size: 8pt; padding: 0 12px; border: none; }}"
            f"QPushButton:hover {{ background: {p.bg_hover2}; color: {p.fg}; }}"
        )
        for btn in self._footer_btns:
            btn.setStyleSheet(btn_style)

    def _build_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        row.addWidget(self._build_card())

    def _build_card(self) -> QFrame:
        p = ThemeManager.instance().current
        card = QFrame()
        self._card = card
        card.setFrameShape(QFrame.NoFrame)
        card.setStyleSheet(
            f"QFrame {{ background-color: {p.bg_surface}; border-radius: 8px; border: none; }}"
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
        p = ThemeManager.instance().current
        header = QWidget()
        header.setStyleSheet("QWidget { background: transparent; }")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        status_color = "#2ecc71" if self._block.exit_code == 0 else "#e74c3c"
        self._toggle_btn = QPushButton("▾")
        self._toggle_btn.setFixedSize(16, 16)
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {status_color}; border: none;"
            f" font-size: 9pt; padding: 0; }}"
            f"QPushButton:hover {{ color: {status_color}; opacity: 0.7; }}"
        )
        self._toggle_btn.clicked.connect(self._toggle_output)
        layout.addWidget(self._toggle_btn)

        cwd_text = _display_cwd(self._block.cwd)
        if cwd_text:
            self._cwd_lbl = QLabel(cwd_text)
            self._cwd_lbl.setStyleSheet(
                f"color: {p.blue}; font-family: Monospace; font-size: 9pt; background: transparent;"
            )
            layout.addWidget(self._cwd_lbl)

        self._prompt_lbl = QLabel("$")
        self._prompt_lbl.setStyleSheet(
            f"color: {p.green}; font-family: Monospace; font-size: 10pt;"
            f" font-weight: bold; background: transparent;"
        )
        layout.addWidget(self._prompt_lbl)

        cmd_font = QFont("Monospace", 10)
        cmd_font.setBold(True)
        self._cmd_lbl = QLabel(self._block.command.text)
        self._cmd_lbl.setFont(cmd_font)
        self._cmd_lbl.setStyleSheet(f"color: {p.fg}; background: transparent;")
        layout.addWidget(self._cmd_lbl)

        layout.addStretch()

        self._ts_lbl = QLabel(self._block.command.created_at.strftime("%H:%M:%S"))
        self._ts_lbl.setStyleSheet(f"color: {p.fg_dim}; font-size: 8pt; background: transparent;")
        layout.addWidget(self._ts_lbl)

        self._menu_btn = QPushButton("⋮")
        self._menu_btn.setFixedSize(22, 22)
        self._menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_dim}; border: none; font-size: 13pt; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._menu_btn.clicked.connect(self._show_menu)
        layout.addWidget(self._menu_btn)

        return header

    def _build_output(self, text: str) -> QPlainTextEdit:
        p = ThemeManager.instance().current
        font = QFont("Monospace", 9)
        out = QPlainTextEdit()
        out.setReadOnly(True)
        out.setFont(font)
        out.document().setDocumentMargin(4)
        out.setPlainText(_clean_output(text).rstrip())
        out.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; border: none;"
            f" color: {p.fg}; selection-background-color: {p.bg_overlay}; }}"
        )
        out.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        out.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        is_stderr = bool(self._block.stderr) and not self._block.stdout
        _OutputHighlighter(
            out.document(),
            self._block.command.text,
            self._block.cwd,
            is_stderr,
        )

        line_h = QFontMetrics(font).lineSpacing()
        content_h = out.document().blockCount() * line_h + 12
        out.setFixedHeight(max(line_h + 12, content_h))

        return out

    def append_output(self, chunk: str) -> None:
        if self._output_widget is None:
            self._output_widget = self._build_output_empty()
            card_layout = self._card.layout()
            card_layout.insertWidget(card_layout.count() - 1, self._output_widget)
            if self._expanded:
                self._output_widget.setVisible(True)
        self._raw_output += chunk
        cleaned = _ANSI_RE.sub('', chunk)
        cursor = self._output_widget.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._output_widget.setTextCursor(cursor)
        self._output_widget.insertPlainText(cleaned)
        self._resize_output()

    def finalize(self, exit_code: int) -> None:
        self._block.exit_code = exit_code
        status_color = "#2ecc71" if exit_code == 0 else "#e74c3c"
        if self._toggle_btn:
            self._toggle_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {status_color}; border: none;"
                f" font-size: 9pt; padding: 0; }}"
                f"QPushButton:hover {{ color: {status_color}; opacity: 0.7; }}"
            )
        if self._output_widget and self._raw_output:
            cleaned = _clean_output(self._raw_output).rstrip()
            self._output_widget.setPlainText(cleaned)
            self._resize_output()
            if self._footer and not self._copy_out_added:
                self._copy_out_added = True
                p = ThemeManager.instance().current
                copy_out = self._make_button("Copy output", p)
                copy_out.clicked.connect(
                    lambda c=cleaned: QApplication.clipboard().setText(c)
                )
                self._footer.layout().addWidget(copy_out)
                self._footer_btns.append(copy_out)
        if self._stop_btn:
            self._stop_btn.setVisible(False)

    def set_stoppable(self, callback) -> None:
        if self._footer is None:
            return
        p = ThemeManager.instance().current
        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.setFixedHeight(24)
        self._stop_btn.setStyleSheet(
            f"QPushButton {{ background: {p.red}; color: {p.bg}; border-radius: 4px;"
            f" font-size: 8pt; padding: 0 12px; border: none; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.red}; color: {p.bg}; }}"
        )
        self._stop_btn.clicked.connect(callback)
        self._footer.layout().addWidget(self._stop_btn)

    def _build_output_empty(self) -> QPlainTextEdit:
        p = ThemeManager.instance().current
        font = QFont("Monospace", 9)
        out = QPlainTextEdit()
        out.setReadOnly(True)
        out.setFont(font)
        out.document().setDocumentMargin(4)
        out.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; border: none;"
            f" color: {p.fg}; selection-background-color: {p.bg_overlay}; }}"
        )
        out.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        out.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        line_h = QFontMetrics(font).lineSpacing()
        out.setFixedHeight(line_h + 12)
        return out

    def _resize_output(self) -> None:
        if self._output_widget is None:
            return
        font = self._output_widget.font()
        line_h = QFontMetrics(font).lineSpacing()
        line_count = self._output_widget.document().blockCount()
        content_h = line_count * line_h + 12
        self._output_widget.setFixedHeight(max(line_h + 12, content_h))

    def _build_footer(self) -> QWidget:
        p = ThemeManager.instance().current
        footer = QWidget()
        self._footer = footer
        footer.setStyleSheet("QWidget { background: transparent; }")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch()

        self._footer_btns.clear()

        copy_cmd = self._make_button("Copy command", p)
        copy_cmd.clicked.connect(
            lambda: QApplication.clipboard().setText(self._block.command.text)
        )
        layout.addWidget(copy_cmd)
        self._footer_btns.append(copy_cmd)

        output = self._block.stdout or self._block.stderr
        if output.strip():
            self._copy_out_added = True
            copy_out = self._make_button("Copy output", p)
            copy_out.clicked.connect(
                lambda: QApplication.clipboard().setText(output.rstrip())
            )
            layout.addWidget(copy_out)
            self._footer_btns.append(copy_out)

        return footer

    def _toggle_output(self):
        if self._output_widget is None:
            return
        self._expanded = not self._expanded
        self._output_widget.setVisible(self._expanded)
        if self._toggle_btn:
            self._toggle_btn.setText("▾" if self._expanded else "▸")

    def _show_menu(self):
        p = ThemeManager.instance().current
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {p.bg_selected}; }}"
        )
        output = self._block.stdout or self._block.stderr
        menu.addAction("Copy command",
                       lambda: QApplication.clipboard().setText(self._block.command.text))
        if output.strip():
            menu.addAction("Copy output",
                           lambda: QApplication.clipboard().setText(output.rstrip()))
        menu.addSeparator()
        menu.addAction("Add to Favorites", self._add_to_favorites)
        menu.addSeparator()
        menu.addAction("Remove block", lambda: self.remove_requested.emit(self))
        menu.exec(self.cursor().pos())

    def _add_to_favorites(self) -> None:
        default = self._block.command.text[:40]
        name, ok = QInputDialog.getText(self, "Add to Favorites", "Name:", text=default)
        if ok and name.strip():
            self.favorite_requested.emit(name.strip(), self._block.command.text, self._block.cwd)

    @staticmethod
    def _make_button(text: str, p: Palette) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(24)
        btn.setStyleSheet(
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg_muted}; border-radius: 4px;"
            f" font-size: 8pt; padding: 0 12px; border: none; }}"
            f"QPushButton:hover {{ background: {p.bg_hover2}; color: {p.fg}; }}"
        )
        return btn
