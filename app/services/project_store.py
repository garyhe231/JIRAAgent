import json
import os
import uuid
from datetime import datetime, date
from typing import List, Optional, Dict

from app.models.project import Project, Milestone, Pipeline, PROJECT_COLORS

PROJECTS_DIR = "data/projects"
MILESTONES_DIR = "data/milestones"
PIPELINES_DIR = "data/pipelines"
COUNTER_FILE = "data/counter.json"


def _now() -> str:
    return datetime.utcnow().isoformat()


def _load_counter() -> Dict:
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            return json.load(f)
    return {}


def _save_counter(c: Dict):
    with open(COUNTER_FILE, "w") as f:
        json.dump(c, f)


def _next_project_key(name: str) -> str:
    # derive short key from name, e.g. "Auth Service" -> "AUTH"
    words = name.upper().split()
    if len(words) >= 2:
        key = words[0][:3] + words[1][:3]
    else:
        key = words[0][:6]
    # ensure uniqueness
    existing_keys = {p.key for p in list_projects()}
    base = key
    i = 2
    while key in existing_keys:
        key = f"{base}{i}"
        i += 1
    return key


# ── Project CRUD ─────────────────────────────────────────────────────────────

def create_project(
    name: str,
    description: str = "",
    status: str = "Active",
    color: str = "",
    owner: str = "Admin",
) -> Project:
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    existing = list_projects()
    c = color or PROJECT_COLORS[len(existing) % len(PROJECT_COLORS)]
    now = _now()
    project = Project(
        id=str(uuid.uuid4()),
        key=_next_project_key(name),
        name=name,
        description=description,
        status=status,
        color=c,
        owner=owner,
        created_at=now,
        updated_at=now,
    )
    with open(os.path.join(PROJECTS_DIR, f"{project.id}.json"), "w") as f:
        json.dump(project.to_dict(), f, indent=2)
    return project


def list_projects() -> List[Project]:
    projects = []
    if not os.path.exists(PROJECTS_DIR):
        return projects
    for fname in os.listdir(PROJECTS_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(PROJECTS_DIR, fname)) as f:
            projects.append(Project.from_dict(json.load(f)))
    projects.sort(key=lambda p: p.created_at)
    return projects


