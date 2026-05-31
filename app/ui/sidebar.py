import os
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QStackedWidget,
    QButtonGroup, QInputDialog, QMenu,
)
from PySide6.QtCore import Qt, Signal, QEasingCurve, QPropertyAnimation, QTimer

from ..domain.block import Block
from ..domain.favorite import Favorite
from ..domain.project import Project
from ..domain.ssh_connection import SshConnection
from ..domain.workflow import Workflow
from .theme import Palette, ThemeManager, get_mono_font, TY

_TYPE_COLORS: dict[str, str] = {
    "git":     "#89b4fa",
    "node":    "#a6e3a1",
    "php":     "#cba6f7",
    "python":  "#f9e2af",
    "rust":    "#fab387",
    "go":      "#89dceb",
    "generic": "#6c7086",
}


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
    ("⌁",  "SSH",        False),
    ("▶",  "Workflows",  False),
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
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._icon_lbl.setStyleSheet(f"font-size: {TY.md}px; background: transparent; border: none;")

        self._text_lbl = QLabel(label)
        self._text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._text_lbl.setStyleSheet(f"font-size: {TY.base}px; background: transparent; border: none;")

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)
        layout.addStretch()

    def set_collapsed(self, collapsed: bool) -> None:
        self._text_lbl.setVisible(not collapsed)
        lay = self.layout()
        if collapsed:
            lay.setContentsMargins(0, 0, 0, 0)
            self._icon_lbl.setMinimumWidth(48)
            self._icon_lbl.setAlignment(Qt.AlignCenter)
            self.setToolTip(self._text_lbl.text())
        else:
            lay.setContentsMargins(12, 0, 12, 0)
            self._icon_lbl.setMinimumWidth(0)
            self._icon_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setToolTip("")

    def apply_theme(self, p: Palette) -> None:
        self._icon_lbl.setStyleSheet(f"font-size: {TY.md}px; background: transparent; border: none;")
        self._text_lbl.setStyleSheet(f"font-size: {TY.base}px; background: transparent; border: none;")
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
                border-left: 3px solid {p.blue};
                border-radius: 0px 6px 6px 0px;
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
    favorite_rename_requested = Signal(str, str)         # id, new_name
    favorite_delete_requested = Signal(str)               # id
    favorite_edit_requested   = Signal(str, str, str, str) # id, name, command_text, cwd
    favorite_add_requested    = Signal(str, str, str)      # name, command_text, cwd
    projects_open_requested   = Signal()
    project_selected          = Signal(str)        # path → cd <path>
    project_add_requested     = Signal()           # add current directory
    project_rename_requested  = Signal(str, str)   # id, new_name
    project_delete_requested  = Signal(str)        # id
    settings_requested        = Signal()
    terminal_requested        = Signal()
    ssh_open_requested        = Signal()
    ssh_connect_requested     = Signal(str)        # conn_id
    ssh_add_requested         = Signal()
    ssh_edit_requested        = Signal(str)        # conn_id
    ssh_delete_requested      = Signal(str)        # conn_id
    workflows_open_requested  = Signal()
    workflow_run_requested    = Signal(str)        # workflow_id
    workflow_add_requested    = Signal()
    workflow_edit_requested   = Signal(str)        # workflow_id
    workflow_delete_requested = Signal(str)        # workflow_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(52)
        self._collapsed = True
        self._nav_buttons: list[_NavButton] = []
        self._build_ui()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    def _build_ui(self):
        self._sub_back_btns: list = []
        self._sub_title_lbls: list = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_nav_page())         # 0
        self._stack.addWidget(self._build_history_page())    # 1
        self._stack.addWidget(self._build_themes_page())     # 2
        self._stack.addWidget(self._build_favorites_page())  # 3
        self._stack.addWidget(self._build_projects_page())   # 4
        self._stack.addWidget(self._build_ssh_page())        # 5
        self._stack.addWidget(self._build_workflows_page())  # 6
        self._stack.addWidget(self._build_about_page())      # 7
        layout.addWidget(self._stack)

    def _build_nav_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 10, 4, 12)
        layout.setSpacing(2)

        nav_group = QButtonGroup(page)
        nav_group.setExclusive(True)

        for icon, label, active in _NAV_MAIN:
            btn = _NavButton(icon, label, active)
            btn.set_collapsed(True)
            nav_group.addButton(btn)
            self._nav_buttons.append(btn)
            if label == "Terminal":
                btn.clicked.connect(self.terminal_requested.emit)
            elif label == "History":
                btn.clicked.connect(self._open_history)
            elif label == "Favorites":
                btn.clicked.connect(self._open_favorites)
            elif label == "Projects":
                btn.clicked.connect(self._open_projects)
            elif label == "SSH":
                btn.clicked.connect(self._open_ssh)
            elif label == "Workflows":
                btn.clicked.connect(self._open_workflows)
            layout.addWidget(btn)

        layout.addStretch()

        self._nav_sep = QFrame()
        self._nav_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._nav_sep)
        layout.addSpacing(6)

        for icon, label, active in _NAV_FOOTER:
            btn = _NavButton(icon, label, active)
            btn.set_collapsed(True)
            nav_group.addButton(btn)
            self._nav_buttons.append(btn)
            if label == "Themes":
                btn.clicked.connect(self._open_themes)
            elif label == "Settings":
                btn.clicked.connect(self._open_settings)
            elif label == "About":
                btn.clicked.connect(self._open_about)
            layout.addWidget(btn)

        layout.addSpacing(12)
        self._sys_info_widget = self._build_system_info()
        self._sys_info_widget.setVisible(False)
        layout.addWidget(self._sys_info_widget)

        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        header = self._build_sub_header("History", self._back_to_nav)
        layout.addWidget(header)

        self._hist_sep = QFrame()
        self._hist_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._hist_sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._history_list = QWidget()
        self._history_list.setStyleSheet("QWidget { background: transparent; }")
        self._history_list_layout = QVBoxLayout(self._history_list)
        self._history_list_layout.setContentsMargins(0, 0, 0, 0)
        self._history_list_layout.setSpacing(2)

        scroll.setWidget(self._history_list)
        layout.addWidget(scroll)
        self._history_scroll = scroll

        return page

    def _build_themes_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        header = self._build_sub_header("Themes", self._back_to_nav)
        layout.addWidget(header)

        self._themes_sep = QFrame()
        self._themes_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._themes_sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._themes_list = QWidget()
        self._themes_list.setStyleSheet("QWidget { background: transparent; }")
        self._themes_list_layout = QVBoxLayout(self._themes_list)
        self._themes_list_layout.setContentsMargins(0, 0, 0, 0)
        self._themes_list_layout.setSpacing(2)

        scroll.setWidget(self._themes_list)
        layout.addWidget(scroll)
        self._themes_scroll = scroll

        return page

    def _build_favorites_page(self) -> QWidget:
        p = ThemeManager.instance().current
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        header_widget = QWidget()
        header_widget.setStyleSheet("QWidget { background: transparent; }")
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(4)

        self._favs_back_btn = QPushButton("←")
        self._favs_back_btn.setFixedSize(24, 24)
        self._favs_back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._favs_back_btn.clicked.connect(self._back_to_nav)
        back_btn = self._favs_back_btn

        self._favs_title_lbl = QLabel("Favorites")
        self._favs_title_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: {TY.md}px; font-weight: bold; background: transparent;"
        )
        title_lbl = self._favs_title_lbl

        self._favs_add_btn = QPushButton("+")
        self._favs_add_btn.setFixedSize(22, 22)
        self._favs_add_btn.setToolTip("Add favorite")
        self._favs_add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._favs_add_btn.clicked.connect(self._open_add_favorite)

        h_layout.addWidget(back_btn)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        h_layout.addWidget(self._favs_add_btn)
        layout.addWidget(header_widget)

        self._favs_sep = QFrame()
        self._favs_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._favs_sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._favs_list = QWidget()
        self._favs_list.setStyleSheet("QWidget { background: transparent; }")
        self._favs_list_layout = QVBoxLayout(self._favs_list)
        self._favs_list_layout.setContentsMargins(0, 0, 0, 0)
        self._favs_list_layout.setSpacing(2)

        scroll.setWidget(self._favs_list)
        layout.addWidget(scroll)
        self._favs_scroll = scroll

        return page

    def _build_projects_page(self) -> QWidget:
        p = ThemeManager.instance().current
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        # Header with back + title + add button
        header_widget = QWidget()
        header_widget.setStyleSheet("QWidget { background: transparent; }")
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(4)

        self._proj_back_btn = QPushButton("←")
        self._proj_back_btn.setFixedSize(24, 24)
        self._proj_back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._proj_back_btn.clicked.connect(self._back_to_nav)
        back_btn = self._proj_back_btn

        self._proj_title_lbl = QLabel("Projects")
        self._proj_title_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: {TY.md}px; font-weight: bold; background: transparent;"
        )
        title_lbl = self._proj_title_lbl

        self._proj_add_btn = QPushButton("+")
        self._proj_add_btn.setFixedSize(22, 22)
        self._proj_add_btn.setToolTip("Add current directory")
        self._proj_add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._proj_add_btn.clicked.connect(self.project_add_requested)

        h_layout.addWidget(back_btn)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        h_layout.addWidget(self._proj_add_btn)
        layout.addWidget(header_widget)

        self._projs_sep = QFrame()
        self._projs_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._projs_sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._projs_list = QWidget()
        self._projs_list.setStyleSheet("QWidget { background: transparent; }")
        self._projs_list_layout = QVBoxLayout(self._projs_list)
        self._projs_list_layout.setContentsMargins(0, 0, 0, 0)
        self._projs_list_layout.setSpacing(4)

        scroll.setWidget(self._projs_list)
        layout.addWidget(scroll)
        self._projs_scroll = scroll

        self._expanded_projects: set[str] = set()

        return page

    def _build_ssh_page(self) -> QWidget:
        p = ThemeManager.instance().current
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        header_widget = QWidget()
        header_widget.setStyleSheet("QWidget { background: transparent; }")
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(4)

        self._ssh_back_btn = QPushButton("←")
        self._ssh_back_btn.setFixedSize(24, 24)
        self._ssh_back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._ssh_back_btn.clicked.connect(self._back_to_nav)
        back_btn = self._ssh_back_btn

        self._ssh_title_lbl = QLabel("SSH")
        self._ssh_title_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: {TY.md}px; font-weight: bold; background: transparent;"
        )
        title_lbl = self._ssh_title_lbl

        self._ssh_add_btn = QPushButton("+")
        self._ssh_add_btn.setFixedSize(22, 22)
        self._ssh_add_btn.setToolTip("Add SSH connection")
        self._ssh_add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._ssh_add_btn.clicked.connect(self.ssh_add_requested)

        h_layout.addWidget(back_btn)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        h_layout.addWidget(self._ssh_add_btn)
        layout.addWidget(header_widget)

        self._ssh_sep = QFrame()
        self._ssh_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._ssh_sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._ssh_list = QWidget()
        self._ssh_list.setStyleSheet("QWidget { background: transparent; }")
        self._ssh_list_layout = QVBoxLayout(self._ssh_list)
        self._ssh_list_layout.setContentsMargins(0, 0, 0, 0)
        self._ssh_list_layout.setSpacing(4)

        scroll.setWidget(self._ssh_list)
        layout.addWidget(scroll)
        self._ssh_scroll = scroll

        return page

    def _build_workflows_page(self) -> QWidget:
        p = ThemeManager.instance().current
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        header_widget = QWidget()
        header_widget.setStyleSheet("QWidget { background: transparent; }")
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(4)

        self._wf_back_btn = QPushButton("←")
        self._wf_back_btn.setFixedSize(24, 24)
        self._wf_back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._wf_back_btn.clicked.connect(self._back_to_nav)
        back_btn = self._wf_back_btn

        self._wf_title_lbl = QLabel("Workflows")
        self._wf_title_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: {TY.md}px; font-weight: bold; background: transparent;"
        )
        title_lbl = self._wf_title_lbl

        self._wf_add_btn = QPushButton("+")
        self._wf_add_btn.setFixedSize(22, 22)
        self._wf_add_btn.setToolTip("New workflow")
        self._wf_add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        self._wf_add_btn.clicked.connect(self.workflow_add_requested)

        h_layout.addWidget(back_btn)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        h_layout.addWidget(self._wf_add_btn)
        layout.addWidget(header_widget)

        self._wf_sep = QFrame()
        self._wf_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._wf_sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._wf_list = QWidget()
        self._wf_list.setStyleSheet("QWidget { background: transparent; }")
        self._wf_list_layout = QVBoxLayout(self._wf_list)
        self._wf_list_layout.setContentsMargins(0, 0, 0, 0)
        self._wf_list_layout.setSpacing(4)

        scroll.setWidget(self._wf_list)
        layout.addWidget(scroll)
        self._wf_scroll = scroll

        return page

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        header = self._build_sub_header("About", self._back_to_nav)
        layout.addWidget(header)

        self._about_sep = QFrame()
        self._about_sep.setFrameShape(QFrame.HLine)
        layout.addWidget(self._about_sep)

        p = ThemeManager.instance().current

        logo_lbl = QLabel(f'<b style="color:{p.blue}">&gt;_</b> Blocksh')
        logo_lbl.setTextFormat(Qt.RichText)
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: {TY.md}px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(logo_lbl)

        version_lbl = QLabel("v0.9.0")
        version_lbl.setAlignment(Qt.AlignCenter)
        version_lbl.setStyleSheet(
            f"color: {p.accent}; font-size: {TY.md}px; background: transparent;"
        )
        layout.addWidget(version_lbl)

        desc_lbl = QLabel(
            "A Warp-inspired, block-based terminal emulator with full PTY support, "
            "SSH manager, command workflows, split panes, and a streaming AI assistant."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setStyleSheet(
            f"color: {p.fg_muted}; font-size: {TY.base}px; background: transparent;"
        )
        layout.addWidget(desc_lbl)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color: {p.bg_overlay}; background: {p.bg_overlay}; max-height: 1px;")
        layout.addWidget(sep2)

        for label, value in [
            ("Stack",    "Python 3.10 + PySide6"),
            ("Theme",    "Catppuccin Mocha/Latte"),
            ("Storage",  "SQLite (~/.blocksh/)"),
            ("PTY",      "pyte + QThread"),
        ]:
            row = QWidget()
            row.setStyleSheet("QWidget { background: transparent; }")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 0, 4, 0)
            rl.setSpacing(6)
            k = QLabel(label)
            k.setStyleSheet(f"color: {p.fg_dim}; font-size: {TY.base}px; background: transparent;")
            v = QLabel(value)
            v.setStyleSheet(f"color: {p.fg_muted}; font-size: {TY.base}px; background: transparent;")
            rl.addWidget(k)
            rl.addStretch()
            rl.addWidget(v)
            layout.addWidget(row)

        layout.addStretch()

        import webbrowser

        gh_btn = QPushButton("⎋  GitHub")
        gh_btn.setFixedHeight(30)
        gh_btn.setStyleSheet(
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg_muted};"
            f" border: 1px solid {p.border}; border-radius: 8px; font-size: {TY.base}px; }}"
            f"QPushButton:hover {{ background: {p.bg_hover}; color: {p.fg}; }}"
        )
        gh_btn.clicked.connect(
            lambda: webbrowser.open("https://github.com/rhaymisonbetini/Blocksh")
        )
        layout.addWidget(gh_btn)

        author_lbl = QLabel("Made with ♥ by rhaymisonbetini")
        author_lbl.setAlignment(Qt.AlignCenter)
        author_lbl.setStyleSheet(
            f"color: {p.fg_dim}; font-size: {TY.sm}px; background: transparent;"
        )
        layout.addWidget(author_lbl)

        return page

    def _build_sub_header(self, title: str, back_fn) -> QWidget:
        p = ThemeManager.instance().current
        header = QWidget()
        header.setStyleSheet("QWidget { background: transparent; }")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        back_btn = QPushButton("←")
        back_btn.setFixedSize(24, 24)
        back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        back_btn.clicked.connect(back_fn)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: {TY.md}px; font-weight: bold; background: transparent;"
        )

        h_layout.addWidget(back_btn)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()

        self._sub_back_btns.append(back_btn)
        self._sub_title_lbls.append(title_lbl)
        return header

    def _build_system_info(self) -> QWidget:
        p = ThemeManager.instance().current
        w = QWidget()
        w.setStyleSheet("QWidget { background: transparent; }")
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(10, 8, 10, 4)
        vbox.setSpacing(2)

        self._info_lbl = QLabel(f"● {_username()}")
        self._info_lbl.setWordWrap(False)
        self._info_lbl.setToolTip(_os_info())
        self._info_lbl.setStyleSheet(f"color: {p.fg_muted}; font-size: {TY.sm}px; background: transparent;")
        vbox.addWidget(self._info_lbl)

        self._cwd_label = QLabel("~")
        self._cwd_label.setWordWrap(True)
        self._cwd_label.setStyleSheet(f"color: {p.blue}; font-size: {TY.xs}px; background: transparent;")
        vbox.addWidget(self._cwd_label)

        # Kept for backward compat — no longer displayed
        self._os_lbl = QLabel()
        self._os_lbl.setVisible(False)
        self._user_lbl = QLabel()
        self._user_lbl.setVisible(False)

        return w

    # ── theme application ─────────────────────────────────────────────────────

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(f"QWidget {{ background-color: {p.bg_panel}; }}")
        sep_style = f"QFrame {{ color: {p.bg_overlay}; background: {p.bg_overlay}; max-height: 1px; }}"
        self._nav_sep.setStyleSheet(sep_style)
        self._hist_sep.setStyleSheet(sep_style)
        self._themes_sep.setStyleSheet(sep_style)
        self._favs_sep.setStyleSheet(sep_style)
        self._projs_sep.setStyleSheet(sep_style)
        self._ssh_sep.setStyleSheet(sep_style)
        self._wf_sep.setStyleSheet(sep_style)
        self._about_sep.setStyleSheet(sep_style)
        self._info_lbl.setStyleSheet(f"color: {p.fg_muted}; font-size: {TY.sm}px; background: transparent;")
        self._cwd_label.setStyleSheet(f"color: {p.blue}; font-size: {TY.xs}px; background: transparent;")
        for btn in self._nav_buttons:
            btn.apply_theme(p)

        _back_style = (
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.base}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        _title_style = (
            f"color: {p.fg}; font-size: {TY.md}px; font-weight: bold; background: transparent;"
        )
        _add_style = (
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        for btn in getattr(self, '_sub_back_btns', []):
            btn.setStyleSheet(_back_style)
        for lbl in getattr(self, '_sub_title_lbls', []):
            lbl.setStyleSheet(_title_style)
        for attr in ('_favs_back_btn', '_proj_back_btn', '_ssh_back_btn', '_wf_back_btn'):
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(_back_style)
        for attr in ('_favs_title_lbl', '_proj_title_lbl', '_ssh_title_lbl', '_wf_title_lbl'):
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(_title_style)
        for attr in ('_favs_add_btn', '_proj_add_btn', '_ssh_add_btn', '_wf_add_btn'):
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(_add_style)

        self._refresh_themes_list(p)

    # ── collapse / expand (automatic, no manual toggle) ──────────────────────

    def _back_to_nav(self) -> None:
        """Return to icon-only nav, collapsing the sidebar."""
        self._stack.setCurrentIndex(0)
        self._set_collapsed(True)

    def _set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        target_w = 52 if collapsed else 210

        for btn in self._nav_buttons:
            btn.set_collapsed(collapsed)

        self.setMinimumWidth(0)
        self._anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._anim.setDuration(150)
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target_w)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        if collapsed:
            self._info_lbl.setVisible(False)
            self._cwd_label.setVisible(False)
            self._sys_info_widget.setVisible(False)
            self._anim.finished.connect(lambda: self.setFixedWidth(52))
        else:
            def _on_done():
                self.setFixedWidth(target_w)
                self._info_lbl.setVisible(True)
                self._cwd_label.setVisible(True)
                self._sys_info_widget.setVisible(True)
            self._anim.finished.connect(_on_done)

        self._anim.start()

    def _expand_to(self, page_index: int) -> None:
        """Switch to sub-page and expand sidebar if currently collapsed."""
        self._stack.setCurrentIndex(page_index)
        if self._collapsed:
            self._set_collapsed(False)

    # ── navigation ────────────────────────────────────────────────────────────

    def _open_history(self) -> None:
        self._expand_to(1)
        self.history_open_requested.emit()

    def _open_favorites(self) -> None:
        self._expand_to(3)
        self.favorites_open_requested.emit()

    def _open_projects(self) -> None:
        self._expand_to(4)
        self.projects_open_requested.emit()

    def _open_themes(self) -> None:
        self._refresh_themes_list(ThemeManager.instance().current)
        self._expand_to(2)

    def _open_settings(self) -> None:
        self.settings_requested.emit()

    def _open_ssh(self) -> None:
        self._expand_to(5)
        self.ssh_open_requested.emit()

    def _open_workflows(self) -> None:
        self._expand_to(6)
        self.workflows_open_requested.emit()

    def _open_about(self) -> None:
        self._expand_to(7)

    @staticmethod
    def _make_list_widget(spacing: int = 2) -> tuple["QWidget", "QVBoxLayout"]:
        w = QWidget()
        w.setStyleSheet("QWidget { background: transparent; }")
        w.setMaximumWidth(164)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(spacing)
        return w, lay

    def _swap_scroll_widget(self, scroll: "QScrollArea", new_widget: "QWidget",
                            row_h: int, n_rows: int) -> None:
        """Force layout on new_widget while standalone, then swap it into scroll."""
        vp_w = scroll.viewport().width()
        new_widget.resize(vp_w if vp_w > 0 else 164, max(1, n_rows) * row_h)
        scroll.setWidget(new_widget)   # Qt deletes the old content widget

    def _refresh_themes_list(self, p: Palette) -> None:
        all_themes = ThemeManager.instance().all_themes()
        new_list, new_layout = self._make_list_widget(spacing=2)
        current_name = ThemeManager.instance().current.name
        for theme in all_themes:
            is_active = theme.name == current_name
            prefix = "●" if is_active else "○"
            color = p.fg if is_active else p.fg_muted
            btn = QPushButton(f"{prefix}  {theme.name}")
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color}; border: none;"
                f" font-family: {get_mono_font()}; font-size: {TY.md}px; text-align: left; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {p.bg_overlay}; color: {p.fg}; }}"
            )
            btn.clicked.connect(lambda checked, n=theme.name: self._on_theme_clicked(n))
            new_layout.addWidget(btn)
        new_layout.addStretch()
        self._swap_scroll_widget(self._themes_scroll, new_list, 30, len(all_themes))
        self._themes_list = new_list
        self._themes_list_layout = new_layout

    def _on_theme_clicked(self, name: str) -> None:
        self.theme_selected.emit(name)

    # ── public API ────────────────────────────────────────────────────────────

    def show_history(self, blocks: list[Block]) -> None:
        p = ThemeManager.instance().current
        new_list, new_layout = self._make_list_widget(spacing=2)
        for block in reversed(blocks):
            cmd_text = block.command.text
            color = p.fg if block.exit_code == 0 else p.red
            btn = QPushButton(cmd_text)
            btn.setFixedHeight(28)
            btn.setToolTip(cmd_text)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color}; border: none;"
                f" font-family: {get_mono_font()}; font-size: {TY.base}px; text-align: left; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {p.bg_overlay}; color: {p.fg}; }}"
            )
            btn.clicked.connect(lambda checked, t=cmd_text: self.command_selected.emit(t))
            new_layout.addWidget(btn)
        new_layout.addStretch()
        self._swap_scroll_widget(self._history_scroll, new_list, 30, len(blocks))
        self._history_list = new_list
        self._history_list_layout = new_layout

    def show_favorites(self, favorites: list[Favorite]) -> None:
        p = ThemeManager.instance().current
        new_list, new_layout = self._make_list_widget(spacing=2)
        if not favorites:
            empty = QLabel("No favorites yet\nUse ⋮ on any command block")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {p.fg_dim}; font-size: {TY.base}px; background: transparent; padding: 16px 8px;"
            )
            new_layout.addWidget(empty)
        else:
            for fav in favorites:
                new_layout.addWidget(self._build_favorite_row(fav, p))
        new_layout.addStretch()
        self._swap_scroll_widget(self._favs_scroll, new_list, 56, len(favorites))
        self._favs_list = new_list
        self._favs_list_layout = new_layout

    def _build_favorite_row(self, fav: Favorite, p: Palette) -> QWidget:
        row = QWidget()
        row.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header_h = QHBoxLayout()
        header_h.setContentsMargins(0, 0, 0, 0)
        header_h.setSpacing(4)

        name_lbl = QLabel(fav.name)
        name_lbl.setStyleSheet(
            f"color: {p.fg}; font-size: {TY.md}px; font-weight: bold; background: transparent;"
        )
        header_h.addWidget(name_lbl, 1)

        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(20, 20)
        menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg}; border: none; font-size: {TY.base}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; background: {p.bg_overlay}; border-radius: 4px; }}"
        )
        menu_btn.clicked.connect(lambda checked, f=fav: self._show_favorite_menu(f))
        header_h.addWidget(menu_btn)

        layout.addLayout(header_h)

        cmd_btn = QPushButton(fav.command_text)
        cmd_btn.setFixedHeight(22)
        cmd_btn.setToolTip(fav.command_text)
        cmd_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none;"
            f" font-family: {get_mono_font()}; font-size: {TY.base}px; text-align: left; padding: 0 4px; }}"
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

        def _edit():
            from .favorite_edit_dialog import FavoriteEditDialog
            dlg = FavoriteEditDialog(fav, parent=self)
            if dlg.exec():
                name, cmd, cwd = dlg.result_data()
                self.favorite_edit_requested.emit(fav.id, name, cmd, cwd)

        def _rename():
            name, ok = QInputDialog.getText(self, "Rename Favorite", "New name:", text=fav.name)
            if ok and name.strip():
                self.favorite_rename_requested.emit(fav.id, name.strip())

        menu.addAction("Edit",   _edit)
        menu.addAction("Rename", _rename)
        menu.addAction("Delete", lambda: self.favorite_delete_requested.emit(fav.id))
        menu.exec(self.cursor().pos())

    def _open_add_favorite(self) -> None:
        from .favorite_edit_dialog import FavoriteEditDialog
        dlg = FavoriteEditDialog(parent=self)
        if dlg.exec():
            name, cmd, cwd = dlg.result_data()
            self.favorite_add_requested.emit(name, cmd, cwd)

    def show_projects(self, projects_with_history: list[tuple[Project, list[Block]]]) -> None:
        p = ThemeManager.instance().current
        new_list, new_layout = self._make_list_widget(spacing=4)
        if not projects_with_history:
            empty = QLabel("No projects yet\nNavigate to a project and run a command, or use + to add")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {p.fg_dim}; font-size: {TY.base}px; background: transparent; padding: 16px 8px;"
            )
            new_layout.addWidget(empty)
        else:
            for proj, history in projects_with_history:
                new_layout.addWidget(self._build_project_row(proj, history, p))
        new_layout.addStretch()
        self._swap_scroll_widget(self._projs_scroll, new_list, 56, len(projects_with_history))
        self._projs_list = new_list
        self._projs_list_layout = new_layout

    def _build_project_row(
        self, proj: Project, history: list[Block], p: Palette
    ) -> QWidget:
        from pathlib import Path
        container = QWidget()
        container.setStyleSheet("QWidget { background: transparent; }")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── main row ──────────────────────────────────────────────────────────
        main_row = QWidget()
        main_row.setStyleSheet("QWidget { background: transparent; }")
        h = QHBoxLayout(main_row)
        h.setContentsMargins(4, 4, 4, 4)
        h.setSpacing(4)

        is_expanded = proj.id in self._expanded_projects
        toggle_btn = QPushButton("▾" if is_expanded else "▸")
        toggle_btn.setFixedSize(16, 16)
        toggle_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: {TY.md}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; }}"
        )
        h.addWidget(toggle_btn)

        name_btn = QPushButton(proj.name)
        name_btn.setFixedHeight(22)
        name_btn.setToolTip(proj.path)
        name_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg}; border: none;"
            f" font-size: {TY.md}px; font-weight: bold; text-align: left; padding: 0 2px; }}"
            f"QPushButton:hover {{ color: {p.blue}; }}"
        )
        name_btn.clicked.connect(
            lambda checked, path=proj.path: self.project_selected.emit(path)
        )
        h.addWidget(name_btn, 1)

        type_color = _TYPE_COLORS.get(proj.type, p.fg_muted)
        type_lbl = QLabel(proj.type)
        type_lbl.setStyleSheet(
            f"color: {type_color}; font-size: {TY.sm}px; background: transparent; padding: 1px 4px;"
        )
        h.addWidget(type_lbl)

        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(20, 20)
        menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg}; border: none; font-size: {TY.base}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; background: {p.bg_overlay}; border-radius: 4px; }}"
        )
        menu_btn.clicked.connect(lambda checked, pr=proj: self._show_project_menu(pr))
        h.addWidget(menu_btn)

        vbox.addWidget(main_row)

        # ── path label ────────────────────────────────────────────────────────
        home = str(Path.home())
        display_path = "~" + proj.path[len(home):] if proj.path.startswith(home) else proj.path
        path_lbl = QLabel(display_path)
        path_lbl.setStyleSheet(
            f"color: {p.fg_dim}; font-family: {get_mono_font()}; font-size: {TY.sm}px;"
            f" background: transparent; padding: 0 26px 2px 26px;"
        )
        path_lbl.setWordWrap(True)
        vbox.addWidget(path_lbl)

        # ── history sub-list ──────────────────────────────────────────────────
        hist_widget = QWidget()
        hist_widget.setStyleSheet("QWidget { background: transparent; }")
        hist_layout = QVBoxLayout(hist_widget)
        hist_layout.setContentsMargins(24, 0, 0, 4)
        hist_layout.setSpacing(1)

        for block in history:
            cmd_btn = QPushButton(block.command.text)
            cmd_btn.setFixedHeight(20)
            cmd_btn.setToolTip(block.command.text)
            color = p.fg_muted if block.exit_code == 0 else p.red
            cmd_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color}; border: none;"
                f" font-family: {get_mono_font()}; font-size: {TY.base}px; text-align: left; padding: 0 4px; }}"
                f"QPushButton:hover {{ background: {p.bg_overlay}; color: {p.fg}; }}"
            )
            cmd_btn.clicked.connect(
                lambda checked, t=block.command.text: self.command_selected.emit(t)
            )
            hist_layout.addWidget(cmd_btn)

        if not history:
            no_hist = QLabel("No commands yet")
            no_hist.setStyleSheet(f"color: {p.fg_dim}; font-size: {TY.base}px; background: transparent; padding: 0 4px;")
            hist_layout.addWidget(no_hist)

        hist_widget.setVisible(is_expanded)
        vbox.addWidget(hist_widget)

        # ── toggle wiring ─────────────────────────────────────────────────────
        def _toggle(checked=False, pid=proj.id, tw=hist_widget, tb=toggle_btn):
            if pid in self._expanded_projects:
                self._expanded_projects.discard(pid)
                tw.setVisible(False)
                tb.setText("▸")
            else:
                self._expanded_projects.add(pid)
                tw.setVisible(True)
                tb.setText("▾")

        toggle_btn.clicked.connect(_toggle)

        # ── right-click menu ──────────────────────────────────────────────────
        container.setContextMenuPolicy(Qt.CustomContextMenu)
        container.customContextMenuRequested.connect(
            lambda pos, pr=proj: self._show_project_menu(pr)
        )

        return container

    def _show_project_menu(self, proj: Project) -> None:
        p = ThemeManager.instance().current
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {p.bg_selected}; }}"
        )

        def _rename():
            name, ok = QInputDialog.getText(self, "Rename Project", "New name:", text=proj.name)
            if ok and name.strip():
                self.project_rename_requested.emit(proj.id, name.strip())

        menu.addAction("Rename", _rename)
        menu.addAction("Remove", lambda: self.project_delete_requested.emit(proj.id))
        menu.exec(self.cursor().pos())

    def update_cwd(self, display_path: str) -> None:
        self._cwd_label.setText(display_path)

    def show_ssh_connections(self, connections: list[SshConnection]) -> None:
        p = ThemeManager.instance().current
        new_list, new_layout = self._make_list_widget(spacing=4)
        if not connections:
            empty = QLabel("No SSH connections\nUse + to add one")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {p.fg_dim}; font-size: {TY.base}px; background: transparent; padding: 16px 8px;"
            )
            new_layout.addWidget(empty)
        else:
            groups: dict[str, list[SshConnection]] = {}
            for conn in connections:
                key = conn.group or ""
                groups.setdefault(key, []).append(conn)
            for group_name in sorted(groups.keys()):
                if group_name:
                    grp_lbl = QLabel(group_name)
                    grp_lbl.setStyleSheet(
                        f"color: {p.fg_muted}; font-size: {TY.base}px; font-weight: bold;"
                        f" background: transparent; padding: 4px 4px 2px 4px;"
                    )
                    new_layout.addWidget(grp_lbl)
                for conn in groups[group_name]:
                    new_layout.addWidget(self._build_ssh_row(conn, p))
        new_layout.addStretch()
        self._swap_scroll_widget(self._ssh_scroll, new_list, 52, len(connections))
        self._ssh_list = new_list
        self._ssh_list_layout = new_layout

    def _build_ssh_row(self, conn: SshConnection, p: Palette) -> QWidget:
        row = QWidget()
        row.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header_h = QHBoxLayout()
        header_h.setContentsMargins(0, 0, 0, 0)
        header_h.setSpacing(4)

        name_btn = QPushButton(conn.name)
        name_btn.setFixedHeight(22)
        name_btn.setToolTip(conn.to_command())
        name_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg}; border: none;"
            f" font-size: {TY.md}px; font-weight: bold; text-align: left; padding: 0 4px; }}"
            f"QPushButton:hover {{ color: {p.blue}; }}"
        )
        name_btn.clicked.connect(
            lambda checked, cid=conn.id: self.ssh_connect_requested.emit(cid)
        )
        header_h.addWidget(name_btn, 1)

        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(20, 20)
        menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg}; border: none; font-size: {TY.base}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; background: {p.bg_overlay}; border-radius: 4px; }}"
        )
        menu_btn.clicked.connect(lambda checked, c=conn: self._show_ssh_menu(c))
        header_h.addWidget(menu_btn)

        layout.addLayout(header_h)

        host_lbl = QLabel(f"{conn.user}@{conn.host}:{conn.port}")
        host_lbl.setStyleSheet(
            f"color: {p.fg_muted}; font-family: {get_mono_font()}; font-size: {TY.base}px;"
            f" background: transparent; padding: 0 4px;"
        )
        layout.addWidget(host_lbl)

        row.setContextMenuPolicy(Qt.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, c=conn: self._show_ssh_menu(c)
        )
        return row

    def show_workflows(self, workflows: list[Workflow]) -> None:
        p = ThemeManager.instance().current
        new_list, new_layout = self._make_list_widget(spacing=4)
        if not workflows:
            empty = QLabel("No workflows yet\nUse + to create one")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {p.fg_dim}; font-size: {TY.base}px; background: transparent; padding: 16px 8px;"
            )
            new_layout.addWidget(empty)
        else:
            for wf in workflows:
                new_layout.addWidget(self._build_workflow_row(wf, p))
        new_layout.addStretch()
        self._swap_scroll_widget(self._wf_scroll, new_list, 52, len(workflows))
        self._wf_list = new_list
        self._wf_list_layout = new_layout

    def _build_workflow_row(self, wf: Workflow, p: Palette) -> QWidget:
        row = QWidget()
        row.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header_h = QHBoxLayout()
        header_h.setContentsMargins(0, 0, 0, 0)
        header_h.setSpacing(4)

        name_btn = QPushButton(wf.name)
        name_btn.setFixedHeight(22)
        name_btn.setToolTip(wf.description or wf.name)
        name_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg}; border: none;"
            f" font-size: {TY.md}px; font-weight: bold; text-align: left; padding: 0 4px; }}"
            f"QPushButton:hover {{ color: {p.green}; }}"
        )
        name_btn.clicked.connect(
            lambda checked, wid=wf.id: self.workflow_run_requested.emit(wid)
        )
        header_h.addWidget(name_btn, 1)

        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(20, 20)
        menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg}; border: none; font-size: {TY.base}px; }}"
            f"QPushButton:hover {{ color: {p.fg}; background: {p.bg_overlay}; border-radius: 4px; }}"
        )
        menu_btn.clicked.connect(lambda checked, w=wf: self._show_workflow_menu(w))
        header_h.addWidget(menu_btn)

        layout.addLayout(header_h)

        steps_lbl = QLabel(f"{len(wf.steps)} step{'s' if len(wf.steps) != 1 else ''}")
        steps_lbl.setStyleSheet(
            f"color: {p.fg_muted}; font-size: {TY.base}px; background: transparent; padding: 0 4px;"
        )
        layout.addWidget(steps_lbl)

        row.setContextMenuPolicy(Qt.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, w=wf: self._show_workflow_menu(w)
        )
        return row

    def _show_workflow_menu(self, wf: Workflow) -> None:
        p = ThemeManager.instance().current
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {p.bg_selected}; }}"
        )
        menu.addAction("Run",    lambda: self.workflow_run_requested.emit(wf.id))
        menu.addAction("Edit",   lambda: self.workflow_edit_requested.emit(wf.id))
        menu.addAction("Delete", lambda: self.workflow_delete_requested.emit(wf.id))
        menu.exec(self.cursor().pos())

    def _show_ssh_menu(self, conn: SshConnection) -> None:
        p = ThemeManager.instance().current
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {p.bg_selected}; }}"
        )
        menu.addAction("Connect", lambda: self.ssh_connect_requested.emit(conn.id))
        menu.addAction("Edit",    lambda: self.ssh_edit_requested.emit(conn.id))
        menu.addAction("Delete",  lambda: self.ssh_delete_requested.emit(conn.id))
        menu.exec(self.cursor().pos())
