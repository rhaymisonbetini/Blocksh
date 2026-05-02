from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QScrollArea, QWidget
from PySide6.QtCore import Signal, Qt


class CompletionPopup(QFrame):
    item_activated = Signal(str)

    def __init__(self):
        # Tool + no focus steal: stays visible while user types in the input
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)
        self.setStyleSheet(
            "QFrame { background: #1e2235; border: 1px solid #313244; border-radius: 6px; }"
        )
        self._items: list[str] = []
        self._selected = -1
        self._buttons: list[QPushButton] = []
        self._build_ui()

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

    def update_items(self, items: list[tuple[str, bool]]) -> None:
        """items: list of (completion_text, is_dir)"""
        for btn in self._buttons:
            self._list_layout.removeWidget(btn)
            btn.deleteLater()
        self._buttons.clear()
        self._items.clear()
        self._selected = -1

        for text, is_dir in items:
            self._items.append(text)
            btn = self._make_button(text, is_dir, active=False)
            btn.clicked.connect(lambda checked, t=text: self.item_activated.emit(t))
            self._list_layout.addWidget(btn)
            self._buttons.append(btn)

        row_h = 26
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
        if 0 <= self._selected < len(self._buttons):
            old_text = self._items[self._selected]
            is_dir = old_text.endswith("/")
            self._buttons[self._selected].setStyleSheet(
                self._button_style(is_dir, active=False)
            )
        self._selected = index
        if 0 <= index < len(self._buttons):
            btn = self._buttons[index]
            btn.setStyleSheet(self._button_style(self._items[index].endswith("/"), active=True))
            self._scroll.ensureWidgetVisible(btn)

    def _make_button(self, text: str, is_dir: bool, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(26)
        btn.setStyleSheet(self._button_style(is_dir, active))
        return btn

    @staticmethod
    def _button_style(is_dir: bool, active: bool) -> str:
        color = "#89b4fa" if is_dir else "#cdd6f4"
        bg = "#2a3f6e" if active else "transparent"
        return (
            f"QPushButton {{ background: {bg}; color: {color}; border: none;"
            f" font-family: Monospace; font-size: 9pt; text-align: left; padding: 0 10px; }}"
            f"QPushButton:hover {{ background: #252840; }}"
        )
