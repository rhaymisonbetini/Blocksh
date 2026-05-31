import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator

from ...infra.config.settings import DB_PATH


class ThreadSafeConnection:
    """
    Thread-safe wrapper around a single sqlite3.Connection.

    Uses a reentrant lock so that nested calls within the same thread
    (e.g. executescript → commit) do not deadlock.  WAL journal mode
    is enabled at construction time for better read/write concurrency.

    The public interface mirrors the subset of sqlite3.Connection that
    the repository layer actually uses, so existing callers need no changes.
    """

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        # WAL gives concurrent readers while a writer holds the lock,
        # and avoids "database is locked" errors under parallel tab usage.
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.commit()

    # ── context manager for multi-step atomic operations ──────────────────────

    @contextmanager
    def atomic(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield the raw connection inside the reentrant lock.

        Use this whenever execute + commit must be kept atomic:

            with conn.atomic() as c:
                c.execute("INSERT ...", (...))
                c.commit()
        """
        with self._lock:
            yield self._conn

    # ── drop-in replacements for the sqlite3.Connection API ──────────────────

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value) -> None:
        with self._lock:
            self._conn.row_factory = value

    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executescript(self, sql: str) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executescript(sql)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def get_connection() -> ThreadSafeConnection:
    return ThreadSafeConnection(str(DB_PATH))


def initialize_schema(conn: ThreadSafeConnection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id   TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS blocks (
            id             TEXT PRIMARY KEY,
            session_id     TEXT NOT NULL,
            command_text   TEXT NOT NULL,
            command_status TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            stdout         TEXT NOT NULL DEFAULT '',
            stderr         TEXT NOT NULL DEFAULT '',
            exit_code      INTEGER NOT NULL DEFAULT 0,
            cwd            TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS favorites (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            command_text TEXT NOT NULL,
            cwd          TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            path          TEXT NOT NULL UNIQUE,
            type          TEXT NOT NULL DEFAULT 'generic',
            created_at    TEXT NOT NULL,
            last_accessed TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ssh_connections (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            host       TEXT NOT NULL,
            user       TEXT NOT NULL,
            port       INTEGER NOT NULL DEFAULT 22,
            key_path   TEXT NOT NULL DEFAULT '',
            group_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            last_used  TEXT
        );

        CREATE TABLE IF NOT EXISTS workflows (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            last_run    TEXT
        );

        CREATE TABLE IF NOT EXISTS workflow_steps (
            id               TEXT PRIMARY KEY,
            workflow_id      TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
            command_template TEXT NOT NULL,
            on_error         TEXT NOT NULL DEFAULT 'stop',
            step_order       INTEGER NOT NULL
        );
    """)
    conn.commit()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id         TEXT PRIMARY KEY,
            tab_id     TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_messages (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
            role        TEXT NOT NULL,
            content_json TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
    """)
    conn.commit()

    # Migrations — run safely on existing databases
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN env_decision TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists
