from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QFileDialog, QFontComboBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont

from .theme import Palette, ThemeManager
from ..domain.settings import AppSettings
from ..infra.storage.history_repository import HistoryRepository
from ..infra.storage.favorites_repository import FavoritesRepository
from ..infra.storage.project_repository import ProjectRepository
from ..services.settings_service import SettingsService


# ── helpers ───────────────────────────────────────────────────────────────────

def _section_frame(title: str, p: Palette) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame {{ background: {p.bg_surface}; border: 1px solid {p.border};"
        f" border-radius: 8px; }}"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(8)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        f"color: {p.blue}; font-size: 9pt; font-weight: bold;"
        f" background: transparent; border: none;"
    )
    layout.addWidget(title_lbl)

    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setStyleSheet(f"QFrame {{ color: {p.border}; max-height: 1px; border: none; background: {p.border}; }}")
    layout.addWidget(sep)

    return frame, layout


def _row_widget(label: str, control: QWidget, p: Palette) -> QWidget:
    w = QWidget()
    w.setStyleSheet("QWidget { background: transparent; border: none; }")
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {p.fg_muted}; font-size: 9pt; background: transparent; border: none;")
    lbl.setFixedWidth(130)
    h.addWidget(lbl)
    h.addWidget(control)
    return w


def _action_btn(text: str, p: Palette, danger: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(28)
    color = p.red_ui if danger else p.blue
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {color}; border: 1px solid {color};"
        f" border-radius: 4px; font-size: 9pt; padding: 0 12px; }}"
        f"QPushButton:hover {{ background: {color}; color: {p.bg}; }}"
    )
    return btn


# ── Theme Creator ─────────────────────────────────────────────────────────────

_COLOR_GROUPS = [
    ("Foreground",   ["fg", "fg_muted", "fg_dim"]),
    ("Backgrounds",  ["bg", "bg_panel", "bg_surface", "bg_overlay",
                      "bg_hover", "bg_hover2", "bg_active", "bg_selected", "bg_highlight"]),
    ("Semantic",     ["blue", "green", "red", "red_ui", "cyan"]),
    ("PTY canvas",   ["pty_bg", "pty_fg", "pty_cursor_bg", "pty_cursor_fg"]),
    ("Borders",      ["border"]),
]


class _ThemeCreatorSection(QWidget):
    def __init__(self, p: Palette, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QWidget { background: transparent; border: none; }")
        self._working: dict[str, str] = {}
        self._swatch_btns: dict[str, QPushButton] = {}
        self._build(p)

    def _build(self, p: Palette) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        # seed working colors from current theme
        current = ThemeManager.instance().current
        current_dict = asdict(current)
        for field, val in current_dict.items():
            if field != "name":
                self._working[field] = val

        # name row
        name_row = QWidget()
        name_row.setStyleSheet("QWidget { background: transparent; border: none; }")
        nh = QHBoxLayout(name_row)
        nh.setContentsMargins(0, 0, 0, 0)
        nh.setSpacing(8)
        name_lbl = QLabel("Theme name:")
        name_lbl.setStyleSheet(f"color: {p.fg_muted}; font-size: 9pt; background: transparent; border: none;")
        name_lbl.setFixedWidth(100)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("my-theme")
        self._name_edit.setFixedHeight(26)
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 4px; font-size: 9pt; padding: 0 6px; }}"
        )
        save_btn = _action_btn("Save theme", p)
        save_btn.clicked.connect(self._save_theme)
        nh.addWidget(name_lbl)
        nh.addWidget(self._name_edit, 1)
        nh.addWidget(save_btn)
        vbox.addWidget(name_row)

        # live preview
        self._preview_frame = QFrame()
        self._preview_frame.setFixedSize(160, 50)
        self._preview_frame.setStyleSheet(
            f"QFrame {{ background: {self._working.get('bg', '#000')};"
            f" border: 1px solid {self._working.get('border', '#333')}; border-radius: 4px; }}"
        )
        pv_lbl = QLabel("Preview text", self._preview_frame)
        pv_lbl.setAlignment(Qt.AlignCenter)
        pv_lbl.setGeometry(0, 0, 160, 50)
        pv_lbl.setStyleSheet(
            f"color: {self._working.get('fg', '#fff')}; font-size: 9pt;"
            f" background: transparent; border: none;"
        )
        self._preview_text_lbl = pv_lbl
        vbox.addWidget(self._preview_frame)

        # color groups — two-column grid
        for group_name, grp_fields in _COLOR_GROUPS:
            grp_lbl = QLabel(group_name)
            grp_lbl.setStyleSheet(
                f"color: {p.fg_dim}; font-size: 8pt; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            vbox.addWidget(grp_lbl)

            grid = QWidget()
            grid.setStyleSheet("QWidget { background: transparent; border: none; }")
            gl = QGridLayout(grid)
            gl.setContentsMargins(0, 0, 0, 6)
            gl.setSpacing(4)
            gl.setColumnStretch(0, 1)
            gl.setColumnStretch(1, 1)

            for idx, field in enumerate(grp_fields):
                col = idx % 2
                row_n = idx // 2

                cell = QWidget()
                cell.setStyleSheet("QWidget { background: transparent; border: none; }")
                ch = QHBoxLayout(cell)
                ch.setContentsMargins(0, 0, 0, 0)
                ch.setSpacing(6)

                swatch = QPushButton()
                swatch.setFixedSize(22, 22)
                color_val = self._working.get(field, "#888888")
                swatch.setStyleSheet(
                    f"QPushButton {{ background: {color_val}; border: 1px solid {p.border};"
                    f" border-radius: 4px; }}"
                    f"QPushButton:hover {{ border: 2px solid {p.fg}; }}"
                )
                swatch.clicked.connect(lambda checked, f=field: self._pick_color(f))
                self._swatch_btns[field] = swatch

                flbl = QLabel(field)
                flbl.setStyleSheet(
                    f"color: {p.fg_muted}; font-family: Monospace; font-size: 8pt;"
                    f" background: transparent; border: none;"
                )

                ch.addWidget(swatch)
                ch.addWidget(flbl, 1)
                gl.addWidget(cell, row_n, col)

            vbox.addWidget(grid)

        # existing user themes (delete)
        del_lbl = QLabel("Existing user themes")
        del_lbl.setStyleSheet(
            f"color: {p.fg_dim}; font-size: 8pt; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        vbox.addWidget(del_lbl)

        self._del_container = QWidget()
        self._del_container.setStyleSheet("QWidget { background: transparent; border: none; }")
        self._del_layout = QVBoxLayout(self._del_container)
        self._del_layout.setContentsMargins(0, 0, 0, 0)
        self._del_layout.setSpacing(3)
        vbox.addWidget(self._del_container)
        self._refresh_delete_list(p)

    def _refresh_delete_list(self, p: Palette | None = None) -> None:
        if p is None:
            p = ThemeManager.instance().current
        while self._del_layout.count():
            item = self._del_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from .theme import _BUILT_IN
        for theme in ThemeManager.instance().all_themes():
            if theme.name in _BUILT_IN:
                continue
            row = QWidget()
            row.setStyleSheet("QWidget { background: transparent; border: none; }")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(8)
            nlbl = QLabel(theme.name)
            nlbl.setStyleSheet(
                f"color: {p.fg}; font-family: Monospace; font-size: 9pt;"
                f" background: transparent; border: none;"
            )
            rh.addWidget(nlbl, 1)
            del_btn = _action_btn("Delete", p, danger=True)
            del_btn.clicked.connect(lambda checked, n=theme.name: self._delete_theme(n))
            rh.addWidget(del_btn)
            self._del_layout.addWidget(row)

        from .theme import _BUILT_IN as _BI2
        has_user = any(t.name not in _BI2 for t in ThemeManager.instance().all_themes())
        if not has_user:
            no_lbl = QLabel("No custom themes yet")
            no_lbl.setStyleSheet(
                f"color: {p.fg_dim}; font-size: 8pt; background: transparent; border: none;"
            )
            self._del_layout.addWidget(no_lbl)

    def _pick_color(self, field: str) -> None:
        current_hex = self._working.get(field, "#888888")
        color = QColorDialog.getColor(QColor(current_hex), self, f"Choose color for {field}")
        if color.isValid():
            hex_val = color.name()
            self._working[field] = hex_val
            btn = self._swatch_btns.get(field)
            if btn:
                p = ThemeManager.instance().current
                btn.setStyleSheet(
                    f"QPushButton {{ background: {hex_val}; border: 1px solid {p.border};"
                    f" border-radius: 3px; }}"
                    f"QPushButton:hover {{ border: 1px solid {p.fg}; }}"
                )
            self._update_preview()

    def _update_preview(self) -> None:
        bg = self._working.get("bg", "#000")
        fg = self._working.get("fg", "#fff")
        border = self._working.get("border", "#333")
        self._preview_frame.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {border}; border-radius: 4px; }}"
        )
        self._preview_text_lbl.setStyleSheet(
            f"color: {fg}; font-size: 9pt; background: transparent; border: none;"
        )

    def _save_theme(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Settings", "Please enter a theme name.")
            return

        from .theme import Palette, _BUILT_IN
        if name in _BUILT_IN:
            QMessageBox.warning(self, "Settings", f"Cannot overwrite built-in theme '{name}'.")
            return

        try:
            palette = Palette(name=name, **{k: v for k, v in self._working.items()})
            ThemeManager.instance().save_user_theme(palette)
            p = ThemeManager.instance().current
            self._refresh_delete_list(p)
            QMessageBox.information(self, "Settings", f"Theme '{name}' saved.")
        except Exception as exc:
            QMessageBox.warning(self, "Settings", f"Failed to save theme: {exc}")

    def _delete_theme(self, name: str) -> None:
        reply = QMessageBox.question(
            self, "Delete theme",
            f"Delete theme '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            ThemeManager.instance().delete_user_theme(name)
            p = ThemeManager.instance().current
            self._refresh_delete_list(p)

    def apply_theme(self, p: Palette) -> None:
        self._refresh_delete_list(p)


# ── Data Management ───────────────────────────────────────────────────────────

class _DataManagementSection(QWidget):
    data_cleared = Signal()

    def __init__(
        self,
        repository: HistoryRepository,
        favorites_repo: FavoritesRepository,
        project_repo: ProjectRepository,
        conn: sqlite3.Connection,
        p: Palette,
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet("QWidget { background: transparent; border: none; }")
        self._repo     = repository
        self._fav_repo = favorites_repo
        self._proj_repo = project_repo
        self._conn     = conn
        self._build(p)

    def _build(self, p: Palette) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {p.green}; font-size: 8pt; background: transparent; border: none;"
        )
        self._status_lbl.setWordWrap(True)

        def add_btn(label: str, slot, danger: bool = False):
            btn = _action_btn(label, p, danger=danger)
            btn.clicked.connect(slot)
            vbox.addWidget(btn)

        add_btn("Clear command history", self._clear_history, danger=True)
        add_btn("Clear favorites",       self._clear_favorites, danger=True)
        add_btn("Clear projects",        self._clear_projects, danger=True)
        add_btn("Clear ALL data",        self._clear_all, danger=True)
        add_btn("Export history to JSON", self._export_history, danger=False)

        vbox.addWidget(self._status_lbl)

    def _confirm(self, msg: str) -> bool:
        return QMessageBox.question(
            self, "Confirm", msg, QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes

    def _clear_history(self) -> None:
        if self._confirm("Delete ALL command history? This cannot be undone."):
            self._repo.clear_all()
            self._status_lbl.setText("Command history cleared.")
            self.data_cleared.emit()

    def _clear_favorites(self) -> None:
        if self._confirm("Delete ALL favorites? This cannot be undone."):
            self._fav_repo.clear_all()
            self._status_lbl.setText("Favorites cleared.")
            self.data_cleared.emit()

    def _clear_projects(self) -> None:
        if self._confirm("Delete ALL projects? This cannot be undone."):
            self._proj_repo.clear_all()
            self._status_lbl.setText("Projects cleared.")
            self.data_cleared.emit()

    def _clear_all(self) -> None:
        if not self._confirm("Delete ALL history, favorites, and projects? This cannot be undone."):
            return
        if not self._confirm("Are you absolutely sure? This is irreversible."):
            return
        self._repo.clear_all()
        self._fav_repo.clear_all()
        self._proj_repo.clear_all()
        try:
            self._conn.execute("VACUUM")
            self._conn.commit()
        except Exception:
            pass
        self._status_lbl.setText("All data cleared.")
        self.data_cleared.emit()

    def _export_history(self) -> None:
        blocks = self._repo.load_recent(limit=10000)
        from pathlib import Path
        from dataclasses import asdict as _asdict
        out_path = Path.home() / ".blocksh" / "export.json"
        data = [
            {
                "command": b.command.text,
                "exit_code": b.exit_code,
                "cwd": b.cwd,
                "created_at": b.command.created_at.isoformat(),
                "stdout": b.stdout,
                "stderr": b.stderr,
            }
            for b in blocks
        ]
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        self._status_lbl.setText(f"Exported to {out_path}")

    def apply_theme(self, p: Palette) -> None:
        pass


# ── Appearance ────────────────────────────────────────────────────────────────

class _AppearanceSection(QWidget):
    def __init__(self, p: Palette, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QWidget { background: transparent; border: none; }")
        self._color_btn: QPushButton | None = None
        self._build(p)

    def _build(self, p: Palette) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        s = SettingsService.instance().get()
        ctrl_style = (
            f"QComboBox, QSpinBox, QFontComboBox {{"
            f" background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 4px; font-size: 9pt; padding: 2px 6px; min-height: 24px; }}"
        )

        # profile photo
        from pathlib import Path as _Path
        photo_name = _Path(s.avatar_path).name if s.avatar_path else "No photo selected"
        self._avatar_name_lbl = QLabel(photo_name)
        self._avatar_name_lbl.setFixedHeight(26)
        self._avatar_name_lbl.setStyleSheet(
            f"color: {p.fg_muted}; font-size: 9pt; background: {p.bg_overlay};"
            f" border: 1px solid {p.border}; border-radius: 4px; padding: 0 6px;"
        )
        choose_avatar_btn = _action_btn("Choose...", p)
        choose_avatar_btn.clicked.connect(self._pick_avatar)
        clear_avatar_btn = QPushButton("✕")
        clear_avatar_btn.setFixedSize(26, 26)
        clear_avatar_btn.setToolTip("Remove photo")
        clear_avatar_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: 10pt; }}"
            f"QPushButton:hover {{ color: {p.red_ui}; }}"
        )
        clear_avatar_btn.clicked.connect(self._clear_avatar)
        avatar_ctrl = QWidget()
        avatar_ctrl.setStyleSheet("QWidget { background: transparent; border: none; }")
        ac = QHBoxLayout(avatar_ctrl)
        ac.setContentsMargins(0, 0, 0, 0)
        ac.setSpacing(4)
        ac.addWidget(self._avatar_name_lbl, 1)
        ac.addWidget(choose_avatar_btn)
        ac.addWidget(clear_avatar_btn)
        vbox.addWidget(_row_widget("Profile photo", avatar_ctrl, p))

        # font family
        self._font_combo = QFontComboBox()
        self._font_combo.setFontFilters(QFontComboBox.MonospacedFonts)
        self._font_combo.setCurrentFont(QFont(s.font_family))
        self._font_combo.setStyleSheet(ctrl_style)
        self._font_combo.currentFontChanged.connect(
            lambda f: SettingsService.instance().update(font_family=f.family())
        )
        vbox.addWidget(_row_widget("Font family", self._font_combo, p))

        # terminal font size
        self._term_size = QSpinBox()
        self._term_size.setRange(8, 24)
        self._term_size.setValue(s.font_size_terminal)
        self._term_size.setStyleSheet(ctrl_style)
        self._term_size.valueChanged.connect(
            lambda v: SettingsService.instance().update(font_size_terminal=v)
        )
        vbox.addWidget(_row_widget("Terminal font size", self._term_size, p))

        # output font size
        self._out_size = QSpinBox()
        self._out_size.setRange(7, 18)
        self._out_size.setValue(s.font_size_output)
        self._out_size.setStyleSheet(ctrl_style)
        self._out_size.valueChanged.connect(
            lambda v: SettingsService.instance().update(font_size_output=v)
        )
        vbox.addWidget(_row_widget("Output font size", self._out_size, p))

        # cursor style
        self._cursor_combo = QComboBox()
        self._cursor_combo.addItems(["Block", "Underline", "Beam"])
        idx = {"block": 0, "underline": 1, "beam": 2}.get(s.cursor_style, 0)
        self._cursor_combo.setCurrentIndex(idx)
        self._cursor_combo.setStyleSheet(ctrl_style)
        self._cursor_combo.currentTextChanged.connect(
            lambda t: SettingsService.instance().update(cursor_style=t.lower())
        )
        vbox.addWidget(_row_widget("Cursor style", self._cursor_combo, p))

        # output text color override
        self._color_btn = QPushButton(s.output_fg_override or "Theme default")
        self._color_btn.setFixedHeight(26)
        self._color_btn.setStyleSheet(
            f"QPushButton {{ background: {s.output_fg_override or p.bg_overlay};"
            f" color: {p.fg}; border: 1px solid {p.border}; border-radius: 4px;"
            f" font-size: 9pt; padding: 0 8px; }}"
        )
        self._color_btn.clicked.connect(self._pick_output_color)

        clear_color_btn = QPushButton("✕")
        clear_color_btn.setFixedSize(26, 26)
        clear_color_btn.setToolTip("Reset to theme default")
        clear_color_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted}; border: none; font-size: 10pt; }}"
            f"QPushButton:hover {{ color: {p.red_ui}; }}"
        )
        clear_color_btn.clicked.connect(self._clear_output_color)

        color_row = QWidget()
        color_row.setStyleSheet("QWidget { background: transparent; border: none; }")
        ch = QHBoxLayout(color_row)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(4)
        ch.addWidget(self._color_btn, 1)
        ch.addWidget(clear_color_btn)
        vbox.addWidget(_row_widget("Output text color", color_row, p))

    def _pick_avatar(self) -> None:
        from pathlib import Path
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose profile photo", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
        )
        if path:
            SettingsService.instance().update(avatar_path=path)
            self._avatar_name_lbl.setText(Path(path).name)

    def _clear_avatar(self) -> None:
        SettingsService.instance().update(avatar_path="")
        self._avatar_name_lbl.setText("No photo selected")

    def _pick_output_color(self) -> None:
        s = SettingsService.instance().get()
        init = QColor(s.output_fg_override) if s.output_fg_override else QColor("#cdd6f4")
        color = QColorDialog.getColor(init, self, "Choose output text color")
        if color.isValid():
            hex_val = color.name()
            SettingsService.instance().update(output_fg_override=hex_val)
            p = ThemeManager.instance().current
            self._color_btn.setText(hex_val)
            self._color_btn.setStyleSheet(
                f"QPushButton {{ background: {hex_val}; color: {p.fg};"
                f" border: 1px solid {p.border}; border-radius: 4px;"
                f" font-size: 9pt; padding: 0 8px; }}"
            )

    def _clear_output_color(self) -> None:
        SettingsService.instance().update(output_fg_override="")
        p = ThemeManager.instance().current
        if self._color_btn:
            self._color_btn.setText("Theme default")
            self._color_btn.setStyleSheet(
                f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg};"
                f" border: 1px solid {p.border}; border-radius: 4px;"
                f" font-size: 9pt; padding: 0 8px; }}"
            )

    def apply_theme(self, p: Palette) -> None:
        pass


