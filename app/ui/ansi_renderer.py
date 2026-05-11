import re
from PySide6.QtGui import QTextCharFormat, QFont, QColor
from .ansi_colors import _resolve_color

# ── link detection regexes ────────────────────────────────────────────────

_URL_RE   = re.compile(r'https?://[^\s\'"<>\]]+')
_FILE_LINE_RE = re.compile(r'(/[^\s:\'"\)\]]+):(\d+)')
_FILE_RE  = re.compile(r'(?<!["\'])(/[^\s:\'"\)\]]+)(?::(\d+))?')
_PY_TB_RE = re.compile(r'File "([^"]+)", line (\d+)')

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


def render_ansi_with_links(
    text: str,
) -> list[tuple[str, QTextCharFormat]]:
    """Like render_ansi() but also detects URLs and file paths and marks them
    as clickable anchors by setting setAnchor/setAnchorHref on the format."""
    base_segments = render_ansi(text)
    result: list[tuple[str, QTextCharFormat]] = []
    for seg_text, seg_fmt in base_segments:
        result.extend(_inject_links(seg_text, seg_fmt))
    return result


def _inject_links(
    text: str, base_fmt: QTextCharFormat
) -> list[tuple[str, QTextCharFormat]]:
    """Scan text for URLs and file paths; return segments with link formatting."""
    # Collect all matches with their hrefs, sorted by start position
    spans: list[tuple[int, int, str]] = []  # (start, end, href)

    # Python traceback: File "path", line N — highest priority
    for m in _PY_TB_RE.finditer(text):
        path = m.group(1)
        line = int(m.group(2))
        href = f"file://{path}?line={line}"
        spans.append((m.start(), m.end(), href))

    # HTTP URLs
    for m in _URL_RE.finditer(text):
        if not _overlaps(spans, m.start(), m.end()):
            spans.append((m.start(), m.end(), m.group()))

    # Absolute file paths with optional :line
    for m in _FILE_LINE_RE.finditer(text):
        if not _overlaps(spans, m.start(), m.end()):
            path = m.group(1)
            line = int(m.group(2))
            href = f"file://{path}?line={line}"
            spans.append((m.start(), m.end(), href))

    for m in _FILE_RE.finditer(text):
        if not _overlaps(spans, m.start(), m.end()):
            path = m.group(1)
            href = f"file://{path}"
            spans.append((m.start(), m.end(), href))

    if not spans:
        return [(text, base_fmt)]

    spans.sort(key=lambda x: x[0])
    result: list[tuple[str, QTextCharFormat]] = []
    pos = 0
    for start, end, href in spans:
        if pos < start:
            result.append((text[pos:start], QTextCharFormat(base_fmt)))
        link_fmt = QTextCharFormat(base_fmt)
        link_fmt.setAnchor(True)
        link_fmt.setAnchorHref(href)
        link_fmt.setUnderlineStyle(QTextCharFormat.SingleUnderline)
        result.append((text[start:end], link_fmt))
        pos = end
    if pos < len(text):
        result.append((text[pos:], QTextCharFormat(base_fmt)))
    return result


def _overlaps(spans: list[tuple[int, int, str]], start: int, end: int) -> bool:
    return any(s < end and e > start for s, e, _ in spans)
