import sqlite3
from ...infra.config.settings import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # allows column access by name
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
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
    """)
    conn.commit()
