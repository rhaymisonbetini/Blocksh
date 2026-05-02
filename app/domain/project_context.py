from dataclasses import dataclass, field


@dataclass
class ProjectContext:
    path: str
    env_vars: dict = field(default_factory=dict)
    history_id: str = ""
