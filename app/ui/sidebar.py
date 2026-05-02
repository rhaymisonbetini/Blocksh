import os
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt, Signal


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
    ("≡",  "Histórico",  False),
    ("◇",  "Favoritos",  False),
    ("⊞",  "Projetos",   False),
]

_NAV_FOOTER = [
    ("⚙",  "Configs",    False),
    ("◑",  "Temas",      False),
    ("○",  "Sobre",      False),
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self.setStyleSheet("QWidget { background-color: #10121e; }")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 12)
        layout.setSpacing(2)

        # Logo
        logo = QLabel(">_ Terminator")
        logo.setStyleSheet(
            "color: #cdd6f4; font-family: Monospace; font-size: 11pt;"
            " font-weight: bold; padding: 4px 8px 20px 8px;"
            " background: transparent;"
        )
        layout.addWidget(logo)

        for icon, label, active in _NAV_MAIN:
            layout.addWidget(_NavButton(icon, label, active))

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame { color: #1e2235; background: #1e2235; max-height: 1px; }")
        layout.addWidget(sep)
        layout.addSpacing(6)

        for icon, label, active in _NAV_FOOTER:
            layout.addWidget(_NavButton(icon, label, active))

        layout.addSpacing(12)
        layout.addWidget(self._build_system_info())

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

    def update_cwd(self, display_path: str) -> None:
        self._cwd_label.setText(display_path)
