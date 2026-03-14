from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime
import uuid


STATUSES = ["Backlog", "To Do", "In Progress", "In Review", "Done"]
PRIORITIES = ["Critical", "High", "Medium", "Low"]
TYPES = ["Bug", "Feature", "Task", "Story", "Epic", "Improvement"]


@dataclass
class Comment:
    id: str
    ticket_id: str
    author: str
    body: str
    created_at: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Comment":
        return cls(**d)


@dataclass
class Ticket:
    id: str
    key: str
    title: str
    description: str
    type: str
    status: str
    priority: str
    assignee: str
    reporter: str
    labels: List[str]
    sprint_id: Optional[str]
    story_points: Optional[int]
    created_at: str
    updated_at: str
    comments: List[dict] = field(default_factory=list)
    parent_id: Optional[str] = None
    project_id: Optional[str] = None
    milestone_id: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Ticket":
        return cls(**d)


@dataclass
class Sprint:
    id: str
    name: str
    goal: str
    status: str  # Planning, Active, Completed
    start_date: Optional[str]
    end_date: Optional[str]
    created_at: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Sprint":
        return cls(**d)