# ── Terminal Behavior ─────────────────────────────────────────────────────────

class _TerminalSection(QWidget):
    def __init__(self, p: Palette, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QWidget { background: transparent; border: none; }")
        self._build(p)

    def _build(self, p: Palette) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        s = SettingsService.instance().get()
        ctrl_style = (
            f"QComboBox, QSpinBox {{"
            f" background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 4px; font-size: 9pt; padding: 2px 6px; min-height: 24px; }}"
        )

        # default shell
        self._shell_combo = QComboBox()
        shells = self._available_shells()
        self._shell_combo.addItems(shells)
        if s.default_shell in shells:
            self._shell_combo.setCurrentText(s.default_shell)
        self._shell_combo.setStyleSheet(ctrl_style)
        self._shell_combo.currentTextChanged.connect(
            lambda t: SettingsService.instance().update(default_shell=t)
        )
        vbox.addWidget(_row_widget("Default shell", self._shell_combo, p))

        # scrollback lines
        self._scrollback = QSpinBox()
        self._scrollback.setRange(500, 50000)
        self._scrollback.setSingleStep(500)
        self._scrollback.setValue(s.scrollback_lines)
        self._scrollback.setStyleSheet(ctrl_style)
        self._scrollback.valueChanged.connect(
            lambda v: SettingsService.instance().update(scrollback_lines=v)
        )
        vbox.addWidget(_row_widget("Scrollback lines", self._scrollback, p))

        # history limit
        self._hist_limit = QSpinBox()
        self._hist_limit.setRange(50, 10000)
        self._hist_limit.setValue(s.history_limit)
        self._hist_limit.setStyleSheet(ctrl_style)
        self._hist_limit.valueChanged.connect(
            lambda v: SettingsService.instance().update(history_limit=v)
        )
        vbox.addWidget(_row_widget("History load limit", self._hist_limit, p))

        # auto-scroll
        self._auto_scroll = QCheckBox("Auto-scroll to latest output")
        self._auto_scroll.setChecked(s.auto_scroll)
        self._auto_scroll.setStyleSheet(
            f"QCheckBox {{ color: {p.fg_muted}; font-size: 9pt; background: transparent; border: none; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; }}"
        )
        self._auto_scroll.stateChanged.connect(
            lambda st: SettingsService.instance().update(auto_scroll=bool(st))
        )
        vbox.addWidget(self._auto_scroll)

        # history retention
        self._retention_combo = QComboBox()
        retention_labels = ["Forever", "7 days", "30 days", "90 days"]
        retention_values = [0, 7, 30, 90]
        self._retention_combo.addItems(retention_labels)
        current_days = s.history_retention_days
        idx = retention_values.index(current_days) if current_days in retention_values else 0
        self._retention_combo.setCurrentIndex(idx)
        self._retention_combo.setStyleSheet(ctrl_style)
        self._retention_combo.currentIndexChanged.connect(
            lambda i: SettingsService.instance().update(
                history_retention_days=retention_values[i]
            )
        )
        vbox.addWidget(_row_widget("History retention", self._retention_combo, p))

        # .env auto-load
        self._env_combo = QComboBox()
        env_labels  = ["Ask each time", "Always load automatically", "Never load"]
        env_values  = ["ask", "always", "never"]
        self._env_combo.addItems(env_labels)
        current_env = s.auto_load_env if s.auto_load_env in env_values else "ask"
        self._env_combo.setCurrentIndex(env_values.index(current_env))
        self._env_combo.setStyleSheet(ctrl_style)
        self._env_combo.currentIndexChanged.connect(
            lambda i: SettingsService.instance().update(auto_load_env=env_values[i])
        )
        vbox.addWidget(_row_widget(".env file loading", self._env_combo, p))

        # info note
        note = QLabel("Shell and scrollback changes apply to new terminal tabs only.")
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {p.fg_dim}; font-size: 8pt; background: transparent; border: none;"
        )
        vbox.addWidget(note)

    @staticmethod
    def _available_shells() -> list[str]:
        try:
            lines = Path("/etc/shells").read_text().splitlines()
            shells = [
                s.strip() for s in lines
                if s.strip() and not s.startswith("#")
                and Path(s.strip()).exists()
                and os.access(s.strip(), os.X_OK)
            ]
            return shells or ["bash"]
        except Exception:
            return ["bash"]

    def apply_theme(self, p: Palette) -> None:
        pass


