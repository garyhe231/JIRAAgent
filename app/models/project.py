from dataclasses import dataclass, asdict
from typing import Optional, List

PROJECT_STATUSES = ["Active", "On Hold", "Completed", "Cancelled"]
MILESTONE_STATUSES = ["Open", "Completed", "Overdue"]
PROJECT_COLORS = [
    "#4f7ef8", "#22c55e", "#f59e0b", "#ef4444",
    "#a855f7", "#06b6d4", "#f97316", "#ec4899",
]


@dataclass
class Project:
    id: str
    key: str           # e.g. PROJ-AUTH
    name: str
    description: str
    status: str        # Active | On Hold | Completed | Cancelled
    color: str         # hex
    owner: str         # display_name of owner
    created_at: str
    updated_at: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(**d)


@dataclass
class Milestone:
    id: str
    project_id: str
    name: str
    description: str
    status: str        # Open | Completed | Overdue
    due_date: Optional[str]
    created_at: str
    updated_at: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Milestone":
        return cls(**d)
