from html import escape

import pyte
from PySide6.QtCore import Qt, QEvent, QTimer, Signal
from PySide6.QtGui import QFont, QFontMetrics, QKeyEvent
from PySide6.QtWidgets import QSizePolicy, QTextEdit, QVBoxLayout, QWidget

from ..core.pty_process import PtyProcess

# ── colour palette (Catppuccin Mocha) ────────────────────────────────────────

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

_DEFAULT_FG = "#cdd6f4"
_DEFAULT_BG = "#0d0f1a"

# ── key mapping ───────────────────────────────────────────────────────────────

_KEY_MAP: dict[int, bytes] = {
    Qt.Key_Return:   b"\r",
    Qt.Key_Enter:    b"\r",
    Qt.Key_Backspace: b"\x7f",
    Qt.Key_Delete:   b"\x1b[3~",
    Qt.Key_Up:       b"\x1b[A",
    Qt.Key_Down:     b"\x1b[B",
    Qt.Key_Right:    b"\x1b[C",
    Qt.Key_Left:     b"\x1b[D",
    Qt.Key_Home:     b"\x1b[H",
    Qt.Key_End:      b"\x1b[F",
    Qt.Key_PageUp:   b"\x1b[5~",
    Qt.Key_PageDown: b"\x1b[6~",
    Qt.Key_Tab:      b"\t",
    Qt.Key_Escape:   b"\x1b",
    Qt.Key_F1:       b"\x1bOP",
    Qt.Key_F2:       b"\x1bOQ",
    Qt.Key_F3:       b"\x1bOR",
    Qt.Key_F4:       b"\x1bOS",
    Qt.Key_F5:       b"\x1b[15~",
    Qt.Key_F6:       b"\x1b[17~",
    Qt.Key_F7:       b"\x1b[18~",
    Qt.Key_F8:       b"\x1b[19~",
    Qt.Key_F9:       b"\x1b[20~",
    Qt.Key_F10:      b"\x1b[21~",
}


def _resolve_color(pyte_color: str) -> str | None:
    if pyte_color in _NAMED:
        return _NAMED[pyte_color]
    if pyte_color.startswith("color"):
        return _256_to_hex(int(pyte_color[5:]))
    if "/" in pyte_color:
        r, g, b = pyte_color.split("/")
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"
    return None


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


# ─────────────────────────────────────────────────────────────────────────────


