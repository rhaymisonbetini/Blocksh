from __future__ import annotations

import json
from dataclasses import dataclass, asdict, fields, MISSING

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
    # extended design tokens (with defaults for backward-compat with user themes)
    accent:        str = "#48CAB2"
    accent_hover:  str = "#3db89f"
    accent_fg:     str = "#0d0f1a"
    surface_glass: str = "rgba(22,25,38,0.92)"
    border_focus:  str = "#89b4fa"
    shadow:        str = "rgba(0,0,0,0.35)"
    status_ok:     str = "#a6e3a1"
    status_err:    str = "#f38ba8"
    status_warn:   str = "#f9e2af"
    tag_local_bg:  str = "#1a3a2e"
    tag_local_fg:  str = "#a6e3a1"


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
    border        = "#252840",
    pty_bg        = "#0d0f1a",
    pty_fg        = "#cdd6f4",
    pty_cursor_bg = "#cdd6f4",
    pty_cursor_fg = "#0d0f1a",
    accent        = "#48CAB2",
    accent_hover  = "#3db89f",
    accent_fg     = "#0d0f1a",
    surface_glass = "rgba(22,25,38,0.92)",
    border_focus  = "#89b4fa",
    shadow        = "rgba(0,0,0,0.35)",
    status_ok     = "#a6e3a1",
    status_err    = "#f38ba8",
    status_warn   = "#f9e2af",
    tag_local_bg  = "#1a3a2e",
    tag_local_fg  = "#a6e3a1",
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
    accent        = "#179299",
    accent_hover  = "#0d7e84",
    accent_fg     = "#eff1f5",
    surface_glass = "rgba(230,233,239,0.92)",
    border_focus  = "#1e66f5",
    shadow        = "rgba(0,0,0,0.15)",
    status_ok     = "#40a02b",
    status_err    = "#d20f39",
    status_warn   = "#df8e1d",
    tag_local_bg  = "#d8f0e8",
    tag_local_fg  = "#179299",
)

_BUILT_IN: dict[str, Palette] = {
    DARK.name:  DARK,
    LIGHT.name: LIGHT,
}

_FIELD_NAMES = {f.name for f in fields(Palette)}
_REQUIRED_FIELD_NAMES = {
    f.name for f in fields(Palette)
    if f.default is MISSING and f.default_factory is MISSING  # type: ignore[misc]
}


def _load_palette_from_dict(data: dict) -> Palette | None:
    if not _REQUIRED_FIELD_NAMES <= set(data.keys()):
        return None
    try:
        return Palette(**{k: data[k] for k in _FIELD_NAMES if k in data})
    except Exception:
        return None


def _best_mono_font() -> str:
    try:
        from PySide6.QtGui import QFontDatabase
        available = set(QFontDatabase.families())
        for preferred in ["Ubuntu Mono", "JetBrains Mono", "Fira Code", "Cascadia Code", "Monospace"]:
            if preferred in available:
                return preferred
    except Exception:
        pass
    return "Monospace"


_MONO_FONT: str | None = None


def get_mono_font() -> str:
    """Return the best available monospace font. Lazy — safe to call before QApplication."""
    global _MONO_FONT
    if _MONO_FONT is None:
        _MONO_FONT = _best_mono_font()
    return _MONO_FONT


FONT_FAMILY = "Ubuntu Mono"


@dataclass(frozen=True)
class Typography:
    xs:        int = 10   # timestamps, badges, token names, path labels
    sm:        int = 11   # secondary: sub-labels, muted metadata, helper text
    base:      int = 12   # default: nav items, field labels, descriptions
    md:        int = 13   # body: section titles, buttons, input text
    lg:        int = 15   # headings: panel headings, tab labels
    xl:        int = 18   # large: page titles, settings headers
    xxl:       int = 22   # hero: splash/about titles
    mono_sm:   int = 11   # tool call labels, token values
    mono_base: int = 12   # default output / AI response text
    mono_lg:   int = 13   # command prompt text in blocks


TY = Typography()


@dataclass(frozen=True)
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24


@dataclass(frozen=True)
class Radius:
    sm: int = 6
    md: int = 8
    lg: int = 10
    xl: int = 14


SP = Spacing()
RD = Radius()


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

    def save_user_theme(self, palette: Palette) -> None:
        if palette.name in _BUILT_IN:
            raise ValueError(f"Cannot overwrite built-in theme '{palette.name}'")
        path = THEMES_DIR / f"{palette.name}.json"
        path.write_text(json.dumps(asdict(palette)))
        self._themes[palette.name] = palette
        self.theme_changed.emit(self._current)

    def delete_user_theme(self, name: str) -> None:
        if name in _BUILT_IN:
            return
        (THEMES_DIR / f"{name}.json").unlink(missing_ok=True)
        self._themes.pop(name, None)
        if self._current.name == name:
            self._current = DARK
            self._save_pref(DARK.name)
        self.theme_changed.emit(self._current)

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
