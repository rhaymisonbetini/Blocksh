import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt


def _username() -> str:
    return os.environ.get("USER") or os.environ.get("USERNAME") or "U"


class _Tab(QWidget):
    close_clicked = Signal()
    tab_clicked   = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self._active = False
        self._build_ui(title)
        self._update_style()

    def _build_ui(self, title: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self._lbl = QLabel(title)
        self._lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._lbl.setStyleSheet("color: #6c7086; font-size: 9pt; background: transparent; border: none;")

        close_btn = QPushButton("×")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #45475a; border: none; font-size: 12pt; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        close_btn.clicked.connect(self.close_clicked)

        layout.addWidget(self._lbl)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        self.tab_clicked.emit()
        super().mousePressEvent(event)

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self._update_style()
        color = "#cdd6f4" if active else "#6c7086"
        self._lbl.setStyleSheet(f"color: {color}; font-size: 9pt; background: transparent; border: none;")

    def set_title(self, title: str) -> None:
        self._lbl.setText(title)

    def _update_style(self):
        bg = "#1e2235" if self._active else "transparent"
        self.setStyleSheet(f"QWidget {{ background: {bg}; border-radius: 6px; }}")


class TabBar(QWidget):
    tab_add_requested    = Signal()
    tab_close_requested  = Signal(int)
    tab_switched         = Signal(int)
    search_requested     = Signal()
    collapse_all_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet("QWidget { background-color: #10121e; }")
        self._tabs: list[_Tab] = []
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(28, 28)
        add_btn.setStyleSheet(
            "QPushButton { background: #1e2235; color: #6c7086; border: none;"
            " border-radius: 6px; font-size: 14pt; }"
            "QPushButton:hover { background: #252840; color: #cdd6f4; }"
        )
        add_btn.clicked.connect(self.tab_add_requested)
        layout.addWidget(add_btn)

        self._tab_strip = QWidget()
        self._tab_strip.setStyleSheet("QWidget { background: transparent; }")
        self._tab_layout = QHBoxLayout(self._tab_strip)
        self._tab_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_layout.setSpacing(4)
        layout.addWidget(self._tab_strip, 1)

        search_btn = QPushButton("⌕")
        search_btn.setFixedSize(28, 28)
        search_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6c7086; border: none;"
            " border-radius: 6px; font-size: 13pt; }"
            "QPushButton:hover { background: #1e2235; color: #cdd6f4; }"
        )
        search_btn.clicked.connect(self.search_requested)
        layout.addWidget(search_btn)

        collapse_btn = QPushButton("⊟")
        collapse_btn.setFixedSize(28, 28)
        collapse_btn.setToolTip("Collapse / expand all blocks")
        collapse_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6c7086; border: none;"
            " border-radius: 6px; font-size: 13pt; }"
            "QPushButton:hover { background: #1e2235; color: #cdd6f4; }"
        )
        collapse_btn.clicked.connect(self.collapse_all_requested)
        layout.addWidget(collapse_btn)

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6c7086; border: none;"
            " border-radius: 6px; font-size: 13pt; }"
            "QPushButton:hover { background: #1e2235; color: #cdd6f4; }"
        )
        layout.addWidget(settings_btn)

        initials = _username()[:2].upper()
        avatar = QPushButton(initials)
        avatar.setFixedSize(28, 28)
        avatar.setStyleSheet(
            "QPushButton { background: #2ecc71; color: #0d0f1a; border: none;"
            " border-radius: 14px; font-weight: bold; font-size: 8pt; }"
        )
        layout.addWidget(avatar)

    def add_tab(self, title: str) -> int:
        tab = _Tab(title)
        tab.tab_clicked.connect(lambda t=tab: self._on_tab_clicked(t))
        tab.close_clicked.connect(lambda t=tab: self._on_tab_close(t))
        self._tabs.append(tab)
        self._tab_layout.addWidget(tab)
        return len(self._tabs) - 1

    def remove_tab(self, index: int) -> None:
        if index < 0 or index >= len(self._tabs):
            return
        tab = self._tabs.pop(index)
        self._tab_layout.removeWidget(tab)
        tab.hide()
        tab.deleteLater()

    def set_active(self, index: int) -> None:
        for i, tab in enumerate(self._tabs):
            tab.set_active(i == index)

    def update_tab_title(self, index: int, title: str) -> None:
        if 0 <= index < len(self._tabs):
            self._tabs[index].set_title(title)

    def count(self) -> int:
        return len(self._tabs)

    def _on_tab_clicked(self, tab: _Tab) -> None:
        if tab in self._tabs:
            self.tab_switched.emit(self._tabs.index(tab))

    def _on_tab_close(self, tab: _Tab) -> None:
        if tab in self._tabs:
            self.tab_close_requested.emit(self._tabs.index(tab))
