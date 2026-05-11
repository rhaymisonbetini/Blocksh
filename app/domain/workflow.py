from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class WorkflowStep:
    command_template: str
    on_error: str = "stop"       # "stop" | "continue"
    step_order: int = 0
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class Workflow:
    name: str
    description: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    last_run: datetime | None = None
