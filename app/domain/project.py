from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class Project:
    name: str
    path: str
    type: str = "generic"
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
