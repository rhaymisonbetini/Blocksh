import os
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QStackedWidget,
    QButtonGroup,
)
from PySide6.QtCore import Qt, Signal

from ..domain.block import Block


def _os_info() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return platform.system()


def _username() -> str:
    return os.environ.get("USER") or os.environ.get("USERNAME") or "user"


_NAV_MAIN = [
    (">_", "Terminal",   True),
    ("≡",  "History",    False),
    ("◇",  "Favorites",  False),
    ("⊞",  "Projects",   False),
]

_NAV_FOOTER = [
    ("⚙",  "Settings",  False),
    ("◑",  "Themes",    False),
    ("○",  "About",     False),
]


class _NavButton(QPushButton):
    def __init__(self, icon: str, label: str, active: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(active)
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        icon_lbl.setStyleSheet("font-size: 12pt; background: transparent; border: none;")

        text_lbl = QLabel(label)
        text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        text_lbl.setStyleSheet("font-size: 9pt; background: transparent; border: none;")

        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)
        layout.addStretch()

        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
                color: #6c7086;
                text-align: left;
            }
            QPushButton:checked {
                background-color: #1e3a6e;
                color: #ffffff;
            }
            QPushButton:hover:!checked {
                background-color: #181b2e;
                color: #cdd6f4;
            }
        """)


class Sidebar(QWidget):
    command_selected       = Signal(str)
    history_open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self.setStyleSheet("QWidget { background-color: #10121e; }")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_nav_page())
        self._stack.addWidget(self._build_history_page())
        layout.addWidget(self._stack)

    def _build_nav_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 16, 8, 12)
        layout.setSpacing(2)

        logo = QLabel(">_ Blocksh")
        logo.setStyleSheet(
            "color: #cdd6f4; font-family: Monospace; font-size: 11pt;"
            " font-weight: bold; padding: 4px 8px 20px 8px;"
            " background: transparent;"
        )
        layout.addWidget(logo)

        nav_group = QButtonGroup(page)
        nav_group.setExclusive(True)

        for icon, label, active in _NAV_MAIN:
            btn = _NavButton(icon, label, active)
            nav_group.addButton(btn)
            if label == "History":
                btn.clicked.connect(self._open_history)
            layout.addWidget(btn)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame { color: #1e2235; background: #1e2235; max-height: 1px; }")
        layout.addWidget(sep)
        layout.addSpacing(6)

        for icon, label, active in _NAV_FOOTER:
            btn = _NavButton(icon, label, active)
            nav_group.addButton(btn)
            layout.addWidget(btn)

        layout.addSpacing(12)
        layout.addWidget(self._build_system_info())

        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        header = QWidget()
        header.setStyleSheet("QWidget { background: transparent; }")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        back_btn = QPushButton("←")
        back_btn.setFixedSize(24, 24)
        back_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6c7086; border: none; font-size: 12pt; }"
            "QPushButton:hover { color: #cdd6f4; }"
        )
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))

        title_lbl = QLabel("History")
        title_lbl.setStyleSheet(
            "color: #cdd6f4; font-size: 10pt; font-weight: bold; background: transparent;"
        )

        h_layout.addWidget(back_btn)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame { color: #1e2235; background: #1e2235; max-height: 1px; }")
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._history_list = QWidget()
        self._history_list.setStyleSheet("QWidget { background: transparent; }")
        self._history_list_layout = QVBoxLayout(self._history_list)
        self._history_list_layout.setContentsMargins(0, 0, 0, 0)
        self._history_list_layout.setSpacing(2)

        scroll.setWidget(self._history_list)
        layout.addWidget(scroll)

        return page

    def _build_system_info(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("QWidget { background: transparent; }")
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(10, 8, 10, 4)
        vbox.setSpacing(3)

        for text, style in [
            (_os_info(),   "color: #45475a; font-size: 8pt;"),
            (_username(),  "color: #6c7086; font-size: 9pt;"),
        ]:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"{style} background: transparent;")
            vbox.addWidget(lbl)

        self._cwd_label = QLabel("~")
        self._cwd_label.setWordWrap(True)
        self._cwd_label.setStyleSheet("color: #89b4fa; font-size: 8pt; background: transparent;")
        vbox.addWidget(self._cwd_label)

        return w

    def _open_history(self) -> None:
        self._stack.setCurrentIndex(1)
        self.history_open_requested.emit()

    def show_history(self, blocks: list[Block]) -> None:
        while self._history_list_layout.count() > 0:
            item = self._history_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for block in reversed(blocks):
            cmd_text = block.command.text
            color = "#cdd6f4" if block.exit_code == 0 else "#f38ba8"
            btn = QPushButton(cmd_text)
            btn.setFixedHeight(28)
            btn.setToolTip(cmd_text)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color}; border: none;"
                f" font-family: Monospace; font-size: 8pt; text-align: left; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: #1e2235; color: #cdd6f4; }}"
            )
            btn.clicked.connect(lambda checked, t=cmd_text: self.command_selected.emit(t))
            self._history_list_layout.addWidget(btn)

        self._history_list_layout.addStretch()

    def update_cwd(self, display_path: str) -> None:
        self._cwd_label.setText(display_path)
