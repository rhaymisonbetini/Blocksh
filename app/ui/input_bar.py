from PySide6.QtWidgets import QWidget, QHBoxLayout, QPlainTextEdit, QPushButton
from PySide6.QtCore import Signal, Qt, QRect, QSize
from PySide6.QtGui import QFontMetrics, QTextCursor


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
        self.setPlaceholderText("Digite um comando...")
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document().contentsChanged.connect(self.updateGeometry)

    def focusNextPrevChild(self, _next: bool) -> bool:
        return False   # Tab must reach keyPressEvent for completion

    def sizeHint(self) -> QSize:
        fm    = QFontMetrics(self.font())
        lines = max(1, self.document().blockCount())
        h     = lines * fm.lineSpacing() + 20   # 10 px top + 10 px bottom margin
        return QSize(super().sizeHint().width(), min(160, max(40, h)))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()

        if key == Qt.Key_Tab:
            self.tab_pressed.emit()
            return

        if key == Qt.Key_Escape:
            self.esc_pressed.emit()
            return

        # completion navigation takes priority over history / submit
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
                super().keyPressEvent(event)   # insert real newline
            else:
                self.command_submitted.emit()
            return

        # Up / Down navigate history only when on the first / last line
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
        self.setMinimumHeight(48)
        self.setMaximumHeight(200)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("QWidget { background-color: #0d0f1a; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        attach_btn = QPushButton("⊕")
        attach_btn.setFixedSize(36, 36)
        attach_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #45475a; border: none;"
            " font-size: 16pt; }"
            "QPushButton:hover { color: #6c7086; }"
        )

        self._input = _HistoryInput()
        self._input.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none; color: #cdd6f4;"
            " font-family: Monospace; font-size: 10pt; }"
        )
        self._input.command_submitted.connect(self._submit)
        self._input.go_previous.connect(self._navigate_previous)
        self._input.go_next.connect(self._navigate_next)

        self._text_changed_callbacks: list = []
        self._input.textChanged.connect(self._on_text_changed)

        run_btn = QPushButton("▶  Run")
        run_btn.setFixedHeight(36)
        run_btn.setMinimumWidth(88)
        run_btn.setStyleSheet(
            "QPushButton { background: #2ecc71; color: #0d0f1a; border: none;"
            " border-radius: 6px; font-weight: bold; font-size: 10pt;"
            " padding: 0 18px; }"
            "QPushButton:hover { background: #27ae60; }"
            "QPushButton:pressed { background: #1e8449; }"
        )
        run_btn.clicked.connect(self._submit)

        layout.addWidget(attach_btn, 0, Qt.AlignTop)
        layout.addWidget(self._input)
        layout.addWidget(run_btn, 0, Qt.AlignTop)

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

    # ── text_changed bridge (QLineEdit had str arg; QPlainTextEdit does not) ──

    def _on_text_changed(self):
        # Emit via a plain Signal stored on the instance isn't possible after
        # construction, so we use a list of connected callables instead.
        for cb in self._text_changed_callbacks:
            cb(self._input.toPlainText())

    # ── completion API (called / connected by TerminalPanel) ──────────────────

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

    # text_changed is special: QPlainTextEdit.textChanged carries no arg, but
    # TerminalPanel expects a str.  We expose a tiny adapter object.
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
        """Return (text_before_last_word, dir_prefix, name_prefix)."""
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
        # replace only the token portion (everything from base start to cursor)
        new_text = base + completion + full[pos:]
        self._input.setPlainText(new_text)
        c = self._input.textCursor()
        c.setPosition(len(base + completion))
        self._input.setTextCursor(c)

    def set_popup_open(self, open: bool) -> None:
        self._input.popup_open = open

    def input_field_rect(self) -> QRect:
        """Input field geometry in InputBar-local coordinates."""
        return self._input.geometry()

    # ── public API ────────────────────────────────────────────────────────────

    def update_history(self, commands: list[str]) -> None:
        self._history = commands

    def update_cwd(self, display_path: str) -> None:
        pass   # cwd owned by ShellSession

    def set_text(self, text: str) -> None:
        self._input.setPlainText(text)
        self._move_cursor_end()
        self._input.setFocus()

    def focus(self):
        self._input.setFocus()
