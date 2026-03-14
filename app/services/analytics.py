"""
Analytics engine — computes all metrics for the reporting dashboard.
All computation is done in-process over JSON files (no DB needed).
"""
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Any
from collections import defaultdict

from app.services.ticket_store import list_tickets, list_sprints
from app.services.project_store import list_projects
from app.services.user_store import list_users
from app.models.ticket import STATUSES, PRIORITIES, TYPES


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.utcnow()


def _date_range(days: Optional[int]) -> Optional[datetime]:
    if days is None:
        return None
    return datetime.utcnow() - timedelta(days=days)


# ── Overview metrics ──────────────────────────────────────────────────────────

def overview(days: Optional[int] = None) -> Dict:
    since = _date_range(days)
    all_tickets = list_tickets()
    filtered = [t for t in all_tickets if since is None or _parse_dt(t.created_at) >= since]

    total = len(filtered)
    done = sum(1 for t in filtered if t.status == "Done")
    in_progress = sum(1 for t in filtered if t.status == "In Progress")
    backlog = sum(1 for t in filtered if t.status == "Backlog")
    blocked = sum(1 for t in filtered if "blocked" in [l.lower() for l in t.labels])
    bugs = sum(1 for t in filtered if t.type == "Bug")
    critical = sum(1 for t in filtered if t.priority == "Critical")
    completion_rate = round(done / total * 100) if total else 0

    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "backlog": backlog,
        "blocked": blocked,
        "bugs": bugs,
        "critical": critical,
        "completion_rate": completion_rate,
    }


# ── Tickets by status (donut) ─────────────────────────────────────────────────

def by_status(days: Optional[int] = None) -> Dict:
    since = _date_range(days)
    tickets = list_tickets()
    if since:
        tickets = [t for t in tickets if _parse_dt(t.created_at) >= since]
    counts = defaultdict(int)
    for t in tickets:
        counts[t.status] += 1
    colors = {
        "Backlog": "#94a3b8", "To Do": "#64748b",
        "In Progress": "#4f7ef8", "In Review": "#a855f7", "Done": "#22c55e",
    }
    labels = list(counts.keys())
    return {
        "labels": labels,
        "data": [counts[l] for l in labels],
        "colors": [colors.get(l, "#8896af") for l in labels],
    }


# ── Tickets by priority (donut) ───────────────────────────────────────────────

def by_priority(days: Optional[int] = None) -> Dict:
    since = _date_range(days)
    tickets = list_tickets()
    if since:
        tickets = [t for t in tickets if _parse_dt(t.created_at) >= since]
    counts = defaultdict(int)
    for t in tickets:
        counts[t.priority] += 1
    colors = {"Critical": "#ef4444", "High": "#f97316", "Medium": "#f59e0b", "Low": "#94a3b8"}
    labels = [p for p in PRIORITIES if p in counts]
    return {
        "labels": labels,
        "data": [counts[l] for l in labels],
        "colors": [colors.get(l, "#8896af") for l in labels],
    }


# ── Tickets by type (bar) ─────────────────────────────────────────────────────

def by_type(days: Optional[int] = None) -> Dict:
    since = _date_range(days)
    tickets = list_tickets()
    if since:
        tickets = [t for t in tickets if _parse_dt(t.created_at) >= since]
    counts = defaultdict(int)
    for t in tickets:
        counts[t.type] += 1
    colors = {
        "Bug": "#ef4444", "Feature": "#22c55e", "Task": "#4f7ef8",
        "Story": "#a855f7", "Epic": "#f97316", "Improvement": "#06b6d4",
    }
    labels = [tp for tp in TYPES if tp in counts]
    return {
        "labels": labels,
        "data": [counts[l] for l in labels],
        "colors": [colors.get(l, "#8896af") for l in labels],
    }


# ── Created vs Resolved trend (line chart) ────────────────────────────────────

