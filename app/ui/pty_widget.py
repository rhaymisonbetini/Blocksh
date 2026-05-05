import pyte
from PySide6.QtCore import Qt, QMutex, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeyEvent, QPainter
from PySide6.QtWidgets import QApplication, QHBoxLayout, QScrollBar, QSizePolicy, QVBoxLayout, QWidget

from ..core.pty_process import PtyProcess
from .ansi_colors import _NAMED, _256_to_hex, _resolve_color
from .theme import Palette, ThemeManager

_DEFAULT_FG = "#cdd6f4"
_DEFAULT_BG = "#0d0f1a"

_COLOR_BG   = QColor(_DEFAULT_BG)
_COLOR_FG   = QColor(_DEFAULT_FG)
_COLOR_CUR  = QColor("#cdd6f4")
_COLOR_CURT = QColor(_DEFAULT_BG)

# pyte encodes DEC private mode N as N*32; DECCKM = mode 1 → 32
_DECCKM = 32

# ── key mapping ───────────────────────────────────────────────────────────────

_KEY_MAP: dict[int, bytes] = {
    Qt.Key_Return:    b"\r",
    Qt.Key_Enter:     b"\r",
    Qt.Key_Backspace: b"\x7f",
    Qt.Key_Delete:    b"\x1b[3~",
    Qt.Key_Up:        b"\x1b[A",
    Qt.Key_Down:      b"\x1b[B",
    Qt.Key_Right:     b"\x1b[C",
    Qt.Key_Left:      b"\x1b[D",
    Qt.Key_Home:      b"\x1b[H",
    Qt.Key_End:       b"\x1b[F",
    Qt.Key_PageUp:    b"\x1b[5~",
    Qt.Key_PageDown:  b"\x1b[6~",
    Qt.Key_Tab:       b"\t",
    Qt.Key_Escape:    b"\x1b",
    Qt.Key_F1:        b"\x1bOP",
    Qt.Key_F2:        b"\x1bOQ",
    Qt.Key_F3:        b"\x1bOR",
    Qt.Key_F4:        b"\x1bOS",
    Qt.Key_F5:        b"\x1b[15~",
    Qt.Key_F6:        b"\x1b[17~",
    Qt.Key_F7:        b"\x1b[18~",
    Qt.Key_F8:        b"\x1b[19~",
    Qt.Key_F9:        b"\x1b[20~",
    Qt.Key_F10:       b"\x1b[21~",
    Qt.Key_F11:       b"\x1b[23~",
    Qt.Key_F12:       b"\x1b[24~",
}

# SS3 sequences used when DECCKM (application cursor keys) is active
_KEY_MAP_APP: dict[int, bytes] = {
    Qt.Key_Up:    b"\x1bOA",
    Qt.Key_Down:  b"\x1bOB",
    Qt.Key_Right: b"\x1bOC",
    Qt.Key_Left:  b"\x1bOD",
}


# ── canvas ────────────────────────────────────────────────────────────────────


class _PtyCanvas(QWidget):
    """
    Direct QPainter renderer for a pyte screen buffer.

    Each character is drawn at exactly (col * char_w, row * char_h) —
    fixed grid, no HTML, no layout engine. Acquires the process lock
    before reading the screen buffer to prevent data races with pyte
    feeding in the PTY thread.
    """

    def __init__(self, font: QFont, char_w: int, char_h: int, parent=None):
        super().__init__(parent)
        self._font      = font
        self._font_bold = QFont(font)
        self._font_bold.setBold(True)
        self._char_w    = char_w
        self._char_h    = char_h
        self._ascent    = QFontMetrics(font).ascent()
        self._screen: pyte.Screen | None = None
        self._lock:   QMutex | None = None
        self._scroll_offset: int = 0

        p = ThemeManager.instance().current
        self._color_bg        = QColor(p.pty_bg)
        self._color_fg        = QColor(p.pty_fg)
        self._color_cursor_bg = QColor(p.pty_cursor_bg)
        self._color_cursor_fg = QColor(p.pty_cursor_fg)

        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def set_screen(self, screen: pyte.Screen, lock: QMutex) -> None:
        self._screen = screen
        self._lock   = lock

    def set_scroll_offset(self, offset: int) -> None:
        self._scroll_offset = offset
        self.update()

    def apply_theme(self, p: Palette) -> None:
        self._color_bg        = QColor(p.pty_bg)
        self._color_fg        = QColor(p.pty_fg)
        self._color_cursor_bg = QColor(p.pty_cursor_bg)
        self._color_cursor_fg = QColor(p.pty_cursor_fg)
        self.update()

    def paintEvent(self, _event) -> None:
        if self._screen is None:
            return

        # #38/#39: acquire lock to prevent races with PtyProcess.run() feeding pyte
        if self._lock and not self._lock.tryLock(16):
            # skip this paint cycle if PTY thread is busy; next screen_ready will re-trigger
            return

        try:
            buf    = self._screen.buffer
            offset = self._scroll_offset

            if offset > 0:
                hist_top     = list(self._screen.history.top)
                H            = len(hist_top)
                hist_portion = min(offset, H)
            else:
                hist_top = []; H = 0; hist_portion = 0

            cur_row    = self._screen.cursor.y
            cur_col    = self._screen.cursor.x
            cur_hidden = getattr(self._screen.cursor, "hidden", False)

            cw      = self._char_w
            ch      = self._char_h
            ascent  = self._ascent
            painter = QPainter(self)

            for y in range(self._screen.lines):
                py = y * ch
                if y < hist_portion:
                    row = hist_top[H - hist_portion + y]
                else:
                    row = buf[y - hist_portion]

                for x in range(self._screen.columns):
                    cell = row[x]
                    data = cell.data or " "

                    fg: QColor = _resolve_color(cell.fg) or self._color_fg
                    bg: QColor = _resolve_color(cell.bg) or self._color_bg

                    if cell.reverse:
                        fg, bg = bg, fg

                    if offset == 0 and not cur_hidden and y == cur_row and x == cur_col:
                        fg, bg = self._color_cursor_fg, self._color_cursor_bg

                    px = x * cw

                    painter.fillRect(px, py, cw, ch, bg)
                    painter.setFont(self._font_bold if cell.bold else self._font)
                    painter.setPen(fg)
                    painter.drawText(px, py + ascent, data)

            painter.end()
        finally:
            if self._lock:
                self._lock.unlock()


