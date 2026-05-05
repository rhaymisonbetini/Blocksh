from uuid import uuid4
from ..domain.block import Block
from ..infra.storage.history_repository import HistoryRepository


class HistoryService:
    """
    Manages session history with SQLite persistence.
    Keeps an in-memory cache of the current session for fast access.
    """

    def __init__(self, repository: HistoryRepository):
        self._repo = repository
        self._session_id = str(uuid4())
        self._blocks: list[Block] = []

    @property
    def session_id(self) -> str:
        return self._session_id

    def add(self, block: Block) -> None:
        if self._blocks and self._blocks[-1].command.text.strip() == block.command.text.strip():
            return   # #37: skip consecutive duplicate commands
        self._blocks.append(block)
        self._repo.save_block(block, self._session_id)

    def commands(self) -> list[str]:
        """Returns command texts for keyboard navigation (current session only)."""
        return [b.command.text for b in self._blocks]

    def blocks(self) -> list[Block]:
        return list(self._blocks)
