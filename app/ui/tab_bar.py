import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt


def _username() -> str:
    return os.environ.get("USER") or os.environ.get("USERNAME") or "U"


class TabBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet("QWidget { background-color: #10121e; }")
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # New terminal button
        add_btn = QPushButton("+")
        add_btn.setFixedSize(28, 28)
        add_btn.setStyleSheet(
            "QPushButton { background: #1e2235; color: #6c7086; border: none;"
            " border-radius: 6px; font-size: 14pt; }"
            "QPushButton:hover { background: #252840; color: #cdd6f4; }"
        )
        layout.addWidget(add_btn)

        # Active tab
        tab = self._make_tab("Terminal 1")
        layout.addWidget(tab)

        layout.addStretch()

        # Right-side icon buttons
        for symbol in ["⌕", "⚙"]:
            btn = QPushButton(symbol)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                "QPushButton { background: transparent; color: #6c7086; border: none;"
                " border-radius: 6px; font-size: 13pt; }"
                "QPushButton:hover { background: #1e2235; color: #cdd6f4; }"
            )
            layout.addWidget(btn)

        # User avatar — initials in a colored circle
        initials = _username()[:2].upper()
        avatar = QPushButton(initials)
        avatar.setFixedSize(28, 28)
        avatar.setStyleSheet(
            "QPushButton { background: #2ecc71; color: #0d0f1a; border: none;"
            " border-radius: 14px; font-weight: bold; font-size: 8pt; }"
        )
        layout.addWidget(avatar)

    @staticmethod
    def _make_tab(title: str) -> QWidget:
        tab = QWidget()
        tab.setFixedHeight(32)
        tab.setStyleSheet(
            "QWidget { background: #1e2235; border-radius: 6px; }"
        )

        layout = QHBoxLayout(tab)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        lbl = QLabel(title)
        lbl.setStyleSheet("color: #cdd6f4; font-size: 9pt; background: transparent;")

        close_btn = QPushButton("×")
        close_btn.setFixedSize(16, 16)
        close_btn.setAttribute(Qt.WA_TransparentForMouseEvents)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #45475a; border: none;"
            " font-size: 12pt; }"
        )

        layout.addWidget(lbl)
        layout.addWidget(close_btn)

        return tab
