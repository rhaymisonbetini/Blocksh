from PySide6.QtGui import QColor

# Catppuccin Mocha palette mapped to ANSI named colors
_NAMED: dict[str, str | None] = {
    "default":       None,
    "black":         "#1e2235",
    "red":           "#f38ba8",
    "green":         "#a6e3a1",
    "yellow":        "#f9e2af",
    "blue":          "#89b4fa",
    "magenta":       "#cba6f7",
    "cyan":          "#89dceb",
    "white":         "#cdd6f4",
    "brightblack":   "#45475a",
    "brightred":     "#f38ba8",
    "brightgreen":   "#a6e3a1",
    "brightyellow":  "#f9e2af",
    "brightblue":    "#89b4fa",
    "brightmagenta": "#cba6f7",
    "brightcyan":    "#89dceb",
    "brightwhite":   "#ffffff",
}


def _256_to_hex(n: int) -> str:
    _BASE = [
        "#1e2235", "#f38ba8", "#a6e3a1", "#f9e2af",
        "#89b4fa", "#cba6f7", "#89dceb", "#cdd6f4",
        "#45475a", "#f38ba8", "#a6e3a1", "#f9e2af",
        "#89b4fa", "#cba6f7", "#89dceb", "#ffffff",
    ]
    if n < 16:
        return _BASE[n]
    if n < 232:
        n -= 16
        r, g, b = n // 36, (n // 6) % 6, n % 6
        cv = lambda v: 0 if v == 0 else 55 + v * 40
        return f"#{cv(r):02x}{cv(g):02x}{cv(b):02x}"
    v = 8 + (n - 232) * 10
    return f"#{v:02x}{v:02x}{v:02x}"


def _resolve_color(color: str) -> QColor | None:
    if color in _NAMED:
        v = _NAMED[color]
        return QColor(v) if v else None
    if color.startswith("color"):
        return QColor(_256_to_hex(int(color[5:])))
    if "/" in color:
        r, g, b = color.split("/")
        return QColor(int(r), int(g), int(b))
    if color.startswith("#") and len(color) in (4, 7):
        return QColor(color)
    # pyte 0.8.x resolves truecolor and 256-color to a plain 6-digit hex string (no '#')
    if len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color):
        return QColor(f"#{color}")
    return None
