from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Signal, Qt, QRect


class _HistoryInput(QLineEdit):
    go_previous         = Signal()
    go_next             = Signal()
    tab_pressed         = Signal()
    esc_pressed         = Signal()
    completion_up       = Signal()
    completion_down     = Signal()
    completion_accepted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.popup_open = False

    def focusNextPrevChild(self, _next: bool) -> bool:
        # Prevent Qt from consuming Tab for focus chain navigation so that
        # keyPressEvent receives Key_Tab and we can use it for completion.
        return False

    def keyPressEvent(self, event):
        key = event.key()

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

        if key == Qt.Key_Up:
            self.go_previous.emit()
        elif key == Qt.Key_Down:
            self.go_next.emit()
        else:
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
        self._input.setPlaceholderText("Digite um comando...")
        self._input.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #cdd6f4;"
            " font-family: Monospace; font-size: 10pt; }"
            "QLineEdit::placeholder { color: #45475a; }"
        )
        self._input.returnPressed.connect(self._submit)
        self._input.go_previous.connect(self._navigate_previous)
        self._input.go_next.connect(self._navigate_next)

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

        layout.addWidget(attach_btn)
        layout.addWidget(self._input)
        layout.addWidget(run_btn)

    # ── submission ────────────────────────────────────────────────────────────

    def _submit(self):
        text = self._input.text().strip()
        if text:
            self._history_index = -1
            self.command_submitted.emit(text)
            self._input.clear()

    # ── history navigation ────────────────────────────────────────────────────

    def _navigate_previous(self):
        if not self._history:
            return
        if self._history_index == -1:
            self._draft = self._input.text()
            self._history_index = len(self._history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self._input.setText(self._history[self._history_index])

    def _navigate_next(self):
        if self._history_index == -1:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._input.setText(self._history[self._history_index])
        else:
            self._history_index = -1
            self._input.setText(self._draft)

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

    @property
    def text_changed(self):
        return self._input.textChanged

    def get_completion_context(self) -> tuple[str, str, str]:
        """Return (text_before_last_word, dir_prefix, name_prefix)."""
        text = self._input.text()
        parts = text.rsplit(" ", 1)
        base = (parts[0] + " ") if len(parts) > 1 else ""
        token = parts[1] if len(parts) > 1 else parts[0]

        if "/" in token:
            idx = token.rfind("/")
            return base, token[:idx + 1], token[idx + 1:]
        return base, "", token

    def apply_completion(self, base: str, completion: str) -> None:
        new_text = base + completion
        self._input.setText(new_text)
        self._input.setCursorPosition(len(new_text))

    def set_popup_open(self, open: bool) -> None:
        self._input.popup_open = open

    def input_field_rect(self) -> QRect:
        """Input field geometry in InputBar-local coordinates."""
        return self._input.geometry()

    # ── public API ────────────────────────────────────────────────────────────

    def update_history(self, commands: list[str]) -> None:
        self._history = commands

    def update_cwd(self, display_path: str) -> None:
        pass  # cwd is owned by ShellSession; kept for API compatibility

    def set_text(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus()

    def focus(self):
        self._input.setFocus()
