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
from .ansi_renderer import render_ansi, render_ansi_with_links
from .clickable_output import ClickableOutput
from PySide6.QtCore import Signal, Qt, QSize, QTimer
from ..domain.block import Block
from .theme import Palette, ThemeManager
from ..services.settings_service import SettingsService

# Matches ANSI/VT100 escape sequences: CSI (ESC[…), and other single-char ESC sequences
_ANSI_RE = re.compile(r'\x1b(?:\[[0-9;?]*[A-Za-z]|[^[])')

_QWIDGETSIZE_MAX = 16_777_215


class _OutputEdit(ClickableOutput):
    """ClickableOutput whose sizeHint reflects the height set via setFixedHeight.

    QTextEdit.sizeHint() returns a fixed ~192 px regardless of content.
    When that large hint is used by the parent VBoxLayout to allocate space,
    the card receives far more height than the output needs. The widget itself
    can't fill it (setFixedHeight prevents growth), so the surplus shows up as
    blank gaps above/between elements. Overriding sizeHint to report the actual
    constrained height fixes the allocation.
    """

    def sizeHint(self) -> QSize:
        max_h = self.maximumHeight()
        if max_h < _QWIDGETSIZE_MAX:
            return QSize(super().sizeHint().width(), max_h)
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


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


def _process_cr_ansi(text: str) -> str:
    """Process \\r overwrites while preserving ANSI escape codes (for colored display)."""
    lines = []
    for line in text.split("\n"):
        if "\r" not in line:
            lines.append(line)
            continue
        parts = line.split("\r")
        lines.append(parts[-1] if parts[-1] else (parts[-2] if len(parts) > 1 else ""))
    return "\n".join(lines)


