from abc import ABC, abstractmethod
import subprocess
from ..domain.command import Command
from ..domain.block import Block


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
                command.text,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=env,
            )
            command.status = "done" if result.returncode == 0 else "error"
            return Block(
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                cwd=cwd or "",
            )
        except Exception as e:
            command.status = "error"
            return Block(command=command, stderr=str(e), exit_code=1, cwd=cwd or "")
