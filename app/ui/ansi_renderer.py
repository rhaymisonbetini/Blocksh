import re
from PySide6.QtGui import QTextCharFormat, QFont, QColor
from .ansi_colors import _resolve_color

_ESCAPE_RE = re.compile(
    r'\x1b(?:'
    r'\][^\x07\x1b]*(?:\x07|\x1b\\)'   # OSC: ESC ] ... BEL or ST — consume silently
    r'|\[[0-9;?]*[A-Za-z]'              # CSI: ESC [ params letter
    r'|[^[]'                             # ESC + single non-[ char
    r')'
)

_SGR_FG = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
_SGR_BRIGHT_FG = [
    "brightblack", "brightred", "brightgreen", "brightyellow",
    "brightblue", "brightmagenta", "brightcyan", "brightwhite",
]


def _apply_sgr(params: list[int], fmt: QTextCharFormat) -> QTextCharFormat:
    i = 0
    while i < len(params):
        p = params[i]
        if p == 0:
            fmt = QTextCharFormat()
        elif p == 1:
            fmt.setFontWeight(QFont.Bold)
        elif p == 2:
            fmt.setFontWeight(QFont.Light)       # dim
        elif p == 3:
            fmt.setFontItalic(True)
        elif p == 4:
            fmt.setFontUnderline(True)
        elif p == 7:                              # reverse video — swap fg ↔ bg
            fg = fmt.foreground().color()
            bg = fmt.background().color()
            if fg.isValid():
                fmt.setBackground(fg)
            if bg.isValid():
                fmt.setForeground(bg)
        elif p == 9:
            fmt.setFontStrikeOut(True)
        elif p == 22:
            fmt.setFontWeight(QFont.Normal)
        elif p == 23:
            fmt.setFontItalic(False)
        elif p == 24:
            fmt.setFontUnderline(False)
        elif p == 27:                             # no reverse — reset colors
            fmt.clearForeground()
            fmt.clearBackground()
        elif p == 29:
            fmt.setFontStrikeOut(False)
        elif 30 <= p <= 37:
            c = _resolve_color(_SGR_FG[p - 30])
            if c:
                fmt.setForeground(c)
        elif p == 39:
            fmt.clearForeground()
        elif 40 <= p <= 47:
            c = _resolve_color(_SGR_FG[p - 40])
            if c:
                fmt.setBackground(c)
        elif p == 49:
            fmt.clearBackground()
        elif 90 <= p <= 97:
            c = _resolve_color(_SGR_BRIGHT_FG[p - 90])
            if c:
                fmt.setForeground(c)
        elif 100 <= p <= 107:
            c = _resolve_color(_SGR_BRIGHT_FG[p - 100])
            if c:
                fmt.setBackground(c)
        elif p == 38:
            if i + 2 < len(params) and params[i + 1] == 5:
                c = _resolve_color(f"color{params[i + 2]}")
                if c:
                    fmt.setForeground(c)
                i += 2
            elif i + 4 < len(params) and params[i + 1] == 2:
                fmt.setForeground(QColor(params[i + 2], params[i + 3], params[i + 4]))
                i += 4
        elif p == 48:
            if i + 2 < len(params) and params[i + 1] == 5:
                c = _resolve_color(f"color{params[i + 2]}")
                if c:
                    fmt.setBackground(c)
                i += 2
            elif i + 4 < len(params) and params[i + 1] == 2:
                fmt.setBackground(QColor(params[i + 2], params[i + 3], params[i + 4]))
                i += 4
        i += 1
    return fmt


def render_ansi(text: str) -> list[tuple[str, QTextCharFormat]]:
    """Parse ANSI SGR escape sequences and return (text_segment, QTextCharFormat) pairs."""
    result: list[tuple[str, QTextCharFormat]] = []
    current_fmt = QTextCharFormat()
    pos = 0

    for m in _ESCAPE_RE.finditer(text):
        seg = text[pos:m.start()]
        if seg:
            result.append((seg, QTextCharFormat(current_fmt)))
        esc = m.group()
        if esc.startswith("\x1b[") and esc.endswith("m"):
            raw = esc[2:-1]
            try:
                params = [int(x) for x in raw.split(";") if x != ""] if raw else [0]
            except ValueError:
                params = [0]
            current_fmt = _apply_sgr(params, QTextCharFormat(current_fmt))
        pos = m.end()

    remaining = text[pos:]
    if remaining:
        result.append((remaining, QTextCharFormat(current_fmt)))

    return result