def _insert_ansi_text(cursor: QTextCursor, text: str) -> None:
    for segment, fmt in render_ansi_with_links(text):
        cursor.insertText(segment, fmt)


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
    fix_requested      = Signal(str, str, str)  # command_text, stderr, cwd

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
        self._explain_btn: QPushButton | None = None
        self._fix_btn:     QPushButton | None = None
        self._menu_btn:   QPushButton | None = None
        self._explanation_panel: QFrame | None = None
        self._explanation_label: QLabel | None = None
        self._workers: list = []
        self._raw_output: str = ""
        self._resize_pending: bool = False
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

    def _sync_height(self) -> None:
        """Pin card and CommandBlock to the exact pixel height their content needs.

        QPlainTextEdit.sizeHint() returns ~192 px regardless of content. Even with
        _OutputEdit overriding sizeHint, updateGeometry() propagation can be deferred,
        so the first layout pass may still over-allocate. Calling setFixedHeight on
        both the card and this widget after every size change removes the ambiguity:
        the parent blocks_layout is forced to give exactly what is needed.
        """
        if self._card is None:
            return
        h = self._card.layout().sizeHint().height()
        self._card.setFixedHeight(h)
        self.setFixedHeight(h)

    def collapse(self) -> None:
        if self._output_widget:
            self._expanded = False
            self._output_widget.setVisible(False)
            if self._toggle_btn:
                self._toggle_btn.setText("▸")
            self._sync_height()

    def expand(self) -> None:
        if self._output_widget:
            self._expanded = True
            self._output_widget.setVisible(True)
            if self._toggle_btn:
                self._toggle_btn.setText("▾")
            self._sync_height()

    def apply_theme(self, p: Palette) -> None:
        if self._card:
            self._card.setStyleSheet(
                f"QFrame {{ background-color: {p.bg_surface}; border-radius: 8px; border: none; }}"
            )
        if self._output_widget:
            self._output_widget.setStyleSheet(
                f"QTextEdit {{ background: transparent; border: none;"
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
        if self._explain_btn:
            self._explain_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {p.blue}; border: none;"
                f" font-size: 9pt; padding: 0 2px; }}"
                f"QPushButton:hover {{ color: {p.fg}; }}"
            )
        if self._fix_btn:
            self._fix_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {p.red}; border: 1px solid {p.red};"
                f" border-radius: 3px; font-size: 8pt; padding: 0 5px; }}"
                f"QPushButton:hover {{ background: {p.red}; color: {p.bg}; }}"
            )
        if self._explanation_panel:
            self._explanation_panel.setStyleSheet(
                f"QFrame {{ background: {p.bg_overlay}; border-radius: 4px; border: none; }}"
            )
            if self._explanation_label:
                _fs = SettingsService.instance().get().font_size_output or 11
                self._explanation_label.setStyleSheet(
                    f"QTextEdit {{ background: transparent; border: none;"
                    f" color: {p.fg}; font-size: {_fs}pt; }}"
                )

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
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)

        layout.addWidget(self._build_header())

        output = self._block.stdout or self._block.stderr
        if output.strip():
            self._output_widget = self._build_output(output)
            layout.addWidget(self._output_widget)

        self._sync_height()
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

        self._explain_btn = QPushButton("?")
        self._explain_btn.setFixedSize(22, 22)
        self._explain_btn.setToolTip("Explain with AI")
        self._explain_btn.setVisible(False)
        self._explain_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.blue}; border: none;"
            f" font-size: 9pt; padding: 0 2px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._explain_btn.clicked.connect(self._on_explain_clicked)
        layout.addWidget(self._explain_btn)

        self._fix_btn = QPushButton("Fix ↗")
        self._fix_btn.setFixedHeight(22)
        self._fix_btn.setToolTip("Fix this command with AI")
        self._fix_btn.setVisible(False)
        self._fix_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.red}; border: 1px solid {p.red};"
            f" border-radius: 3px; font-size: 8pt; padding: 0 5px; }}"
            f"QPushButton:hover {{ background: {p.red}; color: {p.bg}; }}"
        )
        self._fix_btn.clicked.connect(self._on_fix_clicked)
        layout.addWidget(self._fix_btn)

        self._menu_btn = QPushButton("⋮")
        self._menu_btn.setFixedSize(22, 22)
        self._menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_dim}; border: none; font-size: 13pt; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._menu_btn.clicked.connect(self._show_menu)
        layout.addWidget(self._menu_btn)

        return header

    def _build_output(self, text: str) -> _OutputEdit:
        p = ThemeManager.instance().current
        _s = SettingsService.instance().get()
        font = QFont(_s.font_family or "Monospace", _s.font_size_output or 11)
        out = _OutputEdit()
        out.setReadOnly(True)
        out.setFont(font)
        out.setFrameShape(QFrame.NoFrame)
        out.document().setDocumentMargin(0)
        out.setContentsMargins(0, 0, 0, 0)
        fg_color = _s.output_fg_override or p.fg
        out.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none;"
            f" color: {fg_color}; selection-background-color: {p.bg_overlay}; }}"
        )
        out.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        out.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        if _ANSI_RE.search(text):
            display = _process_cr_ansi(text).rstrip()
            cursor = out.textCursor()
            _insert_ansi_text(cursor, display)
            out.setTextCursor(cursor)
        else:
            display = _clean_output(text).rstrip()
            cursor = out.textCursor()
            _insert_ansi_text(cursor, display)
            out.setTextCursor(cursor)
            is_stderr = bool(self._block.stderr) and not self._block.stdout
            _OutputHighlighter(
                out.document(),
                self._block.command.text,
                self._block.cwd,
                is_stderr,
            )

        line_h     = QFontMetrics(font).lineSpacing()
        line_count = out.document().blockCount()
        content_h  = line_count * line_h + 2
        max_h      = 200 * line_h + 2
        capped     = content_h >= max_h
        out.setFixedHeight(max(line_h + 2, min(max_h, content_h)))
        out.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if capped else Qt.ScrollBarAlwaysOff
        )

        return out

    def append_output(self, chunk: str) -> None:
        if self._output_widget is None:
            self._output_widget = self._build_output_empty()
            card_layout = self._card.layout()
            card_layout.insertWidget(1, self._output_widget)
            if self._expanded:
                self._output_widget.setVisible(True)
            self._sync_height()
        self._raw_output += chunk
        cursor = self._output_widget.textCursor()
        cursor.movePosition(QTextCursor.End)
        # handle carriage returns: \r without \n overwrites the current line (progress bars)
        first = True
        for part in chunk.split("\r"):
            if first:
                first = False
            else:
                # \r — move to start of current block, clear to end, then write new content
                cursor.movePosition(QTextCursor.StartOfBlock)
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
            _insert_ansi_text(cursor, part)
        self._output_widget.setTextCursor(cursor)
        self._schedule_resize()

    def _schedule_resize(self) -> None:
        if not self._resize_pending:
            self._resize_pending = True
            QTimer.singleShot(100, self._do_resize)

    def _do_resize(self) -> None:
        self._resize_pending = False
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
            display = _process_cr_ansi(self._raw_output).rstrip()
            self._output_widget.setPlainText("")
            cursor = self._output_widget.textCursor()
            _insert_ansi_text(cursor, display)
            self._output_widget.setTextCursor(cursor)
            self._resize_output()

        from ..services.ai_service import AiService
        if AiService.instance().is_enabled():
            if self._explain_btn:
                self._explain_btn.setVisible(True)
            if self._fix_btn and exit_code != 0:
                self._fix_btn.setVisible(True)

        self._sync_height()

    def _build_output_empty(self) -> _OutputEdit:
        p = ThemeManager.instance().current
        _s = SettingsService.instance().get()
        font = QFont(_s.font_family or "Monospace", _s.font_size_output or 11)
        out = _OutputEdit()
        out.setReadOnly(True)
        out.setFont(font)
        out.setFrameShape(QFrame.NoFrame)
        out.document().setDocumentMargin(0)
        out.setContentsMargins(0, 0, 0, 0)
        fg_color = _s.output_fg_override or p.fg
        out.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none;"
            f" color: {fg_color}; selection-background-color: {p.bg_overlay}; }}"
        )
        out.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        out.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        line_h = QFontMetrics(font).lineSpacing()
        out.setFixedHeight(line_h + 2)
        return out

    def _resize_output(self) -> None:
        if self._output_widget is None:
            return
        font = self._output_widget.font()
        line_h = QFontMetrics(font).lineSpacing()
        line_count = self._output_widget.document().blockCount()
        content_h  = line_count * line_h + 2
        max_h      = 200 * line_h + 2
        capped     = content_h >= max_h
        new_h      = min(max_h, content_h)
        self._output_widget.setFixedHeight(max(line_h + 2, new_h))
        self._output_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if capped else Qt.ScrollBarAlwaysOff
        )
        self._sync_height()

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
        # prefer streamed _raw_output over the block's stored stdout/stderr
        output = (
            _clean_output(self._raw_output).rstrip()
            if self._raw_output
            else (self._block.stdout or self._block.stderr).rstrip()
        )
        menu.addAction("Copy command",
                       lambda: QApplication.clipboard().setText(self._block.command.text))
        if output:
            menu.addAction("Copy output",
                           lambda o=output: QApplication.clipboard().setText(o))
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

    # ── AI actions ────────────────────────────────────────────────────────────

    def _on_explain_clicked(self) -> None:
        if self._explanation_panel and self._explanation_panel.isVisible():
            self._explanation_panel.setVisible(False)
            self._sync_height()
            return

        from ..services.ai_service import AiService
        if not AiService.instance().is_enabled():
            return

        if self._explain_btn:
            self._explain_btn.setText("…")
            self._explain_btn.setEnabled(False)

        worker = AiService.instance().explain(self._block)
        worker.result_ready.connect(self._show_explanation)
        worker.error_occurred.connect(lambda msg: self._show_explanation(f"⚠  {msg}"))
        worker.finished.connect(self._reset_explain_btn)
        self._workers.append(worker)
        worker.start()

    def _reset_explain_btn(self) -> None:
        if self._explain_btn:
            self._explain_btn.setText("?")
            self._explain_btn.setEnabled(True)

    def _show_explanation(self, text: str) -> None:
        p = ThemeManager.instance().current
        if self._explanation_panel is None:
            panel = QFrame()
            panel.setStyleSheet(
                f"QFrame {{ background: {p.bg_overlay}; border-radius: 4px; border: none; }}"
            )
            inner = QVBoxLayout(panel)
            inner.setContentsMargins(10, 8, 10, 8)
            edit = QPlainTextEdit()
            edit.setReadOnly(True)
            edit.setFrameShape(QFrame.NoFrame)
            edit.document().setDocumentMargin(0)
            edit.setContentsMargins(0, 0, 0, 0)
            edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            _fs = SettingsService.instance().get().font_size_output or 11
            edit.setStyleSheet(
                f"QTextEdit {{ background: transparent; border: none;"
                f" color: {p.fg}; font-size: {_fs}pt; }}"
            )
            inner.addWidget(edit)
            self._explanation_label = edit
            self._explanation_panel = panel
            if self._card:
                self._card.layout().addWidget(panel)

        if self._explanation_label:
            self._explanation_label.setPlainText(f"💡  {text}")
            QTimer.singleShot(0, self._resize_explanation)
        if self._explanation_panel:
            self._explanation_panel.setVisible(True)
        self._sync_height()

    def _resize_explanation(self) -> None:
        if self._explanation_label is None:
            return
        doc = self._explanation_label.document()
        line_h = QFontMetrics(self._explanation_label.font()).lineSpacing()
        doc.setTextWidth(max(self._explanation_label.viewport().width(), 200))
        content_h = int(doc.size().height()) + 16
        self._explanation_label.setFixedHeight(max(line_h + 16, min(content_h, 300)))
        self._sync_height()

    def _on_fix_clicked(self) -> None:
        self.fix_requested.emit(
            self._block.command.text,
            self._block.stderr,
            self._block.cwd,
        )

