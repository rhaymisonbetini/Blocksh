import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal, Qt, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap

from .theme import Palette, ThemeManager, TY


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
        self.setObjectName("TabItem")
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._active = False
        self._env_tag: QLabel | None = None
        self._build_ui(title)
        self._update_style()

    def _build_ui(self, title: str):
        p = ThemeManager.instance().current
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(6)

        self._lbl = QLabel(title)
        self._lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._lbl.setStyleSheet(
            f"color: {p.fg_muted}; font-size: {TY.lg}pt; background: transparent; border: none;"
        )

        self._env_tag = QLabel("● Local")
        self._env_tag.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._env_tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._env_tag.setStyleSheet(
            f"color: {p.tag_local_fg}; background: {p.tag_local_bg};"
            f" border-radius: 8px; padding: 1px 6px; font-size: {TY.base}pt;"
        )

        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(18, 18)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_dim}; border: none; font-size: {TY.md}pt; }}"
            f"QPushButton:hover {{ color: {p.red_ui}; }}"
        )
        self._close_btn.clicked.connect(self.close_clicked)

        layout.addWidget(self._lbl)
        layout.addWidget(self._env_tag)
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
            f"color: {color}; font-size: {TY.lg}pt; background: transparent; border: none;"
        )
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_dim}; border: none; font-size: {TY.md}pt; }}"
            f"QPushButton:hover {{ color: {p.red_ui}; }}"
        )
        if self._env_tag:
            self._env_tag.setStyleSheet(
                f"color: {p.tag_local_fg}; background: {p.tag_local_bg};"
                f" border-radius: 8px; padding: 1px 6px; font-size: {TY.base}pt;"
            )
        self._update_style()

    def _update_style(self):
        p = ThemeManager.instance().current
        bg = p.bg_overlay if self._active else "transparent"
        self.setStyleSheet(f"QWidget#TabItem {{ background: {bg}; border-radius: 16px; }}")


class TabBar(QWidget):
    tab_add_requested      = Signal()
    tab_close_requested    = Signal(int)
    tab_switched           = Signal(int)
    search_requested       = Signal()
    collapse_all_requested = Signal()
    settings_requested     = Signal()
    split_h_requested      = Signal()
    split_v_requested      = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._tabs: list[_Tab] = []
        self._build_ui()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

        from ..services.settings_service import SettingsService
        SettingsService.instance().settings_changed.connect(lambda _s: self._refresh_avatar())

    def _build_ui(self):
        from PySide6.QtWidgets import QFrame
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Tab strip (takes remaining space)
        self._tab_strip = QWidget()
        self._tab_strip.setStyleSheet("QWidget { background: transparent; }")
        self._tab_layout = QHBoxLayout(self._tab_strip)
        self._tab_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_layout.setSpacing(4)
        self._tab_layout.addStretch(1)   # tabs insert before this; keeps them left-aligned
        layout.addWidget(self._tab_strip, 1)

        # Separator before action cluster
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.VLine)
        self._sep.setFixedWidth(1)
        self._sep.setFixedHeight(20)
        layout.addWidget(self._sep, 0, Qt.AlignVCenter)

        # Action cluster
        self._add_btn = QPushButton("+ New Tab")
        self._add_btn.setFixedHeight(34)
        self._add_btn.clicked.connect(self.tab_add_requested)
        layout.addWidget(self._add_btn)

        self._split_h_btn = QPushButton("Split")
        self._split_h_btn.setFixedHeight(34)
        self._split_h_btn.setToolTip("Split pane right (Ctrl+Shift+\\)")
        self._split_h_btn.clicked.connect(self.split_h_requested)
        layout.addWidget(self._split_h_btn)

        self._split_v_btn = QPushButton("↕")
        self._split_v_btn.setFixedHeight(34)
        self._split_v_btn.setToolTip("Split pane down (Ctrl+Shift+-)")
        self._split_v_btn.clicked.connect(self.split_v_requested)
        layout.addWidget(self._split_v_btn)

        self._collapse_btn = QPushButton("⊟")
        self._collapse_btn.setFixedHeight(34)
        self._collapse_btn.setToolTip("Collapse / expand all blocks")
        self._collapse_btn.clicked.connect(self.collapse_all_requested)
        layout.addWidget(self._collapse_btn)

        self._search_btn = QPushButton("⌕")
        self._search_btn.setFixedHeight(34)
        self._search_btn.clicked.connect(self.search_requested)
        layout.addWidget(self._search_btn)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedHeight(34)
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self._settings_btn)

        self._avatar_btn = QPushButton()
        self._avatar_btn.setFixedSize(34, 34)
        self._avatar_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self._avatar_btn)
        self._refresh_avatar()

    def _refresh_avatar(self) -> None:
        from ..services.settings_service import SettingsService
        s = SettingsService.instance().get()
        pix = _make_circular_pixmap(s.avatar_path, 30, _username())
        if s.avatar_path:
            self._avatar_btn.setIcon(QIcon(pix))
            self._avatar_btn.setIconSize(QSize(30, 30))
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
                f" border-radius: 14px; font-weight: bold; font-size: {TY.base}pt; }}"
                f"QPushButton:hover {{ background: {p.cyan}; }}"
            )

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(f"QWidget {{ background-color: {p.bg_panel}; }}")
        self._sep.setStyleSheet(f"background: {p.border}; color: {p.border};")
        action_style = (
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg_muted}; border: none;"
            f" border-radius: 6px; font-size: {TY.lg}pt; padding: 0 10px; }}"
            f"QPushButton:hover {{ background: {p.bg_hover2}; color: {p.fg}; }}"
        )
        self._add_btn.setStyleSheet(action_style)
        self._split_h_btn.setStyleSheet(action_style)
        self._split_v_btn.setStyleSheet(action_style)
        self._collapse_btn.setStyleSheet(action_style)
        self._search_btn.setStyleSheet(action_style)
        self._settings_btn.setStyleSheet(action_style)
        self._refresh_avatar()
        for tab in self._tabs:
            tab.apply_theme(p)

    def add_tab(self, title: str) -> int:
        tab = _Tab(title)
        tab.apply_theme(ThemeManager.instance().current)
        tab.tab_clicked.connect(lambda t=tab: self._on_tab_clicked(t))
        tab.close_clicked.connect(lambda t=tab: self._on_tab_close(t))
        self._tabs.append(tab)
        # Insert before the trailing stretch (always last item in the layout)
        self._tab_layout.insertWidget(self._tab_layout.count() - 1, tab)
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
