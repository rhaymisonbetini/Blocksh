from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class SshConnection:
    name:       str
    host:       str
    user:       str
    port:       int      = 22
    key_path:   str      = ""
    group:      str      = ""
    id:         str      = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    last_used:  datetime | None = None

    def to_command(self) -> str:
        parts = ["ssh"]
        if self.port != 22:
            parts += ["-p", str(self.port)]
        if self.key_path:
            import os
            parts += ["-i", os.path.expanduser(self.key_path)]
        parts.append(f"{self.user}@{self.host}")
        return " ".join(parts)
