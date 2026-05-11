from __future__ import annotations

from ..domain.ssh_connection import SshConnection
from ..infra.storage.ssh_repository import SshRepository


class SshService:
    def __init__(self, repository: SshRepository) -> None:
        self._repo = repository

    def add(
        self,
        name: str,
        host: str,
        user: str,
        port: int = 22,
        key_path: str = "",
        group: str = "",
    ) -> SshConnection:
        conn = SshConnection(name=name, host=host, user=user,
                             port=port, key_path=key_path, group=group)
        self._repo.save(conn)
        return conn

    def update(self, conn: SshConnection) -> None:
        self._repo.update(conn)

    def all(self) -> list[SshConnection]:
        return self._repo.load_all()

    def remove(self, conn_id: str) -> None:
        self._repo.delete(conn_id)

    def rename(self, conn_id: str, name: str) -> None:
        self._repo.rename(conn_id, name)

    def touch(self, conn_id: str) -> None:
        self._repo.touch(conn_id)

    def groups(self) -> list[str]:
        return sorted({c.group for c in self.all() if c.group})
