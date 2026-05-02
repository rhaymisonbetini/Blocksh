import os
from pathlib import Path
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Signal, Qt, QPoint

from .completion_popup import CompletionPopup


class _HistoryInput(QLineEdit):
    go_previous  = Signal()
    go_next      = Signal()
    tab_pressed  = Signal()
    esc_pressed  = Signal()
    popup_up     = Signal()
    popup_down   = Signal()
    popup_enter  = Signal()
    focus_lost   = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.popup_open = False

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Tab:
            self.tab_pressed.emit()
            return                          # never shift focus on Tab

        if key == Qt.Key_Escape:
            self.esc_pressed.emit()
            return

        if self.popup_open:
            if key == Qt.Key_Up:
                self.popup_up.emit()
                return
            if key == Qt.Key_Down:
                self.popup_down.emit()
                return
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.popup_enter.emit()
                return

        if key == Qt.Key_Up:
            self.go_previous.emit()
        elif key == Qt.Key_Down:
            self.go_next.emit()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_lost.emit()


class InputBar(QWidget):
    command_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._history_index: int = -1
        self._draft: str = ""
        self._cwd: str = str(Path.home())
        self.setFixedHeight(60)
        self._build_ui()
        self._popup = CompletionPopup()
        self._popup.item_activated.connect(self._on_completion_activated)

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
        self._input.tab_pressed.connect(self._on_tab_pressed)
        self._input.esc_pressed.connect(self._close_popup)
        self._input.popup_up.connect(lambda: self._popup.select_prev())
        self._input.popup_down.connect(lambda: self._popup.select_next())
        self._input.popup_enter.connect(self._on_popup_enter)
        self._input.focus_lost.connect(self._close_popup)
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

        layout.addWidget(attach_btn)
        layout.addWidget(self._input)
        layout.addWidget(run_btn)

    # ── submission ────────────────────────────────────────────────────────────

    def _submit(self):
        self._close_popup()
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

    # ── tab completion ────────────────────────────────────────────────────────

    def _on_tab_pressed(self):
        if self._popup.isVisible():
            self._popup.select_next()
        else:
            self._trigger_completion()

    def _trigger_completion(self):
        base, path_prefix, name_prefix = self._extract_prefix()
        if not name_prefix and not path_prefix:
            return

        matches = self._get_completions(path_prefix, name_prefix)
        if not matches:
            return

        if len(matches) == 1:
            self._apply_completion(base, matches[0][0])
            return

        self._popup.update_items(matches)
        self._position_popup()
        self._popup.show()
        self._input.popup_open = True

    def _on_text_changed(self, _text: str):
        if not self._popup.isVisible():
            return
        base, path_prefix, name_prefix = self._extract_prefix()
        matches = self._get_completions(path_prefix, name_prefix)
        if matches:
            self._popup.update_items(matches)
            self._position_popup()
        else:
            self._close_popup()

    def _on_popup_enter(self):
        text = self._popup.current_text()
        if text:
            base, _, _ = self._extract_prefix()
            self._apply_completion(base, text)
        self._close_popup()

    def _on_completion_activated(self, text: str):
        base, _, _ = self._extract_prefix()
        self._apply_completion(base, text)
        self._close_popup()
        self._input.setFocus()

    def _apply_completion(self, base: str, completion: str) -> None:
        new_text = base + completion
        self._input.setText(new_text)
        self._input.setCursorPosition(len(new_text))

    def _close_popup(self):
        self._popup.hide()
        self._input.popup_open = False

    def _position_popup(self):
        global_pos = self._input.mapToGlobal(QPoint(0, 0))
        popup_h = self._popup.height()
        self._popup.move(global_pos.x(), global_pos.y() - popup_h - 4)
        self._popup.setFixedWidth(max(220, self._input.width()))

    # ── completion helpers ────────────────────────────────────────────────────

    def _extract_prefix(self) -> tuple[str, str, str]:
        """Returns (text_before_last_word, dir_prefix, name_prefix)."""
        text = self._input.text()
        parts = text.rsplit(" ", 1)
        base = (parts[0] + " ") if len(parts) > 1 else ""
        token = parts[1] if len(parts) > 1 else parts[0]

        if "/" in token:
            slash_idx = token.rfind("/")
            path_prefix = token[:slash_idx + 1]
            name_prefix = token[slash_idx + 1:]
        else:
            path_prefix = ""
            name_prefix = token

        return base, path_prefix, name_prefix

    def _get_completions(self, path_prefix: str, name_prefix: str) -> list[tuple[str, bool]]:
        """Scan filesystem and return (completion_text, is_dir) pairs."""
        if path_prefix:
            if path_prefix.startswith("~"):
                search_dir = str(Path.home()) + path_prefix[1:]
            elif os.path.isabs(path_prefix):
                search_dir = path_prefix
            else:
                search_dir = os.path.join(self._cwd, path_prefix)
        else:
            search_dir = self._cwd

        if not search_dir:
            return []

        try:
            matches = []
            with os.scandir(search_dir) as entries:
                for entry in entries:
                    if entry.name.startswith(name_prefix):
                        is_dir = entry.is_dir()
                        suffix = "/" if is_dir else ""
                        matches.append((path_prefix + entry.name + suffix, is_dir))
            return sorted(matches, key=lambda x: (not x[1], x[0].lower()))
        except (PermissionError, FileNotFoundError, OSError):
            return []

    # ── public API ────────────────────────────────────────────────────────────

    def update_history(self, commands: list[str]) -> None:
        self._history = commands

    def update_cwd(self, display_path: str) -> None:
        home = str(Path.home())
        if display_path.startswith("~"):
            self._cwd = home + display_path[1:]
        else:
            self._cwd = display_path or home

    def set_text(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus()

    def focus(self):
        self._input.setFocus()
