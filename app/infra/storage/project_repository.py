import sqlite3
from datetime import datetime
from ...domain.project import Project


class ProjectRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(self, project: Project) -> None:
        self._conn.execute(
            """INSERT INTO projects (id, name, path, type, created_at, last_accessed)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project.id, project.name, project.path, project.type,
             project.created_at.isoformat(), project.last_accessed.isoformat()),
        )
        self._conn.commit()

    def load_all(self) -> list[Project]:
        rows = self._conn.execute(
            "SELECT * FROM projects ORDER BY last_accessed DESC"
        ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def find_by_path(self, path: str) -> Project | None:
        row = self._conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM projects")
        self._conn.commit()

    def delete(self, project_id: str) -> None:
        self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self._conn.commit()

    def rename(self, project_id: str, name: str) -> None:
        self._conn.execute("UPDATE projects SET name = ? WHERE id = ?", (name, project_id))
        self._conn.commit()

    def touch(self, project_id: str) -> None:
        self._conn.execute(
            "UPDATE projects SET last_accessed = ? WHERE id = ?",
            (datetime.now().isoformat(), project_id),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            type=row["type"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed=datetime.fromisoformat(row["last_accessed"]),
        )
