import pyte
from PySide6.QtCore import Qt, QMutex, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QKeyEvent, QPainter
from PySide6.QtWidgets import QApplication, QHBoxLayout, QScrollBar, QSizePolicy, QVBoxLayout, QWidget

from ..core.pty_process import PtyProcess
from ..services.settings_service import SettingsService
from ..domain.settings import AppSettings
from .ansi_colors import _NAMED, _256_to_hex, _resolve_color
from .ansi_renderer import _URL_RE
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
    # Qt generates Key_Backtab for Shift+Tab; the ANSI sequence is CSI Z (\x1b[Z)
    Qt.Key_Backtab:   b"\x1b[Z",
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
    # Insert key (used by some TUI apps)
    Qt.Key_Insert:    b"\x1b[2~",
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
        self._url_regions: list[tuple[int, int, int, str]] = []  # (row, col_start, col_end, url)

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

    def update_url_regions(self, screen) -> None:
        """Scan the live screen buffer for clickable URLs (row, col_start, col_end, url)."""
        self._url_regions = []
        if screen is None:
            return
        for row_idx in range(screen.lines):
            row = screen.buffer[row_idx]
            line_text = "".join(row[col].data or " " for col in range(screen.columns))
            for m in _URL_RE.finditer(line_text):
                url = m.group().rstrip(".,;:!?)]}")
                if url:
                    self._url_regions.append((row_idx, m.start(), m.start() + len(url), url))

    def apply_theme(self, p: Palette) -> None:
        self._color_bg        = QColor(p.pty_bg)
        self._color_fg        = QColor(p.pty_fg)
        self._color_cursor_bg = QColor(p.pty_cursor_bg)
        self._color_cursor_fg = QColor(p.pty_cursor_fg)
        self.update()

    def paintEvent(self, _event) -> None:
        if self._screen is None:
            # PTY not yet started — paint background so no garbage shows
            p = QPainter(self)
            p.fillRect(self.rect(), self._color_bg)
            p.end()
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
            painter.fillRect(self.rect(), self._color_bg)

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

                    is_cursor = (offset == 0 and not cur_hidden
                                 and y == cur_row and x == cur_col)

                    px = x * cw

                    if is_cursor:
                        cursor_style = SettingsService.instance().get().cursor_style
                        if cursor_style == "underline":
                            painter.fillRect(px, py, cw, ch, bg)
                            painter.setFont(self._font_bold if cell.bold else self._font)
                            painter.setPen(fg)
                            painter.drawText(px, py + ascent, data)
                            painter.fillRect(px, py + ch - 2, cw, 2, self._color_cursor_bg)
                        elif cursor_style == "beam":
                            painter.fillRect(px, py, cw, ch, bg)
                            painter.setFont(self._font_bold if cell.bold else self._font)
                            painter.setPen(fg)
                            painter.drawText(px, py + ascent, data)
                            painter.fillRect(px, py, 2, ch, self._color_cursor_bg)
                        else:  # block (default)
                            painter.fillRect(px, py, cw, ch, self._color_cursor_bg)
                            painter.setFont(self._font_bold if cell.bold else self._font)
                            painter.setPen(self._color_cursor_fg)
                            painter.drawText(px, py + ascent, data)
                    else:
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

    def __init__(self, cmd: str, cwd: str, env: dict, parent=None, direct: bool = False):
        super().__init__(parent)
        self._cmd    = cmd
        self._cwd    = cwd
        self._env    = env
        self._direct = direct

        self._process: PtyProcess | None = None
        self._render_pending = False

        self._bracketed_paste = False
        self._mouse_mode      = 0    # 0=off, 1000=X10, 1002=button, 1003=any

        # #42: prefer fonts with box-drawing character coverage; respect user settings
        _s = SettingsService.instance().get()
        self._font = QFont()
        self._font.setFamilies([_s.font_family, "DejaVu Sans Mono", "Noto Mono", "Monospace"])
        self._font.setStyleHint(QFont.Monospace)
        self._font.setPointSize(_s.font_size_terminal)
        fm = QFontMetrics(self._font)
        self._char_w = max(1, fm.horizontalAdvance("M"))
        self._char_h = max(1, fm.height())

        self._build_ui()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_resize)

        self._at_bottom = True

        # Two-stage post-resize render suppression:
        # settle_timer fires 150ms after the last screen_ready chunk (output stopped).
        # max_timer fires after 500ms regardless — prevents freeze on continuous output.
        # All screen_ready signals are blocked while _in_post_resize is True.
        self._in_post_resize = False
        self._post_resize_settle_timer = QTimer(self)
        self._post_resize_settle_timer.setSingleShot(True)
        self._post_resize_settle_timer.timeout.connect(self._render_after_resize)
        self._post_resize_max_timer = QTimer(self)
        self._post_resize_max_timer.setSingleShot(True)
        self._post_resize_max_timer.timeout.connect(self._render_after_resize)

        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        SettingsService.instance().settings_changed.connect(self._on_settings_changed)

    def focusNextPrevChild(self, _next: bool) -> bool:
        # Prevent Qt from consuming Tab/Shift+Tab for UI focus navigation.
        # Without this override, Qt intercepts Tab in focusNextPrevChild()
        # *before* keyPressEvent() runs — so _KEY_MAP never sees it and the
        # byte never reaches the PTY process.  Same pattern used by _HistoryInput.
        return False

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
            # Defer PTY startup by one cycle so Qt finalises the widget geometry
            # before we calculate rows/cols and request keyboard focus (#103, #45).
            QTimer.singleShot(0, self._start_pty)
        # Explicitly claim focus when the widget becomes visible so the user
        # can type immediately without needing to click.
        QTimer.singleShot(0, lambda: self.setFocus(Qt.OtherFocusReason))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_timer.start(80)

    def _apply_resize(self) -> None:
        rows, cols = self._calc_dimensions()
        if self._process and (rows != self._process._rows or cols != self._process._cols):
            self._process.resize(rows, cols)
            self._in_post_resize = True
            self._post_resize_settle_timer.start(150)
            self._post_resize_max_timer.start(500)
        self._canvas.update()

    def _render_after_resize(self) -> None:
        """Render once when post-resize output settles (or max wait expires)."""
        self._post_resize_settle_timer.stop()
        self._post_resize_max_timer.stop()
        self._in_post_resize = False
        self._render_pending = False
        self._render()

    def closeEvent(self, event) -> None:
        self._kill_process()
        super().closeEvent(event)

    # ── PTY startup ───────────────────────────────────────────────────────────

    def _start_pty(self) -> None:
        rows, cols = self._calc_dimensions()

        # Declare full color capabilities so TUI apps (claude, vim, htop…) use
        # their rich rendering paths instead of falling back to dumb/monochrome.
        env = dict(self._env)
        env["TERM"]      = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        _s2 = SettingsService.instance().get()
        self._process = PtyProcess(
            self._cmd, self._cwd, env, rows, cols,
            shell=_s2.default_shell,
            scrollback=_s2.scrollback_lines,
            direct=self._direct,
        )
        # canvas shares screen reference; lock protects concurrent reads during paintEvent
        self._canvas.set_screen(self._process._screen, self._process._lock)

        self._process.data_ready.connect(self._on_data)
        self._process.screen_ready.connect(self._on_screen_ready)
        self._process.process_finished.connect(self._on_process_finished)
        self._process.alt_screen_changed.connect(self._on_alt_screen_changed)
        self._process.start_process()
        # Force immediate render so the user sees the terminal background
        # and cursor right away, rather than a black frame until first data arrives.
        self._canvas.update()

    def _calc_dimensions(self) -> tuple[int, int]:
        w = max(1, self._canvas.width()  or self.width())
        h = max(1, self._canvas.height() or self.height())
        return max(5, h // self._char_h), max(10, w // self._char_w)

    def _disconnect_process_signals(self) -> None:
        """Sever all signal connections from PtyProcess before the widget is destroyed.

        Without this, if the PTY thread emits data_ready or screen_ready after
        deleteLater() has been called, Qt tries to invoke slots on a dead object
        which causes a segfault or assertion failure.
        """
        if self._process is None:
            return
        for sig in (
            self._process.data_ready,
            self._process.screen_ready,
            self._process.process_finished,
            self._process.alt_screen_changed,
        ):
            try:
                sig.disconnect()
            except RuntimeError:
                pass  # already disconnected

    def _kill_process(self) -> None:
        if self._process:
            self._disconnect_process_signals()
            self._process.terminate()
            self._process.wait(2000)

    def _on_alt_screen_changed(self, entered: bool) -> None:
        """Swap the canvas to the newly active pyte screen after a 1049 switch."""
        if not self._process:
            return
        self._canvas.set_screen(self._process._screen, self._process._lock)
        if entered:
            # Alt screen has no scrollback — hide the scrollbar immediately.
            self._scrollbar.setValue(0)
            self._scrollbar.hide()
            self._at_bottom = True
        else:
            # Returned to main screen — refresh scrollbar from main history.
            self._render_pending = False
            self._render()

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
        if self._in_post_resize:
            # Restart the settle window on every new chunk: render fires 150ms
            # after output stops, preventing any intermediate redraw frame from
            # being shown (the "scroll through history" visual effect).
            self._post_resize_settle_timer.start(150)
            return
        if not self._render_pending:
            self._render_pending = True
            QTimer.singleShot(33, self._render)

    def _render(self) -> None:
        self._render_pending = False
        if self._process is None:
            return
        screen = self._process._screen
        self._canvas.update_url_regions(screen)
        # pyte.Screen (alt buffer) has no .history; HistoryScreen (main buffer) does.
        H = len(screen.history.top) if hasattr(screen, "history") else 0
        if H > 0:
            self._scrollbar.setMaximum(H)
            self._scrollbar.setPageStep(screen.lines)
            self._scrollbar.show()
            if self._at_bottom and self._scrollbar.value() != 0:
                self._scrollbar.setValue(0)
        else:
            if self._scrollbar.value() != 0:
                self._scrollbar.setValue(0)
            self._scrollbar.hide()
        self._canvas.update()

    # ── scroll ────────────────────────────────────────────────────────────────

    def _on_scroll(self, value: int) -> None:
        self._at_bottom = (value == 0)
        self._canvas.set_scroll_offset(value)

    def wheelEvent(self, event) -> None:
        if self._scrollbar.isVisible():
            delta = 3 if event.angleDelta().y() > 0 else -3
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
        elif (event.button() == Qt.LeftButton
              and self._scrollbar.value() == 0
              and self._canvas._url_regions):
            col = int(event.position().x()) // self._char_w
            row = int(event.position().y()) // self._char_h
            for r, cs, ce, url in self._canvas._url_regions:
                if r == row and cs <= col < ce:
                    QDesktopServices.openUrl(QUrl(url))
                    return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._mouse_mode >= 1000 and self._process:
            self._send_mouse(3, int(event.position().x()), int(event.position().y()))
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._mouse_mode >= 1002 and self._process:
            self._send_mouse(32, int(event.position().x()), int(event.position().y()))
        elif self._mouse_mode < 1000 and self._scrollbar.value() == 0 and self._canvas._url_regions:
            col = int(event.position().x()) // self._char_w
            row = int(event.position().y()) // self._char_h
            on_link = any(r == row and cs <= col < ce for r, cs, ce, _ in self._canvas._url_regions)
            self._canvas.setCursor(Qt.PointingHandCursor if on_link else Qt.IBeamCursor)
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

    def _on_settings_changed(self, s: AppSettings) -> None:
        self._font = QFont()
        self._font.setFamilies([s.font_family, "DejaVu Sans Mono", "Noto Mono", "Monospace"])
        self._font.setStyleHint(QFont.Monospace)
        self._font.setPointSize(s.font_size_terminal)
        fm = QFontMetrics(self._font)
        self._char_w = max(1, fm.horizontalAdvance("M"))
        self._char_h = max(1, fm.height())
        self._canvas._font = self._font
        self._canvas._font_bold = QFont(self._font)
        self._canvas._font_bold.setBold(True)
        self._canvas._char_w = self._char_w
        self._canvas._char_h = self._char_h
        self._canvas._ascent = fm.ascent()
        self._canvas.update()

    def show_exit_banner(self, exit_code: int) -> None:
        if self._process:
            color = "\x1b[32m" if exit_code == 0 else "\x1b[33m"
            msg = f"\r\n{color}[Session ended — exit {exit_code}]\x1b[0m\r\n"
            self._process._stream.feed(msg.encode())
            self._canvas.update()

    def _on_process_finished(self, exit_code: int) -> None:
        # If the app exited while in alt screen (without sending ESC[?1049l),
        # restore the main screen so history and scrollback are visible again.
        if self._process and self._process._in_alt_screen:
            self._process._in_alt_screen = False
            self._process._screen = self._process._screen_main
            self._process._stream = self._process._stream_main
            self._canvas.set_screen(self._process._screen_main, self._process._lock)

        screen = self._process._screen if self._process else None
        self._render_pending = False
        self._canvas.update()

        if screen:
            hist_top = list(screen.history.top) if hasattr(screen, "history") else []
            hist_lines = [
                "".join(row[x].data or " " for x in range(screen.columns)).rstrip()
                for row in hist_top
            ]
            curr_lines = [
                "".join(
                    screen.buffer[y][x].data or " "
                    for x in range(screen.columns)
                ).rstrip()
                for y in range(screen.lines)
            ]
            all_lines = hist_lines + curr_lines
            final_text = "\n".join(all_lines[-500:]).rstrip()
        else:
            final_text = ""

        self.session_finished.emit(exit_code, final_text)
