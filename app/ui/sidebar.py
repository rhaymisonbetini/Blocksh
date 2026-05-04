import os
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QStackedWidget,
    QButtonGroup, QInputDialog, QMenu,
)
from PySide6.QtCore import Qt, Signal

from ..domain.block import Block
from ..domain.favorite import Favorite
from .theme import Palette, ThemeManager


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

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._icon_lbl.setStyleSheet("font-size: 12pt; background: transparent; border: none;")

        self._text_lbl = QLabel(label)
        self._text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._text_lbl.setStyleSheet("font-size: 9pt; background: transparent; border: none;")

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)
        layout.addStretch()

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
                color: {p.fg_muted};
                text-align: left;
            }}
            QPushButton:checked {{
                background-color: {p.bg_active};
                color: {p.fg};
            }}
            QPushButton:hover:!checked {{
                background-color: {p.bg_hover};
                color: {p.fg};
            }}
        """)


class Sidebar(QWidget):
    command_selected          = Signal(str)
    history_open_requested    = Signal()
    theme_selected            = Signal(str)
    favorites_open_requested  = Signal()
    favorite_command_selected = Signal(str)
    favorite_rename_requested = Signal(str, str)  # id, new_name
    favorite_delete_requested = Signal(str)        # id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self._nav_buttons: list[_NavButton] = []
        self._build_ui()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_nav_page())      # 0
        self._stack.addWidget(self._build_history_page())  # 1
        self._stack.addWidget(self._build_themes_page())   # 2
        self._stack.addWidget(self._build_favorites_page()) # 3
        layout.addWidget(self._stack)

    def _build_nav_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 16, 8, 12)
        layout.setSpacing(2)

        self._logo = QLabel(">_ Blocksh")
        self._logo.setStyleSheet(
            "color: #cdd6f4; font-family: Monospace; font-size: 11pt;"
            " font-weight: bold; padding: 4px 8px 20px 8px;"
            " background: transparent;"
        )
        layout.addWidget(self._logo)

        nav_group = QButtonGroup(page)
        nav_group.setExclusive(True)

        for icon, label, active in _NAV_MAIN:
            btn = _NavButton(icon, label, active)
            nav_group.addButton(btn)
            self._nav_buttons.append(btn)
            if label == "History":
                btn.clicked.connect(self._open_history)
            elif label == "Favorites":
                btn.clicked.connect(self._open_favorites)
            layout.addWidget(btn)

        layout.addStretch()

        self._nav_sep = QFrame()
        self._nav_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._nav_sep)
        layout.addSpacing(6)

        for icon, label, active in _NAV_FOOTER:
            btn = _NavButton(icon, label, active)
            nav_group.addButton(btn)
            self._nav_buttons.append(btn)
            if label == "Themes":
                btn.clicked.connect(self._open_themes)
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

        header = self._build_sub_header("History", lambda: self._stack.setCurrentIndex(0))
        layout.addWidget(header)

        self._hist_sep = QFrame()
        self._hist_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._hist_sep)

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

    def _build_themes_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        header = self._build_sub_header("Themes", lambda: self._stack.setCurrentIndex(0))
        layout.addWidget(header)

        self._themes_sep = QFrame()
        self._themes_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._themes_sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._themes_list = QWidget()
        self._themes_list.setStyleSheet("QWidget { background: transparent; }")
        self._themes_list_layout = QVBoxLayout(self._themes_list)
        self._themes_list_layout.setContentsMargins(0, 0, 0, 0)
        self._themes_list_layout.setSpacing(2)

        scroll.setWidget(self._themes_list)
        layout.addWidget(scroll)

        return page

    def _build_favorites_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        header = self._build_sub_header("Favorites", lambda: self._stack.setCurrentIndex(0))
        layout.addWidget(header)

        self._favs_sep = QFrame()
        self._favs_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._favs_sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._favs_list = QWidget()
        self._favs_list.setStyleSheet("QWidget { background: transparent; }")
        self._favs_list_layout = QVBoxLayout(self._favs_list)
        self._favs_list_layout.setContentsMargins(0, 0, 0, 0)
        self._favs_list_layout.setSpacing(2)

        scroll.setWidget(self._favs_list)
        layout.addWidget(scroll)

        return page

    def _build_sub_header(self, title: str, back_fn) -> QWidget:
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
        back_btn.clicked.connect(back_fn)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #cdd6f4; font-size: 10pt; font-weight: bold; background: transparent;"
        )

        h_layout.addWidget(back_btn)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        return header

    def _build_system_info(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("QWidget { background: transparent; }")
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(10, 8, 10, 4)
        vbox.setSpacing(3)

        self._os_lbl = QLabel(_os_info())
        self._os_lbl.setWordWrap(True)
        self._os_lbl.setStyleSheet("color: #45475a; font-size: 8pt; background: transparent;")
        vbox.addWidget(self._os_lbl)

        self._user_lbl = QLabel(_username())
        self._user_lbl.setWordWrap(True)
        self._user_lbl.setStyleSheet("color: #6c7086; font-size: 9pt; background: transparent;")
        vbox.addWidget(self._user_lbl)

        self._cwd_label = QLabel("~")
        self._cwd_label.setWordWrap(True)
        self._cwd_label.setStyleSheet("color: #89b4fa; font-size: 8pt; background: transparent;")
        vbox.addWidget(self._cwd_label)

        return w

    # ── theme application ─────────────────────────────────────────────────────

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(f"QWidget {{ background-color: {p.bg_panel}; }}")
        self._logo.setStyleSheet(
            f"color: {p.fg}; font-family: Monospace; font-size: 11pt;"
            f" font-weight: bold; padding: 4px 8px 20px 8px; background: transparent;"
        )
        sep_style = f"QFrame {{ color: {p.bg_overlay}; background: {p.bg_overlay}; max-height: 1px; }}"
        self._nav_sep.setStyleSheet(sep_style)
        self._hist_sep.setStyleSheet(sep_style)
        self._themes_sep.setStyleSheet(sep_style)
        self._favs_sep.setStyleSheet(sep_style)
        self._os_lbl.setStyleSheet(f"color: {p.fg_dim}; font-size: 8pt; background: transparent;")
        self._user_lbl.setStyleSheet(f"color: {p.fg_muted}; font-size: 9pt; background: transparent;")
        self._cwd_label.setStyleSheet(f"color: {p.blue}; font-size: 8pt; background: transparent;")
        for btn in self._nav_buttons:
            btn.apply_theme(p)
        self._refresh_themes_list(p)

    # ── navigation ────────────────────────────────────────────────────────────

    def _open_history(self) -> None:
        self._stack.setCurrentIndex(1)
        self.history_open_requested.emit()

    def _open_favorites(self) -> None:
        self._stack.setCurrentIndex(3)
        self.favorites_open_requested.emit()

    def _open_themes(self) -> None:
        self._refresh_themes_list(ThemeManager.instance().current)
        self._stack.setCurrentIndex(2)

    def _refresh_themes_list(self, p: Palette) -> None:
        while self._themes_list_layout.count() > 0:
            item = self._themes_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_name = ThemeManager.instance().current.name
        for theme in ThemeManager.instance().all_themes():
            is_active = theme.name == current_name
            prefix = "●" if is_active else "○"
            color = p.fg if is_active else p.fg_muted
            btn = QPushButton(f"{prefix}  {theme.name}")
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color}; border: none;"
                f" font-family: Monospace; font-size: 9pt; text-align: left; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {p.bg_overlay}; color: {p.fg}; }}"
            )
            btn.clicked.connect(lambda checked, n=theme.name: self._on_theme_clicked(n))
            self._themes_list_layout.addWidget(btn)

        self._themes_list_layout.addStretch()

    def _on_theme_clicked(self, name: str) -> None:
        self.theme_selected.emit(name)

    # ── public API ────────────────────────────────────────────────────────────

    def show_history(self, blocks: list[Block]) -> None:
        p = ThemeManager.instance().current
        while self._history_list_layout.count() > 0:
            item = self._history_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for block in reversed(blocks):
            cmd_text = block.command.text
            color = p.fg if block.exit_code == 0 else p.red
            btn = QPushButton(cmd_text)
            btn.setFixedHeight(28)
            btn.setToolTip(cmd_text)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color}; border: none;"
                f" font-family: Monospace; font-size: 8pt; text-align: left; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {p.bg_overlay}; color: {p.fg}; }}"
            )
            btn.clicked.connect(lambda checked, t=cmd_text: self.command_selected.emit(t))
            self._history_list_layout.addWidget(btn)

        self._history_list_layout.addStretch()

    def show_favorites(self, favorites: list[Favorite]) -> None:
        p = ThemeManager.instance().current
        while self._favs_list_layout.count() > 0:
            item = self._favs_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not favorites:
            empty = QLabel("No favorites yet\nUse ⋮ on any command block")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {p.fg_dim}; font-size: 8pt; background: transparent; padding: 16px 8px;"
            )
            self._favs_list_layout.addWidget(empty)
            self._favs_list_layout.addStretch()
            return

        for fav in favorites:
            row = self._build_favorite_row(fav, p)
            self._favs_list_layout.addWidget(row)

        self._favs_list_layout.addStretch()

    def _build_favorite_row(self, fav: Favorite, p: Palette) -> QWidget:
        row = QWidget()
        row.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        name_lbl = QLabel(fav.name)
        name_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: 9pt; font-weight: bold; background: transparent;"
        )
        layout.addWidget(name_lbl)

        cmd_btn = QPushButton(fav.command_text)
        cmd_btn.setFixedHeight(22)
        cmd_btn.setToolTip(fav.command_text)
        cmd_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none;"
            f" font-family: Monospace; font-size: 8pt; text-align: left; padding: 0 4px; }}"
            f"QPushButton:hover {{ background: {p.bg_overlay}; color: {p.fg}; }}"
        )
        cmd_btn.clicked.connect(
            lambda checked, t=fav.command_text: self.favorite_command_selected.emit(t)
        )
        layout.addWidget(cmd_btn)

        row.setContextMenuPolicy(Qt.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, f=fav: self._show_favorite_menu(f)
        )

        return row

    def _show_favorite_menu(self, fav: Favorite) -> None:
        p = ThemeManager.instance().current
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {p.bg_selected}; }}"
        )

        def _rename():
            name, ok = QInputDialog.getText(self, "Rename Favorite", "New name:", text=fav.name)
            if ok and name.strip():
                self.favorite_rename_requested.emit(fav.id, name.strip())

        menu.addAction("Rename", _rename)
        menu.addAction("Delete", lambda: self.favorite_delete_requested.emit(fav.id))
        menu.exec(self.cursor().pos())

    def update_cwd(self, display_path: str) -> None:
        self._cwd_label.setText(display_path)
