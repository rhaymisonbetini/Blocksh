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
        import shlex, os
        parts = [
            "ssh",
            # Fail fast if server is unreachable (firewall / wrong IP) instead of
            # hanging silently for minutes waiting for a TCP timeout.
            "-o", "ConnectTimeout=30",
            # Detect dead connections after ~45 s of silence once connected.
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
        ]
        if self.port != 22:
            parts += ["-p", str(self.port)]
        if self.key_path:
            expanded = os.path.expanduser(self.key_path)
            # shlex.quote handles paths with spaces; shlex.split() in PtyProcess
            # will then parse the quoted token back into the bare path correctly.
            parts += ["-i", shlex.quote(expanded)]
        parts.append(f"{self.user}@{self.host}")
        return " ".join(parts)
