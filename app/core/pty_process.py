import os
import pyte
import struct
import fcntl
import termios
import signal
import select
import subprocess
from PySide6.QtCore import QMutex, QThread, Signal


def _pty_preexec() -> None:
    os.setsid()
    # Designate the PTY slave (fd 0) as the controlling terminal so that
    # ssh, sudo, and programs that open /dev/tty work correctly.
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


# Alternate screen entry/exit sequences (DECSET/DECRST 1049).
# pyte 0.8 has no built-in alt-screen support — we intercept these here so
# that TUI apps (claude, vim, htop, …) draw into a separate buffer and never
# pollute the main scrollback history.
_ALT_ENTER = b"\x1b[?1049h"
_ALT_LEAVE = b"\x1b[?1049l"


class PtyProcess(QThread):
    """Runs a command inside a PTY, feeds pyte off the main thread, and emits render signals."""

    data_ready         = Signal(bytes)   # raw bytes — for escape-sequence detection in PtyWidget
    screen_ready       = Signal(object)  # set of dirty row indices — triggers canvas repaint
    process_finished   = Signal(int)     # exit code
    alt_screen_changed = Signal(bool)    # True = entered alt screen, False = left alt screen

    def __init__(
        self,
        cmd: str,
        cwd: str,
        env: dict,
        rows: int = 24,
        cols: int = 80,
        shell: str = "bash",
        scrollback: int = 2000,
        direct: bool = False,
    ):
        super().__init__()
        self._cmd       = cmd
        self._cwd       = cwd
        self._env       = env
        self._rows      = rows
        self._cols      = cols
        self._shell     = shell
        self._direct    = direct
        self._master_fd = -1
        self._proc: subprocess.Popen | None = None

        # Two pyte buffers: main buffer keeps scrollback history; alt buffer is
        # for full-screen TUI apps and is discarded when they exit.
        self._lock        = QMutex()
        self._screen_main = pyte.HistoryScreen(cols, rows, history=scrollback, ratio=1.0)
        self._screen_alt  = pyte.Screen(cols, rows)
        self._stream_main = pyte.ByteStream(self._screen_main)
        self._stream_alt  = pyte.ByteStream(self._screen_alt)

        # _screen / _stream always point to the active buffer (swapped on 1049 sequences).
        self._in_alt_screen = False
        self._screen = self._screen_main
        self._stream = self._stream_main

    # ── public API ────────────────────────────────────────────────────────────

    def start_process(self) -> None:
        import pty, shlex
        self._master_fd, slave_fd = pty.openpty()
        self._set_winsize(slave_fd, self._rows, self._cols)

        # direct=True: run the command directly (e.g. ssh, vim) — no bash wrapper.
        # This avoids bash -i startup delay and TTY mode changes that can prevent
        # programs like ssh from showing password/key prompts.
        if self._direct:
            args = shlex.split(self._cmd)
        else:
            args = [self._shell, "-i", "-c", self._cmd]

        try:
            self._proc = subprocess.Popen(
                args,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                cwd=self._cwd,
                env=self._env,
                preexec_fn=_pty_preexec,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            err_msg = f"\r\n\x1b[31m[Error] {exc}\x1b[0m\r\n"
            self._stream.feed(err_msg.encode())
            os.close(slave_fd)
            self._master_fd = -1
            self.process_finished.emit(127)
            return
        os.close(slave_fd)
        self.start()   # begins the reader thread

    def write(self, data: bytes) -> None:
        if self._master_fd >= 0:
            try:
                os.write(self._master_fd, data)
            except OSError:
                pass

    def resize(self, rows: int, cols: int) -> None:
        self._rows, self._cols = rows, cols
        self._lock.lock()
        try:
            # Resize both buffers so dimensions stay in sync regardless of which is active.
            self._screen_main.resize(rows, cols)
            self._screen_alt.resize(rows, cols)
        finally:
            self._lock.unlock()
        if self._master_fd >= 0:
            try:
                self._set_winsize(self._master_fd, rows, cols)
            except OSError:
                pass
        # TIOCSWINSZ already delivers SIGWINCH to the process — no manual kill needed

    def terminate(self) -> None:
        if self._proc and self._proc.pid:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass

    # ── reader thread ─────────────────────────────────────────────────────────

    def run(self) -> None:
        while True:
            try:
                r, _, _ = select.select([self._master_fd], [], [], 0.05)
                if r:
                    data = os.read(self._master_fd, 65536)
                    if data:
                        dirty = self._route_and_feed(data)
                        self.data_ready.emit(data)
                        self.screen_ready.emit(dirty)
            except OSError:
                break

        exit_code = self._proc.wait() if self._proc else 1
        try:
            os.close(self._master_fd)
        except OSError:
            pass
        self._master_fd = -1
        self.process_finished.emit(exit_code)

    # ── alt-screen routing ────────────────────────────────────────────────────

    def _route_and_feed(self, data: bytes) -> set:
        """Feed *data* to the correct pyte stream, splitting at ESC[?1049h/l.

        Returns the combined set of dirty row indices for the active screen.
        Emits alt_screen_changed when the active buffer switches.
        """
        dirty = set()
        pos   = 0
        n     = len(data)

        while pos < n:
            ei = data.find(_ALT_ENTER, pos)
            li = data.find(_ALT_LEAVE, pos)

            if ei == -1 and li == -1:
                dirty |= self._feed_active(data[pos:])
                break

            # Pick the earliest switch sequence.
            if ei == -1:
                sw, sw_len, entering = li, len(_ALT_LEAVE), False
            elif li == -1:
                sw, sw_len, entering = ei, len(_ALT_ENTER), True
            elif ei < li:
                sw, sw_len, entering = ei, len(_ALT_ENTER), True
            else:
                sw, sw_len, entering = li, len(_ALT_LEAVE), False

            # Feed everything that comes before the switch sequence.
            if sw > pos:
                dirty |= self._feed_active(data[pos:sw])

            # Perform the buffer swap.
            if entering and not self._in_alt_screen:
                self._in_alt_screen = True
                self._screen_alt.reset()
                self._screen_alt.resize(self._rows, self._cols)
                self._screen = self._screen_alt
                self._stream = self._stream_alt
                self.alt_screen_changed.emit(True)
            elif not entering and self._in_alt_screen:
                self._in_alt_screen = False
                self._screen = self._screen_main
                self._stream = self._stream_main
                self.alt_screen_changed.emit(False)

            pos = sw + sw_len

        return dirty

    def _feed_active(self, chunk: bytes) -> set:
        """Feed *chunk* to the active stream under lock; return dirty rows."""
        if not chunk:
            return set()
        self._lock.lock()
        try:
            self._stream.feed(chunk)
            d = set(self._screen.dirty)
            self._screen.dirty.clear()
        finally:
            self._lock.unlock()
        return d

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _set_winsize(fd: int, rows: int, cols: int) -> None:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
