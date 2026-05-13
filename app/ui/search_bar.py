from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel,
)
from PySide6.QtCore import Signal, Qt

from .theme import Palette, ThemeManager, TY


class SearchBar(QWidget):
    search_changed  = Signal(str)
    navigate_next   = Signal()
    navigate_prev   = Signal()
    closed          = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self._build_ui()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(8)

        self._icon = QLabel("⌕")
        self._icon.setStyleSheet(f"color: #6c7086; font-size: {TY.lg}px; background: transparent;")

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search blocks...")
        self._input.textChanged.connect(self.search_changed)
        self._input.returnPressed.connect(self.navigate_next)

        self._counter = QLabel("0 results")
        self._counter.setMinimumWidth(80)

        self._prev_btn = self._nav_btn("↑")
        self._prev_btn.clicked.connect(self.navigate_prev)

        self._next_btn = self._nav_btn("↓")
        self._next_btn.clicked.connect(self.navigate_next)

        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.clicked.connect(self.closed)

        layout.addWidget(self._icon)
        layout.addWidget(self._input)
        layout.addWidget(self._counter)
        layout.addWidget(self._prev_btn)
        layout.addWidget(self._next_btn)
        layout.addStretch()
        layout.addWidget(self._close_btn)

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(f"QWidget {{ background-color: {p.bg_panel}; }}")
        self._icon.setStyleSheet(f"color: {p.fg_muted}; font-size: {TY.lg}px; background: transparent;")
        self._input.setStyleSheet(
            f"QLineEdit {{ background: {p.bg_overlay}; color: {p.fg}; border: none;"
            f" border-radius: 4px; padding: 4px 10px; font-size: {TY.sm}px; }}"
            f"QLineEdit:focus {{ border: 1px solid {p.blue}; }}"
        )
        self._counter.setStyleSheet(f"color: {p.fg_dim}; font-size: {TY.xs}px; background: transparent;")
        nav_style = (
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg_muted}; border: none;"
            f" border-radius: 4px; font-size: {TY.mono_sm}px; }}"
            f"QPushButton:hover {{ background: {p.bg_hover2}; color: {p.fg}; }}"
        )
        self._prev_btn.setStyleSheet(nav_style)
        self._next_btn.setStyleSheet(nav_style)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.xl}px; }}"
            f"QPushButton:hover {{ color: {p.red_ui}; }}"
        )

    def update_count(self, count: int, current: int = 0) -> None:
        p = ThemeManager.instance().current
        if count == 0:
            self._counter.setText("0 results")
            self._counter.setStyleSheet(
                f"color: {p.bg}; background: {p.red};"
                f" border-radius: 10px; padding: 2px 8px; font-size: {TY.xs}px;"
            )
        else:
            self._counter.setText(f"{current + 1} of {count}")
            self._counter.setStyleSheet(
                f"color: {p.bg}; background: {p.green};"
                f" border-radius: 10px; padding: 2px 8px; font-size: {TY.xs}px;"
            )

    def query(self) -> str:
        return self._input.text()

    def focus(self) -> None:
        self._input.setFocus()
        self._input.selectAll()

    @staticmethod
    def _nav_btn(symbol: str) -> QPushButton:
        btn = QPushButton(symbol)
        btn.setFixedSize(24, 24)
        return btn
