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
