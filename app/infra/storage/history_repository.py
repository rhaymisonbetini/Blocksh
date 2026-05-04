import sqlite3
from datetime import datetime
from ...domain.command import Command
from ...domain.block import Block


class HistoryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save_block(self, block: Block, session_id: str) -> None:
        self._conn.execute(
            """
            INSERT INTO blocks
                (id, session_id, command_text, command_status,
                 created_at, stdout, stderr, exit_code, cwd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                block.command.id,
                session_id,
                block.command.text,
                block.command.status,
                block.command.created_at.isoformat(),
                block.stdout,
                block.stderr,
                block.exit_code,
                block.cwd,
            ),
        )
        self._conn.commit()

    def load_recent(self, limit: int = 200) -> list[Block]:
        """Returns the most recent blocks across all sessions, oldest first."""
        rows = self._conn.execute(
            "SELECT * FROM blocks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_block(r) for r in reversed(rows)]

    def load_by_cwd_prefix(self, cwd_prefix: str, limit: int = 10) -> list[Block]:
        """Returns most recent blocks whose cwd starts with cwd_prefix, oldest first."""
        rows = self._conn.execute(
            "SELECT * FROM blocks WHERE cwd LIKE ? ORDER BY created_at DESC LIMIT ?",
            (cwd_prefix.rstrip("/") + "%", limit),
        ).fetchall()
        return [self._row_to_block(r) for r in reversed(rows)]

    def load_session(self, session_id: str) -> list[Block]:
        rows = self._conn.execute(
            "SELECT * FROM blocks WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_block(r) for r in rows]

    @staticmethod
    def _row_to_block(row: sqlite3.Row) -> Block:
        command = Command(
            id=row["id"],
            text=row["command_text"],
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row["command_status"],
        )
        return Block(
            command=command,
            stdout=row["stdout"],
            stderr=row["stderr"],
            exit_code=row["exit_code"],
            cwd=row["cwd"],
        )
