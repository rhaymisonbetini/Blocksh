from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QScrollArea, QWidget
from PySide6.QtCore import Signal, Qt

from .theme import Palette, ThemeManager, get_mono_font, TY


class CompletionPopup(QFrame):
    item_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self._items: list[str] = []
        self._selected = -1
        self._buttons: list[QPushButton] = []
        self._build_ui()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._list = QWidget()
        self._list.setStyleSheet("QWidget { background: transparent; }")
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(1)

        self._scroll.setWidget(self._list)
        layout.addWidget(self._scroll)

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"QFrame {{ background: {p.bg_overlay}; border: 1px solid {p.border}; border-radius: 6px; }}"
        )
        for i, btn in enumerate(self._buttons):
            is_dir = self._items[i].endswith("/")
            btn.setStyleSheet(self._btn_style(p, is_dir, active=(i == self._selected)))

    def update_items(self, items: list[tuple[str, bool]]) -> None:
        # Build the new list as a standalone widget (no visible parent) so that
        # resize() triggers an immediate layout pass — all buttons are positioned
        # correctly before the widget is inserted into the scroll area.
        new_list = QWidget()
        new_list.setStyleSheet("QWidget { background: transparent; }")
        new_layout = QVBoxLayout(new_list)
        new_layout.setContentsMargins(0, 0, 0, 0)
        new_layout.setSpacing(1)

        p = ThemeManager.instance().current
        new_buttons: list[QPushButton] = []
        new_items: list[str] = []
        for text, is_dir in items:
            new_items.append(text)
            btn = QPushButton(text)
            btn.setFixedHeight(28)
            btn.setStyleSheet(self._btn_style(p, is_dir, active=False))
            btn.clicked.connect(lambda checked, t=text: self.item_activated.emit(t))
            new_layout.addWidget(btn)
            new_buttons.append(btn)

        vp_w = self._scroll.viewport().width()
        new_list.resize(vp_w if vp_w > 0 else 200, max(1, len(items)) * 29)

        self._scroll.setWidget(new_list)   # Qt deletes the old list widget
        self._list = new_list
        self._list_layout = new_layout
        self._buttons = new_buttons
        self._items = new_items
        self._selected = -1

        row_h = 28
        self.setFixedHeight(min(200, len(items) * row_h + 8))

        if self._buttons:
            self._set_selected(0)

    def select_next(self) -> None:
        if self._items:
            self._set_selected((self._selected + 1) % len(self._items))

    def select_prev(self) -> None:
        if self._items:
            self._set_selected((self._selected - 1) % len(self._items))

    def current_text(self) -> str | None:
        if 0 <= self._selected < len(self._items):
            return self._items[self._selected]
        return None

    def _set_selected(self, index: int) -> None:
        p = ThemeManager.instance().current
        if 0 <= self._selected < len(self._buttons):
            is_dir = self._items[self._selected].endswith("/")
            self._buttons[self._selected].setStyleSheet(self._btn_style(p, is_dir, active=False))
        self._selected = index
        if 0 <= index < len(self._buttons):
            btn = self._buttons[index]
            btn.setStyleSheet(self._btn_style(p, self._items[index].endswith("/"), active=True))
            self._scroll.ensureWidgetVisible(btn)

    @staticmethod
    def _btn_style(p: Palette, is_dir: bool, active: bool) -> str:
        color = p.blue if is_dir else p.fg
        bg = p.bg_selected if active else "transparent"
        return (
            f"QPushButton {{ background: {bg}; color: {color}; border: none;"
            f" font-family: {get_mono_font()}; font-size: {TY.sm}px; text-align: left; padding: 0 10px; }}"
            f"QPushButton:hover {{ background: {p.bg_hover2}; }}"
        )
