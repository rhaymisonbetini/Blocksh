import random

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPlainTextEdit, QPushButton
from PySide6.QtCore import Signal, Qt, QRect
from PySide6.QtGui import QTextCursor

from .theme import Palette, ThemeManager

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

        if key == Qt.Key_Tab:
            self.tab_pressed.emit()
            return

        if key == Qt.Key_Escape:
            self.esc_pressed.emit()
            return

        if self.popup_open:
            if key == Qt.Key_Up:
                self.completion_up.emit()
                return
            if key == Qt.Key_Down:
                self.completion_down.emit()
                return
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.completion_accepted.emit()
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
        self._history: list[str] = []
        self._history_index: int = -1
        self._draft: str = ""
        self.setFixedHeight(60)
        self._build_ui()

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

        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setFixedHeight(36)
        self._run_btn.setMinimumWidth(88)
        self._run_btn.setStyleSheet(
            "QPushButton { background: #2ecc71; color: #0d0f1a; border: none;"
            " border-radius: 6px; font-weight: bold; font-size: 10pt;"
            " padding: 0 18px; }"
            "QPushButton:hover { background: #27ae60; }"
            "QPushButton:pressed { background: #1e8449; }"
        )
        self._run_btn.clicked.connect(self._submit)

        layout.addWidget(self._input)
        layout.addWidget(self._run_btn, 0, Qt.AlignTop)

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(f"QWidget {{ background-color: {p.bg}; }}")
        self._input.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; border: none; color: {p.fg};"
            f" font-family: Monospace; font-size: 10pt; }}"
        )

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

    def focus(self):
        self._input.setFocus()
