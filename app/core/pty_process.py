import os
import struct
import fcntl
import termios
import signal
import select
import subprocess
from PySide6.QtCore import QThread, Signal


def _pty_preexec() -> None:
    os.setsid()
    # Designate the PTY slave (fd 0) as the controlling terminal so that
    # ssh, sudo, and programs that open /dev/tty work correctly.
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


class PtyProcess(QThread):
    """Runs a command inside a PTY and streams its output via Qt signals."""

    data_ready       = Signal(bytes)
    process_finished = Signal(int)   # exit code

    def __init__(
        self,
        cmd: str,
        cwd: str,
        env: dict,
        rows: int = 24,
        cols: int = 80,
    ):
        super().__init__()
        self._cmd       = cmd
        self._cwd       = cwd
        self._env       = env
        self._rows      = rows
        self._cols      = cols
        self._master_fd = -1
        self._proc: subprocess.Popen | None = None

    # ── public API ────────────────────────────────────────────────────────────

    def start_process(self) -> None:
        import pty
        self._master_fd, slave_fd = pty.openpty()
        self._set_winsize(slave_fd, self._rows, self._cols)

        self._proc = subprocess.Popen(
            ["/bin/bash", "-c", self._cmd],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            cwd=self._cwd,
            env=self._env,
            preexec_fn=_pty_preexec,
        )
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
        if self._master_fd >= 0:
            try:
                self._set_winsize(self._master_fd, rows, cols)
            except OSError:
                pass
        if self._proc and self._proc.pid:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGWINCH)
            except (OSError, ProcessLookupError):
                pass

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
                    data = os.read(self._master_fd, 4096)
                    if data:
                        self.data_ready.emit(data)
            except OSError:
                break

        exit_code = self._proc.wait() if self._proc else 1
        try:
            os.close(self._master_fd)
        except OSError:
            pass
        self._master_fd = -1
        self.process_finished.emit(exit_code)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _set_winsize(fd: int, rows: int, cols: int) -> None:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
