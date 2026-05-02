from abc import ABC, abstractmethod
import subprocess
from ..domain.command import Command
from ..domain.block import Block


class BaseExecutor(ABC):
    @abstractmethod
    def execute(self, command: Command) -> Block:
        ...


class SubprocessExecutor(BaseExecutor):
    def __init__(self, cwd: str | None = None):
        self._cwd = cwd

    def execute(self, command: Command) -> Block:
        command.status = "running"
        try:
            result = subprocess.run(
                command.text,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self._cwd,
            )
            command.status = "done" if result.returncode == 0 else "error"
            return Block(
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )
        except Exception as e:
            command.status = "error"
            return Block(command=command, stderr=str(e), exit_code=1)
