from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel,
)
from PySide6.QtCore import Signal, Qt


class SearchBar(QWidget):
    search_changed  = Signal(str)
    navigate_next   = Signal()
    navigate_prev   = Signal()
    closed          = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet("QWidget { background-color: #10121e; }")
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(8)

        icon = QLabel("⌕")
        icon.setStyleSheet("color: #6c7086; font-size: 13pt; background: transparent;")

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search blocks...")
        self._input.setStyleSheet(
            "QLineEdit { background: #1e2235; color: #cdd6f4; border: none;"
            " border-radius: 4px; padding: 4px 10px; font-size: 9pt; }"
            "QLineEdit:focus { border: 1px solid #89b4fa; }"
        )
        self._input.textChanged.connect(self.search_changed)
        self._input.returnPressed.connect(self.navigate_next)

        self._counter = QLabel("0 results")
        self._counter.setStyleSheet("color: #45475a; font-size: 8pt; background: transparent;")
        self._counter.setMinimumWidth(80)

        prev_btn = self._nav_btn("↑")
        prev_btn.clicked.connect(self.navigate_prev)

        next_btn = self._nav_btn("↓")
        next_btn.clicked.connect(self.navigate_next)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6c7086; border: none;"
            " font-size: 14pt; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        close_btn.clicked.connect(self.closed)

        layout.addWidget(icon)
        layout.addWidget(self._input)
        layout.addWidget(self._counter)
        layout.addWidget(prev_btn)
        layout.addWidget(next_btn)
        layout.addStretch()
        layout.addWidget(close_btn)

    def update_count(self, count: int, current: int = 0) -> None:
        if count == 0:
            self._counter.setText("No results")
            self._counter.setStyleSheet("color: #e74c3c; font-size: 8pt; background: transparent;")
        else:
            self._counter.setText(f"{current + 1} of {count}")
            self._counter.setStyleSheet("color: #a6e3a1; font-size: 8pt; background: transparent;")

    def query(self) -> str:
        return self._input.text()

    def focus(self) -> None:
        self._input.setFocus()
        self._input.selectAll()

    @staticmethod
    def _nav_btn(symbol: str) -> QPushButton:
        btn = QPushButton(symbol)
        btn.setFixedSize(24, 24)
        btn.setStyleSheet(
            "QPushButton { background: #1e2235; color: #6c7086; border: none;"
            " border-radius: 4px; font-size: 10pt; }"
            "QPushButton:hover { background: #252840; color: #cdd6f4; }"
        )
        return btn
