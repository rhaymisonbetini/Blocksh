from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from ...domain.agent_message import AgentMessage, TextBlock, ToolCallBlock, ToolResultBlock


class AgentHistoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_session(self, session_id: str, tab_id: str, messages: list[AgentMessage]) -> None:
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO agent_sessions (id, tab_id, created_at) VALUES (?, ?, ?)",
            (session_id, tab_id, now),
        )
        self._conn.execute("DELETE FROM agent_messages WHERE session_id = ?", (session_id,))
        for msg in messages:
            self._conn.execute(
                "INSERT INTO agent_messages (id, session_id, role, content_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (msg.id, session_id, msg.role, _content_to_json(msg), now),
            )
        self._conn.commit()

    def load_session(self, session_id: str) -> list[AgentMessage]:
        rows = self._conn.execute(
            "SELECT id, role, content_json FROM agent_messages WHERE session_id = ? ORDER BY rowid",
            (session_id,),
        ).fetchall()
        return [_row_to_message(r) for r in rows]

    def delete_session(self, session_id: str) -> None:
        self._conn.execute("DELETE FROM agent_sessions WHERE id = ?", (session_id,))
        self._conn.commit()


def _content_to_json(msg: AgentMessage) -> str:
    blocks = []
    for b in msg.content:
        if isinstance(b, TextBlock):
            blocks.append({"type": "text", "text": b.text})
        elif isinstance(b, ToolCallBlock):
            blocks.append({"type": "tool_call", "id": b.id, "name": b.name, "args": b.args})
        elif isinstance(b, ToolResultBlock):
            blocks.append({"type": "tool_result", "tool_call_id": b.tool_call_id,
                           "content": b.content, "is_error": b.is_error})
    return json.dumps(blocks)


def _row_to_message(row: sqlite3.Row) -> AgentMessage:
    blocks_raw = json.loads(row["content_json"])
    content = []
    for b in blocks_raw:
        t = b.get("type")
        if t == "text":
            content.append(TextBlock(text=b.get("text", "")))
        elif t == "tool_call":
            content.append(ToolCallBlock(id=b["id"], name=b["name"], args=b.get("args", {})))
        elif t == "tool_result":
            content.append(ToolResultBlock(
                tool_call_id=b.get("tool_call_id", ""),
                content=b.get("content", ""),
                is_error=b.get("is_error", False),
            ))
    return AgentMessage(id=row["id"], role=row["role"], content=content)
