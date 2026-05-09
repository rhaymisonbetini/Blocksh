from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Signal

from .theme import Palette, ThemeManager


class AiPermissionBanner(QWidget):
    """Inline banner shown when the AI agent wants to run a shell command."""

    allowed = Signal()
    denied  = Signal()

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
        icon.setStyleSheet("background: transparent; border: none; font-size: 13pt;")
        icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(icon)

        self._label = QLabel()
        self._label.setWordWrap(False)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._label, 1)

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

    def show_request(self, command: str) -> None:
        short = command if len(command) <= 80 else command[:77] + "…"
        self._label.setText(f"AI wants to run:   <b>{short}</b>")
        self.show()

    def _on_allow(self) -> None:
        self.hide()
        self.allowed.emit()

    def _on_deny(self) -> None:
        self.hide()
        self.denied.emit()

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"QWidget {{ background: {p.bg_overlay};"
            f" border-top: 1px solid {p.border}; border-bottom: 1px solid {p.border}; }}"
        )
        self._label.setStyleSheet(
            f"color: {p.fg}; font-size: 9pt; background: transparent; border: none;"
        )
        self._allow_btn.setStyleSheet(
            f"QPushButton {{ background: {p.green}; color: {p.bg}; border: none;"
            f" border-radius: 4px; font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #b8f0b0; }}"
        )
        self._deny_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.red};"
            f" border: 1px solid {p.red}; border-radius: 4px; font-size: 9pt; }}"
            f"QPushButton:hover {{ background: {p.red}; color: {p.bg}; }}"
        )