def get_project(project_id: str) -> Optional[Project]:
    path = os.path.join(PROJECTS_DIR, f"{project_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return Project.from_dict(json.load(f))


def update_project(project_id: str, **kwargs) -> Optional[Project]:
    p = get_project(project_id)
    if not p:
        return None
    for k, v in kwargs.items():
        if hasattr(p, k):
            setattr(p, k, v)
    p.updated_at = _now()
    with open(os.path.join(PROJECTS_DIR, f"{project_id}.json"), "w") as f:
        json.dump(p.to_dict(), f, indent=2)
    return p


def delete_project(project_id: str) -> bool:
    path = os.path.join(PROJECTS_DIR, f"{project_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# ── Milestone CRUD ────────────────────────────────────────────────────────────

def create_milestone(
    project_id: str,
    name: str,
    description: str = "",
    due_date: Optional[str] = None,
) -> Milestone:
    os.makedirs(MILESTONES_DIR, exist_ok=True)
    now = _now()
    ms = Milestone(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=name,
        description=description,
        status="Open",
        due_date=due_date,
        created_at=now,
        updated_at=now,
    )
    with open(os.path.join(MILESTONES_DIR, f"{ms.id}.json"), "w") as f:
        json.dump(ms.to_dict(), f, indent=2)
    return ms


def list_milestones(project_id: Optional[str] = None) -> List[Milestone]:
    milestones = []
    if not os.path.exists(MILESTONES_DIR):
        return milestones
    for fname in os.listdir(MILESTONES_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(MILESTONES_DIR, fname)) as f:
            milestones.append(Milestone.from_dict(json.load(f)))
    if project_id:
        milestones = [m for m in milestones if m.project_id == project_id]
    # Auto-mark overdue
    today = date.today().isoformat()
    for m in milestones:
        if m.status == "Open" and m.due_date and m.due_date < today:
            m.status = "Overdue"
    milestones.sort(key=lambda m: (m.due_date or "9999", m.created_at))
    return milestones


def get_milestone(milestone_id: str) -> Optional[Milestone]:
    path = os.path.join(MILESTONES_DIR, f"{milestone_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return Milestone.from_dict(json.load(f))


def update_milestone(milestone_id: str, **kwargs) -> Optional[Milestone]:
    ms = get_milestone(milestone_id)
    if not ms:
        return None
    for k, v in kwargs.items():
        if hasattr(ms, k):
            setattr(ms, k, v)
    ms.updated_at = _now()
    with open(os.path.join(MILESTONES_DIR, f"{milestone_id}.json"), "w") as f:
        json.dump(ms.to_dict(), f, indent=2)
    return ms


def delete_milestone(milestone_id: str) -> bool:
    path = os.path.join(MILESTONES_DIR, f"{milestone_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# ── Pipeline CRUD ─────────────────────────────────────────────────────────────

def create_pipeline(
    name: str,
    description: str = "",
    stages: Optional[List[str]] = None,
    created_by: str = "Admin",
) -> Pipeline:
    os.makedirs(PIPELINES_DIR, exist_ok=True)
    now = _now()
    pipeline = Pipeline(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        stages=stages or ["Planned", "In Progress", "Review", "Done"],
        project_stages={},
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    with open(os.path.join(PIPELINES_DIR, f"{pipeline.id}.json"), "w") as f:
        json.dump(pipeline.to_dict(), f, indent=2)
    return pipeline


def list_pipelines() -> List[Pipeline]:
    pipelines = []
    if not os.path.exists(PIPELINES_DIR):
        return pipelines
    for fname in os.listdir(PIPELINES_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(PIPELINES_DIR, fname)) as f:
            pipelines.append(Pipeline.from_dict(json.load(f)))
    pipelines.sort(key=lambda p: p.created_at)
    return pipelines


def get_pipeline(pipeline_id: str) -> Optional[Pipeline]:
    path = os.path.join(PIPELINES_DIR, f"{pipeline_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return Pipeline.from_dict(json.load(f))


def update_pipeline(pipeline_id: str, **kwargs) -> Optional[Pipeline]:
    p = get_pipeline(pipeline_id)
    if not p:
        return None
    for k, v in kwargs.items():
        if hasattr(p, k):
            setattr(p, k, v)
    p.updated_at = _now()
    with open(os.path.join(PIPELINES_DIR, f"{pipeline_id}.json"), "w") as f:
        json.dump(p.to_dict(), f, indent=2)
    return p


def delete_pipeline(pipeline_id: str) -> bool:
    path = os.path.join(PIPELINES_DIR, f"{pipeline_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def set_project_stage(pipeline_id: str, project_id: str, stage: str) -> Optional[Pipeline]:
    p = get_pipeline(pipeline_id)
    if not p:
        return None
    if stage:
        p.project_stages[project_id] = stage
    else:
        p.project_stages.pop(project_id, None)
    p.updated_at = _now()
    with open(os.path.join(PIPELINES_DIR, f"{pipeline_id}.json"), "w") as f:
        json.dump(p.to_dict(), f, indent=2)
    return p


# ── Project stats ─────────────────────────────────────────────────────────────

def project_stats(project_id: str, tickets: list) -> Dict:
    """Compute health metrics for a project given its tickets."""
    total = len(tickets)
    done = sum(1 for t in tickets if t.status == "Done")
    in_progress = sum(1 for t in tickets if t.status == "In Progress")
    blocked = sum(1 for t in tickets if "blocked" in [l.lower() for l in t.labels])
    points_total = sum(t.story_points or 0 for t in tickets)
    points_done = sum(t.story_points or 0 for t in tickets if t.status == "Done")
    by_priority = {}
    for t in tickets:
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
    by_type = {}
    for t in tickets:
        by_type[t.type] = by_type.get(t.type, 0) + 1
    by_status = {}
    for t in tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1

    # Health score 0-100
    health = 100
    if total > 0:
        if blocked > 0:
            health -= min(30, blocked * 10)
        critical = by_priority.get("Critical", 0)
        if critical > 0:
            health -= min(20, critical * 5)
        done_pct = done / total * 100
        if done_pct < 20:
            health -= 10

    milestones = list_milestones(project_id)
    overdue_ms = [m for m in milestones if m.status == "Overdue"]
    if overdue_ms:
        health -= min(20, len(overdue_ms) * 10)

    health = max(0, min(100, health))

    if health >= 75:
        health_label = "Healthy"
        health_color = "#22c55e"
    elif health >= 50:
        health_label = "At Risk"
        health_color = "#f59e0b"
    else:
        health_label = "Critical"
        health_color = "#ef4444"

    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "blocked": blocked,
        "points_total": points_total,
        "points_done": points_done,
        "by_priority": by_priority,
        "by_type": by_type,
        "by_status": by_status,
        "health": health,
        "health_label": health_label,
        "health_color": health_color,
        "milestones_total": len(milestones),
        "milestones_done": sum(1 for m in milestones if m.status == "Completed"),
        "milestones_overdue": len(overdue_ms),
    }
