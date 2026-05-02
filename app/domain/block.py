from dataclasses import dataclass, field
from .command import Command


@dataclass
class Block:
    command: Command
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    cwd: str = ""  # working directory at execution time