# ── AI Assistant Section ──────────────────────────────────────────────────────

_OLLAMA_MODELS    = ["qwen2.5-coder:1.5b", "llama3.2:1b", "phi3.5:mini",
                     "deepseek-r1:1.5b", "llama3.2:3b", "qwen2.5-coder:7b"]
_ANTHROPIC_MODELS = ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"]
_OPENAI_MODELS    = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
_BACKEND_NAMES    = ["ollama", "anthropic", "openai"]


class _AiSection(QWidget):
    def __init__(self, p: Palette, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QWidget { background: transparent; border: none; }")
        self._workers: list = []
        self._build(p)

    def _build(self, p: Palette) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        s = SettingsService.instance().get()
        ctrl_style = (
            f"QComboBox, QLineEdit {{"
            f" background: {p.bg_overlay}; color: {p.fg}; border: 1px solid {p.border};"
            f" border-radius: 4px; font-size: 9pt; padding: 2px 6px; min-height: 24px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
        )

        # Enable AI toggle
        self._enable_cb = QCheckBox("Enable AI features")
        self._enable_cb.setChecked(s.ai_enabled)
        self._enable_cb.setStyleSheet(
            f"QCheckBox {{ color: {p.fg_muted}; font-size: 9pt; background: transparent; border: none; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; }}"
        )
        self._enable_cb.stateChanged.connect(
            lambda st: SettingsService.instance().update(ai_enabled=bool(st))
        )
        vbox.addWidget(self._enable_cb)

        # Backend selector
        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["Ollama (offline)", "Anthropic (Claude)", "OpenAI (GPT)"])
        self._backend_combo.setCurrentIndex(_BACKEND_NAMES.index(s.ai_backend)
                                            if s.ai_backend in _BACKEND_NAMES else 0)
        self._backend_combo.setStyleSheet(ctrl_style)
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        vbox.addWidget(_row_widget("Backend", self._backend_combo, p))

        # Stacked panels per backend
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QWidget { background: transparent; border: none; }")

        # ── Ollama ──────────────────────────────────────────────────────────
        ollama_w = QWidget()
        ollama_w.setStyleSheet("QWidget { background: transparent; border: none; }")
        ov = QVBoxLayout(ollama_w)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(4)

        self._ollama_host = QLineEdit(s.ai_ollama_host)
        self._ollama_host.setStyleSheet(ctrl_style)
        self._ollama_host.editingFinished.connect(
            lambda: SettingsService.instance().update(ai_ollama_host=self._ollama_host.text())
        )
        ov.addWidget(_row_widget("Host", self._ollama_host, p))

        self._ollama_model = QComboBox()
        self._ollama_model.addItems(_OLLAMA_MODELS)
        self._ollama_model.setEditable(True)
        self._ollama_model.setCurrentText(s.ai_ollama_model)
        self._ollama_model.setStyleSheet(ctrl_style)
        self._ollama_model.currentTextChanged.connect(
            lambda t: SettingsService.instance().update(ai_ollama_model=t)
        )
        ov.addWidget(_row_widget("Model", self._ollama_model, p))

        status_row = QWidget()
        status_row.setStyleSheet("QWidget { background: transparent; border: none; }")
        sh = QHBoxLayout(status_row)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(8)
        slbl = QLabel("Status:")
        slbl.setStyleSheet(
            f"color: {p.fg_muted}; font-size: 9pt; background: transparent; border: none;"
        )
        slbl.setFixedWidth(130)
        self._ollama_status = QLabel("● Checking…")
        self._ollama_status.setStyleSheet(
            f"color: {p.fg_dim}; font-size: 9pt; background: transparent; border: none;"
        )
        recheck_btn = _action_btn("Re-check", p)
        recheck_btn.clicked.connect(self._check_ollama)
        sh.addWidget(slbl)
        sh.addWidget(self._ollama_status, 1)
        sh.addWidget(recheck_btn)
        ov.addWidget(status_row)
        self._stack.addWidget(ollama_w)

        # ── Anthropic ───────────────────────────────────────────────────────
        anth_w = QWidget()
        anth_w.setStyleSheet("QWidget { background: transparent; border: none; }")
        av = QVBoxLayout(anth_w)
        av.setContentsMargins(0, 0, 0, 0)
        av.setSpacing(4)

        self._anthropic_key = QLineEdit(s.ai_anthropic_key)
        self._anthropic_key.setEchoMode(QLineEdit.Password)
        self._anthropic_key.setPlaceholderText("sk-ant-…")
        self._anthropic_key.setStyleSheet(ctrl_style)
        self._anthropic_key.editingFinished.connect(
            lambda: SettingsService.instance().update(ai_anthropic_key=self._anthropic_key.text())
        )
        av.addWidget(_row_widget("API key", self._anthropic_key, p))

        self._anthropic_model = QComboBox()
        self._anthropic_model.addItems(_ANTHROPIC_MODELS)
        self._anthropic_model.setCurrentText(s.ai_anthropic_model)
        self._anthropic_model.setStyleSheet(ctrl_style)
        self._anthropic_model.currentTextChanged.connect(
            lambda t: SettingsService.instance().update(ai_anthropic_model=t)
        )
        av.addWidget(_row_widget("Model", self._anthropic_model, p))

        warn_a = QLabel("⚠  API key stored as plaintext in ~/.blocksh/settings.json")
        warn_a.setWordWrap(True)
        warn_a.setStyleSheet(
            f"color: {p.red}; font-size: 8pt; background: transparent; border: none;"
        )
        av.addWidget(warn_a)
        self._stack.addWidget(anth_w)

        # ── OpenAI ──────────────────────────────────────────────────────────
        oai_w = QWidget()
        oai_w.setStyleSheet("QWidget { background: transparent; border: none; }")
        ov2 = QVBoxLayout(oai_w)
        ov2.setContentsMargins(0, 0, 0, 0)
        ov2.setSpacing(4)

        self._openai_key = QLineEdit(s.ai_openai_key)
        self._openai_key.setEchoMode(QLineEdit.Password)
        self._openai_key.setPlaceholderText("sk-…")
        self._openai_key.setStyleSheet(ctrl_style)
        self._openai_key.editingFinished.connect(
            lambda: SettingsService.instance().update(ai_openai_key=self._openai_key.text())
        )
        ov2.addWidget(_row_widget("API key", self._openai_key, p))

        self._openai_model = QComboBox()
        self._openai_model.addItems(_OPENAI_MODELS)
        self._openai_model.setCurrentText(s.ai_openai_model)
        self._openai_model.setStyleSheet(ctrl_style)
        self._openai_model.currentTextChanged.connect(
            lambda t: SettingsService.instance().update(ai_openai_model=t)
        )
        ov2.addWidget(_row_widget("Model", self._openai_model, p))

        warn_o = QLabel("⚠  API key stored as plaintext in ~/.blocksh/settings.json")
        warn_o.setWordWrap(True)
        warn_o.setStyleSheet(
            f"color: {p.red}; font-size: 8pt; background: transparent; border: none;"
        )
        ov2.addWidget(warn_o)
        self._stack.addWidget(oai_w)

        vbox.addWidget(self._stack)
        self._stack.setCurrentIndex(_BACKEND_NAMES.index(s.ai_backend)
                                    if s.ai_backend in _BACKEND_NAMES else 0)

        QTimer.singleShot(200, self._check_ollama)

    def _on_backend_changed(self, index: int) -> None:
        SettingsService.instance().update(ai_backend=_BACKEND_NAMES[index])
        self._stack.setCurrentIndex(index)

    def _check_ollama(self) -> None:
        from ..services.ai_service import AiService
        self._ollama_status.setText("● Checking…")
        p = ThemeManager.instance().current
        self._ollama_status.setStyleSheet(
            f"color: {p.fg_dim}; font-size: 9pt; background: transparent; border: none;"
        )
        host = SettingsService.instance().get().ai_ollama_host
        worker = AiService.instance().check_ollama(host)

        def _ok(_: str) -> None:
            p2 = ThemeManager.instance().current
            self._ollama_status.setText("● Running")
            self._ollama_status.setStyleSheet(
                f"color: {p2.green}; font-size: 9pt; background: transparent; border: none;"
            )

        def _fail(_: str) -> None:
            p2 = ThemeManager.instance().current
            self._ollama_status.setText("✗ Not running — install at ollama.com")
            self._ollama_status.setStyleSheet(
                f"color: {p2.red}; font-size: 9pt; background: transparent; border: none;"
            )

        worker.result_ready.connect(_ok)
        worker.error_occurred.connect(_fail)
        self._workers.append(worker)
        worker.start()

    def apply_theme(self, p: Palette) -> None:
        pass