def created_vs_resolved(days: int = 30) -> Dict:
    since = datetime.utcnow() - timedelta(days=days)
    tickets = list_tickets()

    # Build daily buckets
    buckets: Dict[str, Dict] = {}
    for i in range(days):
        d = (since + timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[d] = {"created": 0, "resolved": 0}

    for t in tickets:
        cd = _parse_dt(t.created_at).strftime("%Y-%m-%d")
        if cd in buckets:
            buckets[cd]["created"] += 1
        if t.status == "Done":
            ud = _parse_dt(t.updated_at).strftime("%Y-%m-%d")
            if ud in buckets:
                buckets[ud]["resolved"] += 1

    labels = sorted(buckets.keys())
    # Use shorter labels for display
    display = [d[5:] for d in labels]  # MM-DD
    return {
        "labels": display,
        "created": [buckets[d]["created"] for d in labels],
        "resolved": [buckets[d]["resolved"] for d in labels],
    }


# ── Sprint velocity (story points done per sprint, bar) ───────────────────────

def sprint_velocity() -> Dict:
    sprints = [s for s in list_sprints() if s.status in ("Active", "Completed")]
    sprints.sort(key=lambda s: s.created_at)
    labels, committed, completed_pts, completed_cnt = [], [], [], []

    for s in sprints[-8:]:  # last 8 sprints
        t_all = list_tickets(sprint_id=s.id)
        t_done = [t for t in t_all if t.status == "Done"]
        pts_all = sum(t.story_points or 0 for t in t_all)
        pts_done = sum(t.story_points or 0 for t in t_done)
        labels.append(s.name[:20])
        committed.append(pts_all)
        completed_pts.append(pts_done)
        completed_cnt.append(len(t_done))

    return {
        "labels": labels,
        "committed": committed,
        "completed_pts": completed_pts,
        "completed_cnt": completed_cnt,
    }


# ── Workload by assignee (horizontal bar) ────────────────────────────────────

def workload_by_assignee(days: Optional[int] = None) -> Dict:
    since = _date_range(days)
    tickets = list_tickets()
    if since:
        tickets = [t for t in tickets if _parse_dt(t.created_at) >= since]

    users = {u.display_name: u.avatar_color for u in list_users()}
    data: Dict[str, Dict] = defaultdict(lambda: defaultdict(int))

    for t in tickets:
        a = t.assignee
        data[a][t.status] += 1

    # Sort by total descending, exclude "Unassigned" last
    sorted_assignees = sorted(
        data.keys(),
        key=lambda a: sum(data[a].values()),
        reverse=True,
    )

    result = []
    for a in sorted_assignees[:12]:
        total = sum(data[a].values())
        result.append({
            "name": a,
            "total": total,
            "done": data[a].get("Done", 0),
            "in_progress": data[a].get("In Progress", 0),
            "in_review": data[a].get("In Review", 0),
            "todo": data[a].get("To Do", 0),
            "backlog": data[a].get("Backlog", 0),
            "color": users.get(a, "#8896af"),
        })

    return {"assignees": result}


# ── Ticket aging (open tickets, days since created) ───────────────────────────

def ticket_aging() -> List[Dict]:
    tickets = [t for t in list_tickets() if t.status not in ("Done",)]
    now = datetime.utcnow()
    aged = []
    for t in tickets:
        age_days = (now - _parse_dt(t.created_at)).days
        aged.append({
            "key": t.key,
            "title": t.title[:60],
            "status": t.status,
            "priority": t.priority,
            "assignee": t.assignee,
            "age_days": age_days,
        })
    aged.sort(key=lambda x: x["age_days"], reverse=True)
    return aged[:20]


# ── Sprint burndown ───────────────────────────────────────────────────────────

def sprint_burndown(sprint_id: str) -> Dict:
    from app.services.ticket_store import get_sprint
    sprint = get_sprint(sprint_id)
    if not sprint or not sprint.start_date or not sprint.end_date:
        return {"labels": [], "ideal": [], "actual": []}

    tickets = list_tickets(sprint_id=sprint_id)
    total_points = sum(t.story_points or 1 for t in tickets)  # fallback 1pt if unset

    start = datetime.fromisoformat(sprint.start_date)
    end = datetime.fromisoformat(sprint.end_date)
    today = datetime.utcnow()
    end_plot = min(end, today)

    num_days = max((end - start).days, 1)
    labels, ideal, actual = [], [], []

    for i in range(num_days + 1):
        d = start + timedelta(days=i)
        if d > end_plot:
            break
        label = d.strftime("%m-%d")
        labels.append(label)

        # Ideal: linear burndown
        ideal.append(round(total_points * (1 - i / num_days), 1))

        # Actual: points remaining = total - points of tickets updated as Done by this date
        done_by = sum(
            t.story_points or 1 for t in tickets
            if t.status == "Done" and _parse_dt(t.updated_at) <= d
        )
        actual.append(max(total_points - done_by, 0))

    return {
        "labels": labels,
        "ideal": ideal,
        "actual": actual,
        "total_points": total_points,
        "sprint_name": sprint.name,
    }


# ── Bug rate trend (bugs created per week) ───────────────────────────────────

def bug_rate(weeks: int = 8) -> Dict:
    tickets = list_tickets()
    now = datetime.utcnow()
    labels, bugs_count, features_count = [], [], []

    for i in range(weeks - 1, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        label = week_start.strftime("%m/%d")
        labels.append(label)
        week_tickets = [
            t for t in tickets
            if week_start <= _parse_dt(t.created_at) < week_end
        ]
        bugs_count.append(sum(1 for t in week_tickets if t.type == "Bug"))
        features_count.append(sum(1 for t in week_tickets if t.type == "Feature"))

    return {"labels": labels, "bugs": bugs_count, "features": features_count}


# ── Full report payload (single API call) ─────────────────────────────────────

def full_report(days: Optional[int] = 30) -> Dict:
    sprints = list_sprints()
    active_sprint = next((s for s in sprints if s.status == "Active"), None)
    burndown = sprint_burndown(active_sprint.id) if active_sprint else {}

    return {
        "overview": overview(days),
        "by_status": by_status(days),
        "by_priority": by_priority(days),
        "by_type": by_type(days),
        "created_vs_resolved": created_vs_resolved(days or 30),
        "velocity": sprint_velocity(),
        "workload": workload_by_assignee(days),
        "aging": ticket_aging(),
        "burndown": burndown,
        "bug_rate": bug_rate(),
    }
