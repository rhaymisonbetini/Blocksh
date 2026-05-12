from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Any
from uuid import uuid4


@dataclass
class TextBlock:
    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class ToolCallBlock:
    type: Literal["tool_call"] = "tool_call"
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultBlock:
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str = ""
    content: str = ""
    is_error: bool = False


ContentBlock = TextBlock | ToolCallBlock | ToolResultBlock


@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: str(uuid4()))
    role: Literal["user", "assistant", "system"] = "user"
    content: list[ContentBlock] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.content if isinstance(b, TextBlock))
