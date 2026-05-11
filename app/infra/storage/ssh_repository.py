from __future__ import annotations

import sqlite3
from datetime import datetime

from ...domain.ssh_connection import SshConnection


class SshRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, conn: SshConnection) -> None:
        self._conn.execute(
            """INSERT INTO ssh_connections
               (id, name, host, user, port, key_path, group_name, created_at, last_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                conn.id, conn.name, conn.host, conn.user, conn.port,
                conn.key_path, conn.group,
                conn.created_at.isoformat(),
                conn.last_used.isoformat() if conn.last_used else None,
            ),
        )
        self._conn.commit()

    def load_all(self) -> list[SshConnection]:
        rows = self._conn.execute(
            """SELECT * FROM ssh_connections
               ORDER BY CASE WHEN last_used IS NULL THEN 1 ELSE 0 END,
                        last_used DESC, name ASC"""
        ).fetchall()
        return [self._row_to_connection(r) for r in rows]

    def delete(self, conn_id: str) -> None:
        self._conn.execute("DELETE FROM ssh_connections WHERE id = ?", (conn_id,))
        self._conn.commit()

    def rename(self, conn_id: str, name: str) -> None:
        self._conn.execute(
            "UPDATE ssh_connections SET name = ? WHERE id = ?", (name, conn_id)
        )
        self._conn.commit()

    def touch(self, conn_id: str) -> None:
        self._conn.execute(
            "UPDATE ssh_connections SET last_used = ? WHERE id = ?",
            (datetime.now().isoformat(), conn_id),
        )
        self._conn.commit()

    def update(self, conn: SshConnection) -> None:
        self._conn.execute(
            """UPDATE ssh_connections
               SET name=?, host=?, user=?, port=?, key_path=?, group_name=?
               WHERE id=?""",
            (conn.name, conn.host, conn.user, conn.port,
             conn.key_path, conn.group, conn.id),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_connection(row: sqlite3.Row) -> SshConnection:
        return SshConnection(
            id=row["id"],
            name=row["name"],
            host=row["host"],
            user=row["user"],
            port=row["port"],
            key_path=row["key_path"],
            group=row["group_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
        )
