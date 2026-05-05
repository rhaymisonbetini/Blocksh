import os
import re
import signal
import subprocess
from abc import ABC, abstractmethod
from PySide6.QtCore import QThread, Signal
from ..domain.command import Command
from ..domain.block import Block

def _color_env(env: dict | None) -> dict:
    base = env if env is not None else os.environ.copy()
    return {
        **base,
        "TERM":           "xterm-256color",
        "COLORTERM":      "truecolor",
        "FORCE_COLOR":    "1",
        "CLICOLOR_FORCE": "1",
        "CLICOLOR":       "1",
    }


# Bash emits these to stderr when run with -i but without a real terminal.
# Filter them so they don't pollute command output.
_BASH_NOISE = re.compile(
    r"^bash: (cannot set terminal process group.*|no job control in this shell.*)\n?",
    re.MULTILINE,
)


class BaseExecutor(ABC):
    @abstractmethod
    def execute(
        self,
        command: Command,
        cwd: str | None = None,
        env: dict | None = None,
    ) -> Block:
        ...


class SubprocessExecutor(BaseExecutor):
    def execute(
        self,
        command: Command,
        cwd: str | None = None,
        env: dict | None = None,
    ) -> Block:
        command.status = "running"
        try:
            result = subprocess.run(
                ["bash", "-i", "-c", command.text],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                cwd=cwd,
                env=_color_env(env),
                preexec_fn=os.setsid,
            )
            command.status = "done" if result.returncode == 0 else "error"
            stderr = _BASH_NOISE.sub("", result.stderr).strip()
            return Block(
                command=command,
                stdout=result.stdout,
                stderr=stderr,
                exit_code=result.returncode,
                cwd=cwd or "",
            )
        except Exception as e:
            command.status = "error"
            return Block(command=command, stderr=str(e), exit_code=1, cwd=cwd or "")


class CommandThread(QThread):
    output_received = Signal(str)
    finished        = Signal(object)  # Block

    def __init__(self, command: Command, cwd: str, env: dict):
        super().__init__()
        self._command = command
        self._cwd     = cwd
        self._env     = env
        self._proc    = None

    def run(self) -> None:
        self._command.status = "running"
        collected = []
        exit_code = 1
        try:
            self._proc = subprocess.Popen(
                ["bash", "-i", "-c", self._command.text],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=False,    # raw bytes — avoids readline() blocking on partial lines
                bufsize=0,
                cwd=self._cwd,
                env=_color_env(self._env),
                preexec_fn=os.setsid,
            )
            while True:
                chunk = self._proc.stdout.read(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                if _BASH_NOISE.match(text):
                    continue
                collected.append(text)
                self.output_received.emit(text)
            self._proc.wait()
            exit_code = self._proc.returncode
        except Exception as e:
            err = str(e)
            collected.append(err)
            self.output_received.emit(err)
        finally:
            self._proc = None

        self._command.status = "done" if exit_code == 0 else "error"
        self.finished.emit(Block(
            command=self._command,
            stdout="".join(collected),
            stderr="",
            exit_code=exit_code,
            cwd=self._cwd or "",
        ))

    def stop(self) -> None:
        if self._proc is not None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