# ── widget ────────────────────────────────────────────────────────────────────


class PtyWidget(QWidget):
    """
    Full terminal emulator widget.

    Runs *cmd* inside a PTY via PtyProcess. pyte parsing happens in the PTY
    thread; main thread only renders via QPainter on a fixed character grid.
    """

    session_finished = Signal(int, str)   # (exit_code, final_screen_text)

    def __init__(self, cmd: str, cwd: str, env: dict, parent=None):
        super().__init__(parent)
        self._cmd = cmd
        self._cwd = cwd
        self._env = env

        self._process: PtyProcess | None = None
        self._render_pending = False

        self._bracketed_paste = False
        self._mouse_mode      = 0    # 0=off, 1000=X10, 1002=button, 1003=any

        self._font = QFont("Monospace", 10)
        fm = QFontMetrics(self._font)
        self._char_w = max(1, fm.horizontalAdvance("M"))
        self._char_h = max(1, fm.height())

        self._build_ui()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        _tm = ThemeManager.instance()
        _tm.theme_changed.connect(self._on_theme_changed)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._canvas = _PtyCanvas(self._font, self._char_w, self._char_h)
        row.addWidget(self._canvas)

        self._scrollbar = QScrollBar(Qt.Vertical)
        self._scrollbar.setInvertedAppearance(True)  # 0 = bottom (live), max = top (oldest)
        self._scrollbar.setMinimum(0)
        self._scrollbar.setSingleStep(1)
        self._scrollbar.hide()
        self._scrollbar.valueChanged.connect(self._on_scroll)
        row.addWidget(self._scrollbar)

        outer.addLayout(row)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._process is None:
            self._start_pty()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._process:
            rows, cols = self._calc_dimensions()
            self._process.resize(rows, cols)  # resize() now locks internally

    def closeEvent(self, event) -> None:
        self._kill_process()
        super().closeEvent(event)

    # ── PTY startup ───────────────────────────────────────────────────────────

    def _start_pty(self) -> None:
        rows, cols = self._calc_dimensions()

        self._process = PtyProcess(self._cmd, self._cwd, self._env, rows, cols)
        # canvas shares screen reference; lock protects concurrent reads during paintEvent
        self._canvas.set_screen(self._process._screen, self._process._lock)

        self._process.data_ready.connect(self._on_data)
        self._process.screen_ready.connect(self._on_screen_ready)
        self._process.process_finished.connect(self._on_process_finished)
        self._process.start_process()

    def _calc_dimensions(self) -> tuple[int, int]:
        w = max(1, self._canvas.width()  or self.width())
        h = max(1, self._canvas.height() or self.height())
        return max(5, h // self._char_h), max(10, w // self._char_w)

    def _kill_process(self) -> None:
        if self._process:
            self._process.terminate()
            self._process.wait(2000)

    # ── data → render ─────────────────────────────────────────────────────────

    def _on_data(self, data: bytes) -> None:
        """Raw bytes from PTY — used only for escape-sequence mode detection."""
        # track bracketed paste mode
        if b"\x1b[?2004h" in data:
            self._bracketed_paste = True
        elif b"\x1b[?2004l" in data:
            self._bracketed_paste = False

        # track mouse reporting mode
        for seq, mode in (
            (b"\x1b[?1003h", 1003),
            (b"\x1b[?1002h", 1002),
            (b"\x1b[?1000h", 1000),
            (b"\x1b[?1000l", 0),
        ):
            if seq in data:
                self._mouse_mode = mode
                self._canvas.setMouseTracking(mode >= 1002)
                break

    def _on_screen_ready(self, dirty: set) -> None:
        """Called after PtyProcess has fed pyte in its thread; schedule repaint."""
        if not self._render_pending:
            self._render_pending = True
            QTimer.singleShot(33, self._render)

    def _render(self) -> None:
        self._render_pending = False
        if self._process is None:
            return
        screen = self._process._screen
        H = len(screen.history.top)
        if H > 0:
            self._scrollbar.setMaximum(H)
            self._scrollbar.setPageStep(screen.lines)
            self._scrollbar.show()
        else:
            self._scrollbar.hide()
        self._canvas.update()

    # ── scroll ────────────────────────────────────────────────────────────────

    def _on_scroll(self, value: int) -> None:
        self._canvas.set_scroll_offset(value)

    def wheelEvent(self, event) -> None:
        if self._scrollbar.isVisible():
            delta = -3 if event.angleDelta().y() > 0 else 3
            self._scrollbar.setValue(self._scrollbar.value() + delta)
        else:
            super().wheelEvent(event)

    # ── mouse → PTY ───────────────────────────────────────────────────────────

    def _send_mouse(self, btn: int, x: int, y: int) -> None:
        col = max(1, min(223, x // self._char_w + 1))
        row = max(1, min(223, y // self._char_h + 1))
        self._process.write(b"\x1b[M" + bytes([32 + btn, 32 + col, 32 + row]))

    def mousePressEvent(self, event) -> None:
        if self._mouse_mode >= 1000 and self._process:
            self.setFocus()
            btn = {Qt.LeftButton: 0, Qt.MiddleButton: 1, Qt.RightButton: 2}.get(event.button(), 3)
            self._send_mouse(btn, int(event.position().x()), int(event.position().y()))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._mouse_mode >= 1000 and self._process:
            self._send_mouse(3, int(event.position().x()), int(event.position().y()))
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._mouse_mode >= 1002 and self._process:
            self._send_mouse(32, int(event.position().x()), int(event.position().y()))
        super().mouseMoveEvent(event)

    # ── keyboard → PTY ────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._process is None:
            return

        key  = event.key()
        mods = event.modifiers()
        text = event.text()

        # Shift+PgUp/PgDn for scrollback navigation
        if mods & Qt.ShiftModifier:
            screen = self._process._screen
            if key == Qt.Key_PageUp:
                self._scrollbar.setValue(self._scrollbar.value() + screen.lines)
                return
            if key == Qt.Key_PageDown:
                self._scrollbar.setValue(self._scrollbar.value() - screen.lines)
                return

        # any keystroke while scrolled returns to live view
        if self._scrollbar.isVisible() and self._scrollbar.value() > 0:
            self._scrollbar.setValue(0)

        # Ctrl+V — bracketed paste
        if key == Qt.Key_V and mods & Qt.ControlModifier:
            clip = QApplication.clipboard().text()
            if clip:
                if self._bracketed_paste:
                    self._process.write(
                        b"\x1b[200~" + clip.encode("utf-8", errors="replace") + b"\x1b[201~"
                    )
                else:
                    self._process.write(clip.encode("utf-8", errors="replace"))
            return

        # DECCKM active — use SS3 sequences for arrow keys
        screen = self._process._screen
        if _DECCKM in screen.mode:
            if key in _KEY_MAP_APP:
                self._process.write(_KEY_MAP_APP[key])
                return

        if key in _KEY_MAP:
            self._process.write(_KEY_MAP[key])
            return

        # Ctrl+key — use event.key() for reliable mapping (text() is unreliable under Ctrl)
        if mods & Qt.ControlModifier:
            k = event.key()
            if Qt.Key_A <= k <= Qt.Key_Z:
                self._process.write(bytes([k - Qt.Key_A + 1]))
                return
            if k == Qt.Key_At:
                self._process.write(b"\x00")
                return
            if k == Qt.Key_BracketLeft:
                self._process.write(b"\x1b")
                return
            if k == Qt.Key_Backslash:
                self._process.write(b"\x1c")
                return

        if text:
            self._process.write(text.encode("utf-8", errors="replace"))

    # ── session end ───────────────────────────────────────────────────────────

    def _on_theme_changed(self, p: Palette) -> None:
        self._canvas.apply_theme(p)

    def _on_process_finished(self, exit_code: int) -> None:
        screen = self._process._screen if self._process else None

        if screen and self._process:
            # force restore of main screen buffer if the app exited without ESC[?1049l
            # PTY thread is done at this point so no lock needed
            self._process._stream.feed(b"\x1b[?1049l")
        self._render_pending = False
        self._canvas.update()

        if screen:
            lines = [
                "".join(
                    screen.buffer[y][x].data or " "
                    for x in range(screen.columns)
                ).rstrip()
                for y in range(screen.lines)
            ]
            final_text = "\n".join(lines).rstrip()
        else:
            final_text = ""

        self.session_finished.emit(exit_code, final_text)