class PtyWidget(QWidget):
    """
    Full terminal emulator widget.

    Runs *cmd* inside a PTY, parses VT100/ANSI escape sequences via pyte,
    and renders the virtual screen as styled HTML in a QTextEdit.
    Forwards all keyboard input back to the PTY master.
    """

    session_finished = Signal(int, str)   # (exit_code, final_screen_text)

    def __init__(self, cmd: str, cwd: str, env: dict, parent=None):
        super().__init__(parent)
        self._cmd  = cmd
        self._cwd  = cwd
        self._env  = env

        self._process: PtyProcess | None  = None
        self._screen:  pyte.Screen | None = None
        self._stream:  pyte.ByteStream | None = None
        self._render_pending = False

        self._font = QFont("Monospace", 10)
        fm = QFontMetrics(self._font)
        self._char_w = max(1, fm.horizontalAdvance("M"))
        self._char_h = max(1, fm.height())

        self._build_ui()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._display = QTextEdit()
        self._display.setReadOnly(True)
        self._display.setFont(self._font)
        self._display.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._display.setStyleSheet(
            "QTextEdit { background: #0d0f1a; color: #cdd6f4; border: none; }"
        )
        self._display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Redirect all key events from the display back to PtyWidget so that
        # QTextEdit doesn't consume Space/PageDown/etc. for its own scrolling.
        self._display.setFocusPolicy(Qt.NoFocus)
        self._display.installEventFilter(self)
        layout.addWidget(self._display)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._process is None:
            self._start_pty()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._screen and self._process:
            rows, cols = self._calc_dimensions()
            self._screen.resize(rows, cols)
            self._process.resize(rows, cols)

    def closeEvent(self, event) -> None:
        self._kill_process()
        super().closeEvent(event)

    # ── PTY startup ───────────────────────────────────────────────────────────

    def _start_pty(self) -> None:
        rows, cols = self._calc_dimensions()
        self._screen = pyte.Screen(cols, rows)
        self._stream = pyte.ByteStream(self._screen)

        self._process = PtyProcess(self._cmd, self._cwd, self._env, rows, cols)
        self._process.data_ready.connect(self._on_data)
        self._process.process_finished.connect(self._on_process_finished)
        self._process.start_process()

    def _calc_dimensions(self) -> tuple[int, int]:
        vp = self._display.viewport()
        w  = max(1, vp.width()  if vp.width()  > 0 else self.width())
        h  = max(1, vp.height() if vp.height() > 0 else self.height())
        return max(5, h // self._char_h), max(10, w // self._char_w)

    def _kill_process(self) -> None:
        if self._process:
            self._process.terminate()
            self._process.wait(2000)

    # ── data → render ─────────────────────────────────────────────────────────

    def _on_data(self, data: bytes) -> None:
        self._stream.feed(data)
        if not self._render_pending:
            self._render_pending = True
            QTimer.singleShot(16, self._render)   # coalesce at ~60 fps

    def _render(self) -> None:
        self._render_pending = False
        if self._screen is None:
            return

        buf   = self._screen.buffer
        parts = [
            '<div style="font-family:\'Courier New\',Monospace;font-size:10pt;'
            'background:#0d0f1a;color:#cdd6f4;white-space:pre;">'
        ]

        for y in range(self._screen.lines):
            row = buf[y]
            # group consecutive chars with the same style into one <span>
            spans: list[tuple[str, str, str, bool]] = []
            cur_fg = cur_bg = ""
            cur_bold = False
            cur_chars: list[str] = []

            for x in range(self._screen.columns):
                ch   = row[x]
                data = ch.data or " "
                fg   = _resolve_color(ch.fg) or _DEFAULT_FG
                bg   = _resolve_color(ch.bg) or "transparent"
                bold = ch.bold

                if ch.reverse:
                    fg, bg = (bg if bg != "transparent" else _DEFAULT_BG), fg

                if (fg, bg, bold) != (cur_fg, cur_bg, cur_bold):
                    if cur_chars:
                        spans.append(("".join(cur_chars), cur_fg, cur_bg, cur_bold))
                    cur_fg, cur_bg, cur_bold = fg, bg, bold
                    cur_chars = [escape(data)]
                else:
                    cur_chars.append(escape(data))

            if cur_chars:
                spans.append(("".join(cur_chars), cur_fg, cur_bg, cur_bold))

            for text, fg, bg, bold in spans:
                style = f"color:{fg};"
                if bg and bg != "transparent":
                    style += f"background:{bg};"
                if bold:
                    style += "font-weight:bold;"
                parts.append(f'<span style="{style}">{text}</span>')

            parts.append("<br>")

        parts.append("</div>")

        self._display.setHtml("".join(parts))
        self._display.verticalScrollBar().setValue(0)

    # ── keyboard → PTY ────────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if obj is self._display and event.type() == QEvent.Type.KeyPress:
            self.keyPressEvent(event)
            return True   # prevent QTextEdit from handling it (no scroll on Space)
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._process is None:
            return

        key  = event.key()
        mods = event.modifiers()
        text = event.text()

        if key in _KEY_MAP:
            self._process.write(_KEY_MAP[key])
            return

        if mods & Qt.ControlModifier and text:
            c = ord(text.lower())
            if ord("a") <= c <= ord("z"):
                self._process.write(bytes([c - ord("a") + 1]))
                return

        if text:
            self._process.write(text.encode("utf-8", errors="replace"))

    # ── session end ───────────────────────────────────────────────────────────

    def _on_process_finished(self, exit_code: int) -> None:
        if self._screen:
            lines = [
                "".join(
                    self._screen.buffer[y][x].data or " "
                    for x in range(self._screen.columns)
                ).rstrip()
                for y in range(self._screen.lines)
            ]
            final_text = "\n".join(lines).rstrip()
        else:
            final_text = ""

        self.session_finished.emit(exit_code, final_text)
