from abc import ABC, abstractmethod
from ..domain.command import Command
from ..domain.block import Block


class BasePTYManager(ABC):
    """Interface para execução via pseudo-terminal — implementação na Fase 4."""

    @abstractmethod
    def execute(self, command: Command) -> Block:
        ...
