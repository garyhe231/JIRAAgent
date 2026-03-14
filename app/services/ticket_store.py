import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict

from app.models.ticket import Ticket, Sprint, Comment, STATUSES

TICKETS_DIR = "data/tickets"
SPRINTS_DIR = "data/sprints"
COMMENTS_DIR = "data/comments"
COUNTER_FILE = "data/counter.json"


def _now() -> str:
    return datetime.utcnow().isoformat()


def _load_counter() -> Dict:
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            return json.load(f)
    return {"ticket": 0, "sprint": 0}


def _save_counter(c: Dict):
    with open(COUNTER_FILE, "w") as f:
        json.dump(c, f)


def _next_ticket_key() -> str:
    c = _load_counter()
    c["ticket"] += 1
    _save_counter(c)
    return f"JIRA-{c['ticket']}"


def _next_sprint_num() -> int:
    c = _load_counter()
    c["sprint"] += 1
    _save_counter(c)
    return c["sprint"]


# ── Ticket CRUD ─────────────────────────────────────────────────────────────

def create_ticket(
    title: str,
    description: str = "",
    type: str = "Task",
    priority: str = "Medium",
    assignee: str = "Unassigned",
    reporter: str = "You",
    labels: Optional[List[str]] = None,
    sprint_id: Optional[str] = None,
    story_points: Optional[int] = None,
    parent_id: Optional[str] = None,
) -> Ticket:
    now = _now()
    ticket = Ticket(
        id=str(uuid.uuid4()),
        key=_next_ticket_key(),
        title=title,
        description=description,
        type=type,
        status="Backlog",
        priority=priority,
        assignee=assignee,
        reporter=reporter,
        labels=labels or [],
        sprint_id=sprint_id,
        story_points=story_points,
        created_at=now,
        updated_at=now,
        comments=[],
        parent_id=parent_id,
    )
    _save_ticket(ticket)
    return ticket


def _save_ticket(ticket: Ticket):
    os.makedirs(TICKETS_DIR, exist_ok=True)
    with open(os.path.join(TICKETS_DIR, f"{ticket.id}.json"), "w") as f:
        json.dump(ticket.to_dict(), f, indent=2)


def get_ticket(ticket_id: str) -> Optional[Ticket]:
    path = os.path.join(TICKETS_DIR, f"{ticket_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return Ticket.from_dict(json.load(f))


def get_ticket_by_key(key: str) -> Optional[Ticket]:
    for t in list_tickets():
        if t.key == key:
            return t
    return None


def list_tickets(
    status: Optional[str] = None,
    sprint_id: Optional[str] = None,
    assignee: Optional[str] = None,
    type: Optional[str] = None,
    label: Optional[str] = None,
    backlog_only: bool = False,
) -> List[Ticket]:
    tickets = []
    if not os.path.exists(TICKETS_DIR):
        return tickets
    for fname in os.listdir(TICKETS_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(TICKETS_DIR, fname)) as f:
            tickets.append(Ticket.from_dict(json.load(f)))

    if status:
        tickets = [t for t in tickets if t.status == status]
    if sprint_id:
        tickets = [t for t in tickets if t.sprint_id == sprint_id]
    if assignee:
        tickets = [t for t in tickets if t.assignee == assignee]
    if type:
        tickets = [t for t in tickets if t.type == type]
    if label:
        tickets = [t for t in tickets if label in t.labels]
    if backlog_only:
        tickets = [t for t in tickets if t.sprint_id is None and t.status != "Done"]

    tickets.sort(key=lambda t: t.created_at, reverse=True)
    return tickets


def update_ticket(ticket_id: str, **kwargs) -> Optional[Ticket]:
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None
    for k, v in kwargs.items():
        if hasattr(ticket, k):
            setattr(ticket, k, v)
    ticket.updated_at = _now()
    _save_ticket(ticket)
    return ticket


def delete_ticket(ticket_id: str) -> bool:
    path = os.path.join(TICKETS_DIR, f"{ticket_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def add_comment(ticket_id: str, author: str, body: str) -> Optional[Comment]:
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None
    comment = Comment(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        author=author,
        body=body,
        created_at=_now(),
    )
    ticket.comments.append(comment.to_dict())
    ticket.updated_at = _now()
    _save_ticket(ticket)
    return comment


# ── Sprint CRUD ──────────────────────────────────────────────────────────────

def create_sprint(
    name: Optional[str] = None,
    goal: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Sprint:
    num = _next_sprint_num()
    sprint = Sprint(
        id=str(uuid.uuid4()),
        name=name or f"Sprint {num}",
        goal=goal,
        status="Planning",
        start_date=start_date,
        end_date=end_date,
        created_at=_now(),
    )
    os.makedirs(SPRINTS_DIR, exist_ok=True)
    with open(os.path.join(SPRINTS_DIR, f"{sprint.id}.json"), "w") as f:
        json.dump(sprint.to_dict(), f, indent=2)
    return sprint


def list_sprints() -> List[Sprint]:
    sprints = []
    if not os.path.exists(SPRINTS_DIR):
        return sprints
    for fname in os.listdir(SPRINTS_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(SPRINTS_DIR, fname)) as f:
            sprints.append(Sprint.from_dict(json.load(f)))
    sprints.sort(key=lambda s: s.created_at, reverse=True)
    return sprints


def get_sprint(sprint_id: str) -> Optional[Sprint]:
    path = os.path.join(SPRINTS_DIR, f"{sprint_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return Sprint.from_dict(json.load(f))


def get_active_sprint() -> Optional[Sprint]:
    for s in list_sprints():
        if s.status == "Active":
            return s
    return None


def update_sprint(sprint_id: str, **kwargs) -> Optional[Sprint]:
    sprint = get_sprint(sprint_id)
    if not sprint:
        return None
    for k, v in kwargs.items():
        if hasattr(sprint, k):
            setattr(sprint, k, v)
    with open(os.path.join(SPRINTS_DIR, f"{sprint_id}.json"), "w") as f:
        json.dump(sprint.to_dict(), f, indent=2)
    return sprint


def board_data(sprint_id: Optional[str] = None) -> Dict:
    """Return kanban lanes for a sprint (or backlog if no sprint)."""
    if sprint_id:
        tickets = list_tickets(sprint_id=sprint_id)
    else:
        active = get_active_sprint()
        if active:
            tickets = list_tickets(sprint_id=active.id)
            sprint_id = active.id
        else:
            tickets = list_tickets()

    lanes = {s: [] for s in ["To Do", "In Progress", "In Review", "Done"]}
    for t in tickets:
        if t.status in lanes:
            lanes[t.status].append(t.to_dict())
    return {"sprint_id": sprint_id, "lanes": lanes}
