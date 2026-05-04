import re
import subprocess
from abc import ABC, abstractmethod
from ..domain.command import Command
from ..domain.block import Block

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
                env=env,
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
