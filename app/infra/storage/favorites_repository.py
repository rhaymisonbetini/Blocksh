import sqlite3
from datetime import datetime
from ...domain.favorite import Favorite


class FavoritesRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(self, favorite: Favorite) -> None:
        self._conn.execute(
            "INSERT INTO favorites (id, name, command_text, cwd, created_at) VALUES (?, ?, ?, ?, ?)",
            (favorite.id, favorite.name, favorite.command_text, favorite.cwd,
             favorite.created_at.isoformat()),
        )
        self._conn.commit()

    def load_all(self) -> list[Favorite]:
        rows = self._conn.execute(
            "SELECT * FROM favorites ORDER BY created_at"
        ).fetchall()
        return [self._row_to_favorite(r) for r in rows]

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM favorites")
        self._conn.commit()

    def delete(self, fav_id: str) -> None:
        self._conn.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
        self._conn.commit()

    def rename(self, fav_id: str, name: str) -> None:
        self._conn.execute("UPDATE favorites SET name = ? WHERE id = ?", (name, fav_id))
        self._conn.commit()

    def update(self, fav_id: str, name: str, command_text: str, cwd: str) -> None:
        self._conn.execute(
            "UPDATE favorites SET name=?, command_text=?, cwd=? WHERE id=?",
            (name, command_text, cwd, fav_id),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_favorite(row: sqlite3.Row) -> Favorite:
        return Favorite(
            id=row["id"],
            name=row["name"],
            command_text=row["command_text"],
            cwd=row["cwd"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
