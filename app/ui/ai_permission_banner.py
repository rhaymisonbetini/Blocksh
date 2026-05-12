from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QLineEdit, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from .theme import Palette, ThemeManager, TY


class AiPermissionBanner(QWidget):
    """Inline banner for two modes:
    - permission: AI wants to run a shell command (Allow / Deny)
    - question:   AI asks the user a clarifying question (free-text reply)
    """

    allowed  = Signal()
    denied   = Signal()
    answered = Signal(str)   # emitted in question mode with the user's reply

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)
        self.hide()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        icon = QLabel("🤖")
        icon.setStyleSheet(f"background: transparent; border: none; font-size: {TY.lg}pt;")
        icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(icon)

        self._label = QLabel()
        self._label.setWordWrap(False)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._label, 1)

        # Question-mode text input
        self._answer_input = QLineEdit()
        self._answer_input.setPlaceholderText("Your answer…")
        self._answer_input.setFixedHeight(28)
        self._answer_input.setMinimumWidth(200)
        self._answer_input.returnPressed.connect(self._on_send)
        layout.addWidget(self._answer_input)

        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedHeight(28)
        self._send_btn.setMinimumWidth(70)
        self._send_btn.clicked.connect(self._on_send)
        layout.addWidget(self._send_btn)

        self._allow_btn = QPushButton("Allow")
        self._allow_btn.setFixedHeight(28)
        self._allow_btn.setMinimumWidth(70)
        self._allow_btn.clicked.connect(self._on_allow)
        layout.addWidget(self._allow_btn)

        self._deny_btn = QPushButton("Deny")
        self._deny_btn.setFixedHeight(28)
        self._deny_btn.setMinimumWidth(70)
        self._deny_btn.clicked.connect(self._on_deny)
        layout.addWidget(self._deny_btn)

    # ── public API ─────────────────────────────────────────────────────────────

    def show_request(self, command: str) -> None:
        """Show permission prompt for a shell command."""
        short = command if len(command) <= 80 else command[:77] + "…"
        self._label.setText(f"AI wants to run:   <b>{short}</b>")
        self._answer_input.hide()
        self._send_btn.hide()
        self._allow_btn.show()
        self._deny_btn.show()
        self.show()

    def show_question(self, question: str) -> None:
        """Show a free-text reply prompt for an AI clarifying question."""
        short = question if len(question) <= 80 else question[:77] + "…"
        self._label.setText(f"AI asks:   <b>{short}</b>")
        self._answer_input.clear()
        self._answer_input.show()
        self._send_btn.show()
        self._allow_btn.hide()
        self._deny_btn.hide()
        self.show()
        self._answer_input.setFocus()

    # ── slots ──────────────────────────────────────────────────────────────────

    def _on_allow(self) -> None:
        self.hide()
        self.allowed.emit()

    def _on_deny(self) -> None:
        self.hide()
        self.denied.emit()

    def _on_send(self) -> None:
        answer = self._answer_input.text().strip()
        self.hide()
        self.answered.emit(answer)

    # ── theming ────────────────────────────────────────────────────────────────

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"QWidget {{ background: {p.bg_overlay};"
            f" border-top: 1px solid {p.border}; border-bottom: 1px solid {p.border}; }}"
        )
        self._label.setStyleSheet(
            f"color: {p.fg}; font-size: {TY.sm}pt; background: transparent; border: none;"
        )
        self._answer_input.setStyleSheet(
            f"QLineEdit {{ background: {p.bg}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 4px; font-size: {TY.sm}pt; padding: 0 6px; }}"
            f"QLineEdit:focus {{ border-color: {p.blue}; }}"
        )
        self._send_btn.setStyleSheet(
            f"QPushButton {{ background: {p.blue}; color: {p.bg}; border: none;"
            f" border-radius: 4px; font-size: {TY.sm}pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #74b0e8; }}"
        )
        self._allow_btn.setStyleSheet(
            f"QPushButton {{ background: {p.green}; color: {p.bg}; border: none;"
            f" border-radius: 4px; font-size: {TY.sm}pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #b8f0b0; }}"
        )
        self._deny_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.red};"
            f" border: 1px solid {p.red}; border-radius: 4px; font-size: {TY.sm}pt; }}"
            f"QPushButton:hover {{ background: {p.red}; color: {p.bg}; }}"
        )
