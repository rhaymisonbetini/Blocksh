import random

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPlainTextEdit, QPushButton
from PySide6.QtCore import Signal, Qt, QRect
from PySide6.QtGui import QFont, QFontMetrics, QTextCursor

from .theme import Palette, ThemeManager, get_mono_font, TY

_PLACEHOLDERS = [
    "type your command...",
    "what's today's command?",
    "write something awesome...",
    "the terminal awaits...",
    "make it happen...",
    "your move...",
    "what shall we run today?",
    "command me...",
    "run something great...",
    "ready when you are...",
]


class _HistoryInput(QPlainTextEdit):
    go_previous         = Signal()
    go_next             = Signal()
    tab_pressed         = Signal()
    esc_pressed         = Signal()
    completion_up       = Signal()
    completion_down     = Signal()
    completion_accepted = Signal()
    command_submitted   = Signal()
    ctrl_c_pressed      = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.popup_open = False
        self.setPlaceholderText(random.choice(_PLACEHOLDERS))
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def focusNextPrevChild(self, _next: bool) -> bool:
        return False

    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()

        # #33: Ctrl+C clears input text then signals the terminal
        if key == Qt.Key_C and mods & Qt.ControlModifier:
            self.clear()
            self.ctrl_c_pressed.emit()
            return

        if key == Qt.Key_Tab:
            self.tab_pressed.emit()
            return

        if key == Qt.Key_Escape:
            self.esc_pressed.emit()
            return

        # #34: readline shortcuts
        if mods & Qt.ControlModifier:
            cursor = self.textCursor()
            if key == Qt.Key_A:
                cursor.movePosition(QTextCursor.StartOfLine)
                self.setTextCursor(cursor)
                return
            if key == Qt.Key_E:
                cursor.movePosition(QTextCursor.EndOfLine)
                self.setTextCursor(cursor)
                return
            if key == Qt.Key_W:
                cursor.movePosition(QTextCursor.PreviousWord, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                return
            if key == Qt.Key_K:
                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                return
            if key == Qt.Key_U:
                cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                return

        if self.popup_open:
            if key == Qt.Key_Up:
                self.completion_up.emit()
                return
            if key == Qt.Key_Down:
                self.completion_down.emit()
                return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.command_submitted.emit()
            return

        if key == Qt.Key_Up:
            if self.textCursor().blockNumber() == 0:
                self.go_previous.emit()
                return
        elif key == Qt.Key_Down:
            if self.textCursor().blockNumber() == self.document().blockCount() - 1:
                self.go_next.emit()
                return

        super().keyPressEvent(event)


class InputBar(QWidget):
    command_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InputBar")
        self._history: list[str] = []
        self._history_index: int = -1
        self._draft: str = ""
        self._build_ui()

        # #35: dynamic height — grow up to 5 lines as user types
        font = QFont("Monospace", TY.mono_sm)
        self._line_h  = QFontMetrics(font).lineSpacing()
        self._v_margin = 20   # layout top (10) + bottom (10) margins
        self._input.document().contentsChanged.connect(self._adjust_height)
        self._adjust_height()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        self._input = _HistoryInput()
        self._input.command_submitted.connect(self._submit)
        self._input.go_previous.connect(self._navigate_previous)
        self._input.go_next.connect(self._navigate_next)

        self._text_changed_callbacks: list = []
        self._input.textChanged.connect(self._on_text_changed)
        self._input.textChanged.connect(self._on_ai_mode_check)

        self._ai_btn = QPushButton("✦")
        self._ai_btn.setFixedSize(38, 38)
        self._ai_btn.setToolTip(
            "AI mode — type a request in natural language\n"
            "e.g.  > list all running docker containers\n"
            "Click to toggle the '> ' prefix"
        )
        self._ai_btn.clicked.connect(self._toggle_ai_prefix)

        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setFixedHeight(42)
        self._run_btn.setMinimumWidth(110)
        self._run_btn.clicked.connect(self._submit)

        layout.addWidget(self._input)
        layout.addWidget(self._ai_btn, 0, Qt.AlignTop)
        layout.addWidget(self._run_btn, 0, Qt.AlignTop)

    def apply_theme(self, p: Palette) -> None:
        mono = get_mono_font()
        ai_mode = self._input.toPlainText().startswith("> ")
        border_color = p.blue if ai_mode else p.border
        self.setStyleSheet(
            f"QWidget#InputBar {{ background: {p.bg_surface}; border: 1px solid {border_color};"
            f" border-radius: 10px; }}"
        )
        self._input.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; border: none; color: {p.fg};"
            f" font-family: {mono}; font-size: {TY.base}pt; }}"
        )
        self._apply_ai_mode_style(p, ai_mode)

    # ── dynamic height (#35) ──────────────────────────────────────────────────

    def _adjust_height(self) -> None:
        lines = max(1, self._input.document().blockCount())
        new_h = min(5 * self._line_h + self._v_margin,
                    lines * self._line_h + self._v_margin)
        min_h = max(self._line_h + self._v_margin, 36 + self._v_margin)
        self.setFixedHeight(max(min_h, new_h))

    # ── submission ────────────────────────────────────────────────────────────

    def _submit(self):
        text = self._input.toPlainText().strip()
        if text:
            self._history_index = -1
            self.command_submitted.emit(text)
            self._input.clear()

    # ── history navigation ────────────────────────────────────────────────────

    def _navigate_previous(self):
        if not self._history:
            return
        if self._history_index == -1:
            self._draft = self._input.toPlainText()
            self._history_index = len(self._history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self._input.setPlainText(self._history[self._history_index])
        self._move_cursor_end()

    def _navigate_next(self):
        if self._history_index == -1:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._input.setPlainText(self._history[self._history_index])
        else:
            self._history_index = -1
            self._input.setPlainText(self._draft)
        self._move_cursor_end()

    def _move_cursor_end(self):
        c = self._input.textCursor()
        c.movePosition(QTextCursor.End)
        self._input.setTextCursor(c)

    def _on_text_changed(self):
        for cb in self._text_changed_callbacks:
            cb(self._input.toPlainText())

    # ── completion API ────────────────────────────────────────────────────────

    @property
    def ctrl_c_pressed(self):
        return self._input.ctrl_c_pressed

    @property
    def tab_pressed(self):
        return self._input.tab_pressed

    @property
    def esc_pressed(self):
        return self._input.esc_pressed

    @property
    def completion_up(self):
        return self._input.completion_up

    @property
    def completion_down(self):
        return self._input.completion_down

    @property
    def completion_accepted(self):
        return self._input.completion_accepted

    class _TextChangedProxy:
        def __init__(self, bar: "InputBar"):
            self._bar = bar

        def connect(self, slot):
            self._bar._text_changed_callbacks.append(slot)

        def disconnect(self, slot=None):
            if slot is None:
                self._bar._text_changed_callbacks.clear()
            else:
                self._bar._text_changed_callbacks.remove(slot)

    @property
    def text_changed(self):
        if not hasattr(self, "_text_changed_proxy"):
            self._text_changed_proxy = self._TextChangedProxy(self)
        return self._text_changed_proxy

    def get_completion_context(self) -> tuple[str, str, str]:
        cursor = self._input.textCursor()
        text   = self._input.toPlainText()[:cursor.position()]
        parts  = text.rsplit(" ", 1)
        base   = (parts[0] + " ") if len(parts) > 1 else ""
        token  = parts[1] if len(parts) > 1 else parts[0]

        if "/" in token:
            idx = token.rfind("/")
            return base, token[:idx + 1], token[idx + 1:]
        return base, "", token

    def apply_completion(self, base: str, completion: str) -> None:
        cursor   = self._input.textCursor()
        full     = self._input.toPlainText()
        pos      = cursor.position()
        new_text = base + completion + full[pos:]
        self._input.setPlainText(new_text)
        c = self._input.textCursor()
        c.setPosition(len(base + completion))
        self._input.setTextCursor(c)

    def set_popup_open(self, open: bool) -> None:
        self._input.popup_open = open

    def input_field_rect(self) -> QRect:
        return self._input.geometry()

    # ── public API ────────────────────────────────────────────────────────────

    def update_history(self, commands: list[str]) -> None:
        self._history = commands

    def update_cwd(self, display_path: str) -> None:
        pass

    def set_text(self, text: str) -> None:
        self._input.setPlainText(text)
        self._move_cursor_end()
        self._input.setFocus()

    def set_running(self, running: bool) -> None:
        if running:
            self._run_btn.setText("● Running…")
            self._run_btn.setEnabled(False)
            self._ai_btn.setEnabled(False)
            self._input.setReadOnly(True)
        else:
            self._run_btn.setEnabled(True)
            self._ai_btn.setEnabled(True)
            self._input.setReadOnly(False)
            self._on_ai_mode_check()

    def set_thinking(self, active: bool) -> None:
        if active:
            self._run_btn.setText("AI…")
            self._run_btn.setEnabled(False)
            self._ai_btn.setEnabled(False)
            self._input.setReadOnly(True)
            self._input.setPlaceholderText("Asking AI…")
        else:
            self._run_btn.setEnabled(True)
            self._ai_btn.setEnabled(True)
            self._input.setReadOnly(False)
            self._input.setPlaceholderText(random.choice(_PLACEHOLDERS))
            self._on_ai_mode_check()

    def _toggle_ai_prefix(self) -> None:
        text = self._input.toPlainText()
        if text.startswith("> "):
            self._input.setPlainText(text[2:])
        else:
            self._input.setPlainText("> " + text)
        self._move_cursor_end()

    def _on_ai_mode_check(self) -> None:
        p = ThemeManager.instance().current
        ai_mode = self._input.toPlainText().startswith("> ")
        border_color = p.blue if ai_mode else p.border
        self.setStyleSheet(
            f"QWidget#InputBar {{ background: {p.bg_surface}; border: 1px solid {border_color};"
            f" border-radius: 10px; }}"
        )
        self._apply_ai_mode_style(p, ai_mode)

    def _apply_ai_mode_style(self, p: Palette, ai_mode: bool) -> None:
        if ai_mode:
            self._ai_btn.setStyleSheet(
                f"QPushButton {{ background: {p.blue}; color: {p.bg}; border: none;"
                f" border-radius: 5px; font-size: {TY.xl}pt; font-weight: bold; }}"
                f"QPushButton:hover {{ background: {p.blue}; opacity: 0.85; }}"
            )
            self._run_btn.setText("Ask AI →")
            self._run_btn.setStyleSheet(
                f"QPushButton {{ background: {p.blue}; color: {p.bg}; border: none;"
                f" border-radius: 6px; font-weight: bold; font-size: {TY.lg}pt;"
                f" padding: 0 18px; }}"
                f"QPushButton:hover {{ background: #74b0e8; }}"
                f"QPushButton:pressed {{ background: #5a9fd4; }}"
            )
        else:
            self._ai_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {p.fg_dim}; border: none;"
                f" border-radius: 5px; font-size: {TY.xl}pt; }}"
                f"QPushButton:hover {{ color: {p.blue}; }}"
            )
            self._run_btn.setText("▶  Run")
            self._run_btn.setStyleSheet(
                f"QPushButton {{ background: {p.accent}; color: {p.accent_fg}; border: none;"
                f" border-radius: 6px; font-weight: bold; font-size: {TY.lg}pt;"
                f" padding: 0 18px; }}"
                f"QPushButton:hover {{ background: {p.accent_hover}; }}"
                f"QPushButton:pressed {{ background: {p.accent_hover}; }}"
            )

    def focus(self):
        self._input.setFocus()
