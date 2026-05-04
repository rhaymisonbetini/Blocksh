from __future__ import annotations

import json
from dataclasses import dataclass, asdict, fields

from PySide6.QtCore import QObject, Signal

from ..infra.config.settings import THEMES_DIR, THEME_PREF_PATH


@dataclass
class Palette:
    name: str
    # backgrounds
    bg: str
    bg_panel: str
    bg_surface: str
    bg_overlay: str
    bg_hover: str
    bg_hover2: str
    bg_active: str
    bg_selected: str
    bg_highlight: str
    # foreground
    fg: str
    fg_muted: str
    fg_dim: str
    # semantic
    blue: str
    green: str
    red: str
    red_ui: str
    cyan: str
    # borders
    border: str
    # pty
    pty_bg: str
    pty_fg: str
    pty_cursor_bg: str
    pty_cursor_fg: str


DARK = Palette(
    name          = "dark",
    bg            = "#0d0f1a",
    bg_panel      = "#10121e",
    bg_surface    = "#161926",
    bg_overlay    = "#1e2235",
    bg_hover      = "#181b2e",
    bg_hover2     = "#252840",
    bg_active     = "#1e3a6e",
    bg_selected   = "#2a3f6e",
    bg_highlight  = "#1e2a3a",
    fg            = "#cdd6f4",
    fg_muted      = "#6c7086",
    fg_dim        = "#45475a",
    blue          = "#89b4fa",
    green         = "#a6e3a1",
    red           = "#f38ba8",
    red_ui        = "#e74c3c",
    cyan          = "#94e2d5",
    border        = "#313244",
    pty_bg        = "#0d0f1a",
    pty_fg        = "#cdd6f4",
    pty_cursor_bg = "#cdd6f4",
    pty_cursor_fg = "#0d0f1a",
)

LIGHT = Palette(
    name          = "light",
    bg            = "#eff1f5",
    bg_panel      = "#e6e9ef",
    bg_surface    = "#dce0e8",
    bg_overlay    = "#ccd0da",
    bg_hover      = "#e0e3ed",
    bg_hover2     = "#d4d7e3",
    bg_active     = "#bcd0f8",
    bg_selected   = "#a8c4f6",
    bg_highlight  = "#c8d8f8",
    fg            = "#4c4f69",
    fg_muted      = "#7287a4",
    fg_dim        = "#9ca0b0",
    blue          = "#1e66f5",
    green         = "#40a02b",
    red           = "#d20f39",
    red_ui        = "#d20f39",
    cyan          = "#179299",
    border        = "#bcc0cc",
    pty_bg        = "#eff1f5",
    pty_fg        = "#4c4f69",
    pty_cursor_bg = "#4c4f69",
    pty_cursor_fg = "#eff1f5",
)

_BUILT_IN: dict[str, Palette] = {
    DARK.name:  DARK,
    LIGHT.name: LIGHT,
}

_FIELD_NAMES = {f.name for f in fields(Palette)}


def _load_palette_from_dict(data: dict) -> Palette | None:
    if not _FIELD_NAMES <= set(data.keys()):
        return None
    try:
        return Palette(**{k: data[k] for k in _FIELD_NAMES})
    except Exception:
        return None


class ThemeManager(QObject):
    theme_changed = Signal(object)   # emits Palette

    _instance: ThemeManager | None = None

    @classmethod
    def instance(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._themes: dict[str, Palette] = dict(_BUILT_IN)
        self._reload_user_themes()

        active = self._load_pref()
        self._current: Palette = self._themes.get(active, DARK)

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def current(self) -> Palette:
        return self._current

    def all_themes(self) -> list[Palette]:
        return list(self._themes.values())

    def set_theme(self, name: str) -> None:
        palette = self._themes.get(name)
        if palette is None or palette is self._current:
            return
        self._current = palette
        self._save_pref(name)
        self.theme_changed.emit(palette)

    def reload_user_themes(self) -> None:
        self._reload_user_themes()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load_pref(self) -> str:
        try:
            data = json.loads(THEME_PREF_PATH.read_text())
            return data.get("active", "dark")
        except Exception:
            return "dark"

    def _save_pref(self, name: str) -> None:
        try:
            THEME_PREF_PATH.write_text(json.dumps({"active": name}))
        except Exception:
            pass

    def _reload_user_themes(self) -> None:
        for path in sorted(THEMES_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                p = _load_palette_from_dict(data)
                if p and p.name not in _BUILT_IN:
                    self._themes[p.name] = p
            except Exception:
                pass
