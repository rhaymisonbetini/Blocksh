import threading
from uuid import uuid4
from ..domain.block import Block
from ..infra.storage.history_repository import HistoryRepository


class HistoryService:
    """
    Manages session history with SQLite persistence.
    Keeps an in-memory cache of the current session for fast access.

    Thread-safe: add() uses an RLock so concurrent Qt signal deliveries
    from multiple CommandThread instances cannot corrupt the in-memory cache
    or produce duplicate DB writes.
    """

    def __init__(self, repository: HistoryRepository):
        self._repo = repository
        self._session_id = str(uuid4())
        self._blocks: list[Block] = []
        self._lock = threading.RLock()

    @property
    def session_id(self) -> str:
        return self._session_id

    def add(self, block: Block) -> None:
        with self._lock:
            last_text = self._blocks[-1].command.text.strip() if self._blocks else None
            if last_text == block.command.text.strip():
                return   # skip consecutive duplicates
            self._blocks.append(block)
            self._repo.save_block(block, self._session_id)

    def commands(self) -> list[str]:
        """Returns command texts for keyboard navigation (current session only)."""
        with self._lock:
            return [b.command.text for b in self._blocks]

    def blocks(self) -> list[Block]:
        with self._lock:
            return list(self._blocks)