# ── Main Settings Panel ───────────────────────────────────────────────────────

class SettingsPanel(QWidget):
    data_cleared = Signal()

    def __init__(
        self,
        repository: HistoryRepository,
        favorites_repo: FavoritesRepository,
        project_repo: ProjectRepository,
        conn: sqlite3.Connection,
        parent=None,
    ):
        super().__init__(parent)
        self._repo      = repository
        self._fav_repo  = favorites_repo
        self._proj_repo = project_repo
        self._conn      = conn
        self._sections: list[QWidget] = []
        self._build_ui()

        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    def _build_ui(self) -> None:
        p = ThemeManager.instance().current
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(0)

        # Two-column grid: left col = Appearance + Terminal Behavior
        #                  right col = Theme Creator + Data Management
        cols = QHBoxLayout()
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(16)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(16)

        # ── Appearance ────────────────────────────────────────────────────────
        frame, layout = _section_frame("Appearance", p)
        self._appearance = _AppearanceSection(p)
        layout.addWidget(self._appearance)
        left_col.addWidget(frame)
        self._sections.append(self._appearance)

        # ── Terminal Behavior ─────────────────────────────────────────────────
        frame2, layout2 = _section_frame("Terminal Behavior", p)
        self._terminal = _TerminalSection(p)
        layout2.addWidget(self._terminal)
        left_col.addWidget(frame2)
        self._sections.append(self._terminal)

        # ── AI Assistant ──────────────────────────────────────────────────────
        frame5, layout5 = _section_frame("AI Assistant", p)
        self._ai = _AiSection(p)
        layout5.addWidget(self._ai)
        left_col.addWidget(frame5)
        self._sections.append(self._ai)

        left_col.addStretch()

        # ── Theme Creator ─────────────────────────────────────────────────────
        frame3, layout3 = _section_frame("Theme Creator", p)
        self._theme_creator = _ThemeCreatorSection(p)
        layout3.addWidget(self._theme_creator)
        right_col.addWidget(frame3)
        self._sections.append(self._theme_creator)

        # ── Data Management ───────────────────────────────────────────────────
        frame4, layout4 = _section_frame("Data Management", p)
        self._data_mgmt = _DataManagementSection(
            self._repo, self._fav_repo, self._proj_repo, self._conn, p
        )
        self._data_mgmt.data_cleared.connect(self.data_cleared)
        layout4.addWidget(self._data_mgmt)
        right_col.addWidget(frame4)
        self._sections.append(self._data_mgmt)

        right_col.addStretch()

        cols.addLayout(left_col, 1)
        cols.addLayout(right_col, 1)
        outer.addLayout(cols)

        # store frame references for theme updates
        self._frames = [frame, frame2, frame3, frame4, frame5]

    def apply_theme(self, p: Palette) -> None:
        frame_style = (
            f"QFrame {{ background: {p.bg_surface}; border: 1px solid {p.border};"
            f" border-radius: 8px; }}"
        )
        for frame in self._frames:
            frame.setStyleSheet(frame_style)
        for sec in self._sections:
            if hasattr(sec, "apply_theme"):
                sec.apply_theme(p)
