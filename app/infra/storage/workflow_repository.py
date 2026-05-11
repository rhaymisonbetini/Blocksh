from __future__ import annotations

import sqlite3
from datetime import datetime

from ...domain.workflow import Workflow, WorkflowStep


class WorkflowRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, workflow: Workflow) -> None:
        self._conn.execute(
            "INSERT INTO workflows (id, name, description, created_at, last_run) VALUES (?,?,?,?,?)",
            (
                workflow.id,
                workflow.name,
                workflow.description,
                workflow.created_at.isoformat(),
                workflow.last_run.isoformat() if workflow.last_run else None,
            ),
        )
        for step in workflow.steps:
            self._save_step(workflow.id, step)
        self._conn.commit()

    def _save_step(self, workflow_id: str, step: WorkflowStep) -> None:
        self._conn.execute(
            "INSERT INTO workflow_steps (id, workflow_id, command_template, on_error, step_order)"
            " VALUES (?,?,?,?,?)",
            (step.id, workflow_id, step.command_template, step.on_error, step.step_order),
        )

    def update(self, workflow: Workflow) -> None:
        self._conn.execute(
            "UPDATE workflows SET name=?, description=?, last_run=? WHERE id=?",
            (
                workflow.name,
                workflow.description,
                workflow.last_run.isoformat() if workflow.last_run else None,
                workflow.id,
            ),
        )
        self._conn.execute("DELETE FROM workflow_steps WHERE workflow_id=?", (workflow.id,))
        for step in workflow.steps:
            self._save_step(workflow.id, step)
        self._conn.commit()

    def delete(self, workflow_id: str) -> None:
        self._conn.execute("DELETE FROM workflows WHERE id=?", (workflow_id,))
        self._conn.commit()

    def touch(self, workflow_id: str) -> None:
        self._conn.execute(
            "UPDATE workflows SET last_run=? WHERE id=?",
            (datetime.now().isoformat(), workflow_id),
        )
        self._conn.commit()

    def load_all(self) -> list[Workflow]:
        rows = self._conn.execute(
            "SELECT * FROM workflows ORDER BY name COLLATE NOCASE"
        ).fetchall()
        workflows = []
        for row in rows:
            steps = self._load_steps(row["id"])
            workflows.append(self._row_to_workflow(row, steps))
        return workflows

    def _load_steps(self, workflow_id: str) -> list[WorkflowStep]:
        rows = self._conn.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id=? ORDER BY step_order",
            (workflow_id,),
        ).fetchall()
        return [
            WorkflowStep(
                id=r["id"],
                command_template=r["command_template"],
                on_error=r["on_error"],
                step_order=r["step_order"],
            )
            for r in rows
        ]

    def _row_to_workflow(self, row, steps: list[WorkflowStep]) -> Workflow:
        return Workflow(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            steps=steps,
            created_at=datetime.fromisoformat(row["created_at"]),
            last_run=datetime.fromisoformat(row["last_run"]) if row["last_run"] else None,
        )
