import os
from pathlib import Path
from ..domain.project import Project
from ..domain.block import Block
from ..infra.storage.project_repository import ProjectRepository
from ..infra.storage.history_repository import HistoryRepository

_MARKERS: dict[str, str] = {
    ".git":           "git",
    "package.json":   "node",
    "composer.json":  "php",
    "pyproject.toml": "python",
    "Cargo.toml":     "rust",
    "go.mod":         "go",
}


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self._repo = repository

    def detect_type(self, path: str) -> str:
        for marker, kind in _MARKERS.items():
            if os.path.exists(os.path.join(path, marker)):
                return kind
        return "generic"

    def register(self, path: str, name: str | None = None) -> Project | None:
        if self._repo.find_by_path(path):
            return None
        project_name = name or Path(path).name or path
        project = Project(
            name=project_name,
            path=path,
            type=self.detect_type(path),
        )
        self._repo.save(project)
        return project

    def auto_register(self, path: str) -> Project | None:
        """Register path if it has known markers and isn't already registered."""
        if not path or self._repo.find_by_path(path):
            return None
        if self.detect_type(path) != "generic":
            return self.register(path)
        return None

    def touch(self, path: str) -> None:
        project = self._repo.find_by_path(path)
        if project:
            self._repo.touch(project.id)

    def all(self) -> list[Project]:
        return self._repo.load_all()

    def remove(self, project_id: str) -> None:
        self._repo.delete(project_id)

    def rename(self, project_id: str, name: str) -> None:
        self._repo.rename(project_id, name)

    def history_for(
        self, project: Project, history_repository: HistoryRepository, limit: int = 8
    ) -> list[Block]:
        return history_repository.load_by_cwd_prefix(project.path, limit)
