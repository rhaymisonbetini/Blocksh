from ..domain.block import Block


class HistoryService:
    """In-memory session history. Persistence (SQLite) comes in Phase 3."""

    def __init__(self):
        self._blocks: list[Block] = []

    def add(self, block: Block) -> None:
        self._blocks.append(block)

    def commands(self) -> list[str]:
        """Returns ordered list of command texts for keyboard navigation."""
        return [b.command.text for b in self._blocks]

    def blocks(self) -> list[Block]:
        return list(self._blocks)
