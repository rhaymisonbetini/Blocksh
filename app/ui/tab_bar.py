import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap

from .theme import Palette, ThemeManager


def _make_circular_pixmap(path: str, size: int, username: str) -> QPixmap:
    result = QPixmap(size, size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(QRectF(0, 0, size, size))
    painter.setClipPath(clip)

    src = QPixmap(path) if path else QPixmap()
    if not src.isNull():
        src = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (src.width() - size) // 2
        y = (src.height() - size) // 2
        painter.drawPixmap(0, 0, src, x, y, size, size)
    else:
        painter.setBrush(QColor("#313244"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(0, 0, size, size))
        painter.setPen(QColor("#89b4fa"))
        font = QFont()
        font.setPixelSize(size // 2)
        font.setBold(True)
        painter.setFont(font)
        initial = username[0].upper() if username else "U"
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)

    painter.end()
    return result


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

        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(16, 16)
        self._close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #45475a; border: none; font-size: 12pt; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        self._close_btn.clicked.connect(self.close_clicked)

        layout.addWidget(self._lbl)
        layout.addWidget(self._close_btn)

    def mousePressEvent(self, event):
        self.tab_clicked.emit()
        super().mousePressEvent(event)

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self._update_style()

    def set_title(self, title: str) -> None:
        self._lbl.setText(title)

    def apply_theme(self, p: Palette) -> None:
        color = p.fg if self._active else p.fg_muted
        self._lbl.setStyleSheet(
            f"color: {color}; font-size: 9pt; background: transparent; border: none;"
        )
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_dim}; border: none; font-size: 12pt; }}"
            f"QPushButton:hover {{ color: {p.red_ui}; }}"
        )
        self._update_style()

    def _update_style(self):
        p = ThemeManager.instance().current
        bg = p.bg_overlay if self._active else "transparent"
        self.setStyleSheet(f"QWidget {{ background: {bg}; border-radius: 6px; }}")


class TabBar(QWidget):
    tab_add_requested      = Signal()
    tab_close_requested    = Signal(int)
    tab_switched           = Signal(int)
    search_requested       = Signal()
    collapse_all_requested = Signal()
    settings_requested     = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._tabs: list[_Tab] = []
        self._build_ui()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

        from ..services.settings_service import SettingsService
        SettingsService.instance().settings_changed.connect(lambda _s: self._refresh_avatar())

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(28, 28)
        self._add_btn.clicked.connect(self.tab_add_requested)
        layout.addWidget(self._add_btn)

        self._tab_strip = QWidget()
        self._tab_strip.setStyleSheet("QWidget { background: transparent; }")
        self._tab_layout = QHBoxLayout(self._tab_strip)
        self._tab_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_layout.setSpacing(4)
        layout.addWidget(self._tab_strip, 1)

        self._search_btn = QPushButton("⌕")
        self._search_btn.setFixedSize(28, 28)
        self._search_btn.clicked.connect(self.search_requested)
        layout.addWidget(self._search_btn)

        self._collapse_btn = QPushButton("⊟")
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.setToolTip("Collapse / expand all blocks")
        self._collapse_btn.clicked.connect(self.collapse_all_requested)
        layout.addWidget(self._collapse_btn)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(28, 28)
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self._settings_btn)

        self._avatar_btn = QPushButton()
        self._avatar_btn.setFixedSize(28, 28)
        self._avatar_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self._avatar_btn)
        self._refresh_avatar()

    def _refresh_avatar(self) -> None:
        from ..services.settings_service import SettingsService
        s = SettingsService.instance().get()
        pix = _make_circular_pixmap(s.avatar_path, 26, _username())
        if s.avatar_path:
            self._avatar_btn.setIcon(QIcon(pix))
            self._avatar_btn.setIconSize(QSize(26, 26))
            self._avatar_btn.setText("")
            self._avatar_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 14px; }"
                "QPushButton:hover { background: rgba(255,255,255,0.08); }"
            )
        else:
            self._avatar_btn.setIcon(QIcon())
            self._avatar_btn.setText(_username()[:2].upper())
            p = ThemeManager.instance().current
            self._avatar_btn.setStyleSheet(
                f"QPushButton {{ background: {p.blue}; color: {p.bg}; border: none;"
                f" border-radius: 14px; font-weight: bold; font-size: 8pt; }}"
                f"QPushButton:hover {{ background: {p.cyan}; }}"
            )

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(f"QWidget {{ background-color: {p.bg_panel}; }}")
        self._add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg_muted}; border: none;"
            f" border-radius: 6px; font-size: 14pt; }}"
            f"QPushButton:hover {{ background: {p.bg_hover2}; color: {p.fg}; }}"
        )
        icon_style = (
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none;"
            f" border-radius: 6px; font-size: 13pt; }}"
            f"QPushButton:hover {{ background: {p.bg_overlay}; color: {p.fg}; }}"
        )
        self._search_btn.setStyleSheet(icon_style)
        self._collapse_btn.setStyleSheet(icon_style)
        self._settings_btn.setStyleSheet(icon_style)
        self._refresh_avatar()
        for tab in self._tabs:
            tab.apply_theme(p)

    def add_tab(self, title: str) -> int:
        tab = _Tab(title)
        tab.apply_theme(ThemeManager.instance().current)
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
