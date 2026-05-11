from __future__ import annotations

from ..domain.workflow import Workflow, WorkflowStep
from ..infra.storage.workflow_repository import WorkflowRepository


class WorkflowService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repo = repository

    def add(self, name: str, description: str = "", steps: list[WorkflowStep] | None = None) -> Workflow:
        wf = Workflow(name=name, description=description, steps=steps or [])
        self._repo.save(wf)
        return wf

    def update(self, workflow: Workflow) -> None:
        self._repo.update(workflow)

    def all(self) -> list[Workflow]:
        return self._repo.load_all()

    def remove(self, workflow_id: str) -> None:
        self._repo.delete(workflow_id)

    def touch(self, workflow_id: str) -> None:
        self._repo.touch(workflow_id)
