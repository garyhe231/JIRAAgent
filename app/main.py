from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional, List
import json

from app.services import ticket_store as ts
from app.services import ai_agent
from app.services import user_store as us
from app.services import project_store as ps
from app.services import analytics
from app.services.auth import (
    get_current_user, create_session_token, SESSION_COOKIE,
)
from app.models.ticket import STATUSES, PRIORITIES, TYPES
from app.models.user import ROLES, PERMISSIONS
from app.models.project import PROJECT_STATUSES, PROJECT_COLORS

app = FastAPI(title="JIRAAgent")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup():
    us.ensure_admin_exists()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _ctx(request: Request, **kwargs):
    """Base template context with current_user injected."""
    user = get_current_user(request)
    return {"request": request, "current_user": user, **kwargs}


def _require(request: Request, permission: str = "view"):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    if not user.can(permission):
        raise HTTPException(status_code=403, detail=f"Requires permission: {permission}")
    return user


# ── Auth pages ────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = "", next: str = "/"):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": error, "next": next})


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    user = us.authenticate(username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password.", "next": next},
            status_code=401,
        )
    token = create_session_token(user.id)
    dest = next if next.startswith("/") else "/"
    resp = RedirectResponse(dest, status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, max_age=86400 * 30, samesite="lax")
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user = _require(request)
    return templates.TemplateResponse("profile.html", _ctx(request, user=user))


@app.post("/profile/update")
async def profile_update(
    request: Request,
    display_name: str = Form(""),
    email: str = Form(""),
):
    user = _require(request)
    fields = {}
    if display_name.strip():
        fields["display_name"] = display_name.strip()
    if email.strip():
        fields["email"] = email.strip().lower()
    us.update_user(user.id, **fields)
    return RedirectResponse("/profile", status_code=303)


@app.post("/profile/password")
async def profile_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
):
    user = _require(request)
    from app.models.user import verify_password
    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse(
            "profile.html",
            _ctx(request, user=user, pw_error="Current password is incorrect."),
        )
    us.change_password(user.id, new_password)
    return RedirectResponse("/profile?pw_changed=1", status_code=303)


# ── Admin: User management ────────────────────────────────────────────────────

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    _require(request, "manage_users")
    users = us.list_users()
    return templates.TemplateResponse("admin_users.html", _ctx(request, users=users, roles=ROLES))


@app.post("/admin/users/create")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
    role: str = Form("Developer"),
):
    _require(request, "manage_users")
    if us.get_user_by_username(username):
        users = us.list_users()
        return templates.TemplateResponse(
            "admin_users.html",
            _ctx(request, users=users, roles=ROLES, error=f"Username '{username}' already exists."),
        )
    us.create_user(username=username, email=email, password=password, role=role, display_name=display_name)
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{user_id}/role")
async def admin_change_role(request: Request, user_id: str, role: str = Form(...)):
    current = _require(request, "manage_users")
    if user_id == current.id:
        raise HTTPException(400, "Cannot change your own role.")
    if role not in ROLES:
        raise HTTPException(400, "Invalid role.")
    us.update_user(user_id, role=role)
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{user_id}/toggle")
async def admin_toggle_user(request: Request, user_id: str):
    current = _require(request, "manage_users")
    if user_id == current.id:
        raise HTTPException(400, "Cannot deactivate yourself.")
    target = us.get_user(user_id)
    if target:
        us.update_user(user_id, active=not target.active)
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(
    request: Request, user_id: str, new_password: str = Form(...)
):
    _require(request, "manage_users")
    us.change_password(user_id, new_password)
    return RedirectResponse("/admin/users", status_code=303)


# ── Page routes ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    _require(request)
    active_sprint = ts.get_active_sprint()
    sprints = ts.list_sprints()
    all_tickets = ts.list_tickets()
    backlog = ts.list_tickets(backlog_only=True)
    stats = {
        "total": len(all_tickets),
        "backlog": len(backlog),
        "in_progress": sum(1 for t in all_tickets if t.status == "In Progress"),
        "done": sum(1 for t in all_tickets if t.status == "Done"),
    }
    return templates.TemplateResponse("index.html", _ctx(
        request, active_sprint=active_sprint, sprints=sprints, stats=stats,
    ))


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    _require(request)
    sprints = ts.list_sprints()
    active_sprint = ts.get_active_sprint()
    projects = ps.list_projects()
    return templates.TemplateResponse("reports.html", _ctx(
        request, sprints=sprints, active_sprint=active_sprint, projects=projects,
    ))


@app.get("/api/reports/data")
async def api_reports_data(request: Request, days: Optional[int] = 30):
    _require(request)
    return JSONResponse(analytics.full_report(days))


@app.get("/api/reports/burndown/{sprint_id}")
async def api_burndown(request: Request, sprint_id: str):
    _require(request)
    return JSONResponse(analytics.sprint_burndown(sprint_id))


@app.get("/board", response_class=HTMLResponse)
async def board_page(request: Request, sprint_id: Optional[str] = None):
    _require(request)
    active = ts.get_active_sprint()
    selected_sprint_id = sprint_id or (active.id if active else None)
    data = ts.board_data(selected_sprint_id)
    sprints = ts.list_sprints()
    sprint = ts.get_sprint(selected_sprint_id) if selected_sprint_id else None
    return templates.TemplateResponse("board.html", _ctx(
        request, lanes=data["lanes"], sprint=sprint, sprints=sprints, statuses=STATUSES,
    ))


@app.get("/backlog", response_class=HTMLResponse)
async def backlog_page(request: Request):
    _require(request)
    backlog = ts.list_tickets(backlog_only=True)
    sprints = [s for s in ts.list_sprints() if s.status in ("Planning", "Active")]
    return templates.TemplateResponse("backlog.html", _ctx(
        request, tickets=backlog, sprints=sprints, priorities=PRIORITIES, types=TYPES,
    ))


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def ticket_detail(request: Request, ticket_id: str):
    _require(request)
    ticket = ts.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    sprints = ts.list_sprints()
    all_users = us.list_users()
    projects = ps.list_projects()
    milestones = ps.list_milestones(ticket.project_id) if ticket.project_id else []
    return templates.TemplateResponse("ticket_detail.html", _ctx(
        request, ticket=ticket, sprints=sprints,
        statuses=STATUSES, priorities=PRIORITIES, types=TYPES,
        all_users=all_users, projects=projects, milestones=milestones,
    ))


@app.get("/sprints", response_class=HTMLResponse)
async def sprints_page(request: Request):
    _require(request)
    sprints = ts.list_sprints()
    sprint_data = []
    for s in sprints:
        tickets = ts.list_tickets(sprint_id=s.id)
        done = sum(1 for t in tickets if t.status == "Done")
        points_total = sum(t.story_points or 0 for t in tickets)
        points_done = sum(t.story_points or 0 for t in tickets if t.status == "Done")
        sprint_data.append({
            "sprint": s,
            "total": len(tickets),
            "done": done,
            "points_total": points_total,
            "points_done": points_done,
        })
    return templates.TemplateResponse("sprints.html", _ctx(request, sprint_data=sprint_data))


@app.get("/ai", response_class=HTMLResponse)
async def ai_page(request: Request):
    _require(request)
    return templates.TemplateResponse("ai.html", _ctx(request))


# ── API: Tickets ─────────────────────────────────────────────────────────────

@app.post("/api/tickets")
async def api_create_ticket(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    type: str = Form("Task"),
    priority: str = Form("Medium"),
    assignee: str = Form("Unassigned"),
    labels: str = Form(""),
    sprint_id: str = Form(""),
    story_points: str = Form(""),
):
    user = _require(request, "create_ticket")
    label_list = [l.strip() for l in labels.split(",") if l.strip()]
    sp = int(story_points) if story_points.strip().isdigit() else None
    sid = sprint_id.strip() or None
    ticket = ts.create_ticket(
        title=title, description=description, type=type, priority=priority,
        assignee=assignee, reporter=user.display_name, labels=label_list,
        sprint_id=sid, story_points=sp,
    )
    return RedirectResponse(url=f"/tickets/{ticket.id}", status_code=303)


@app.post("/api/tickets/{ticket_id}/update")
async def api_update_ticket(
    request: Request,
    ticket_id: str,
    status: str = Form(None),
    priority: str = Form(None),
    assignee: str = Form(None),
    title: str = Form(None),
    description: str = Form(None),
    story_points: str = Form(None),
    sprint_id: str = Form(None),
    type: str = Form(None),
):
    user = _require(request, "view")
    ticket = ts.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    # Permission: Developer can only edit their own tickets (except status/move)
    is_own = ticket.assignee == user.display_name or ticket.reporter == user.display_name
    if not user.can("edit_any_ticket") and not is_own:
        raise HTTPException(403, "You can only edit tickets assigned to or reported by you.")

    fields = {}
    if status: fields["status"] = status
    if priority and user.can("edit_any_ticket"): fields["priority"] = priority
    if assignee and user.can("edit_any_ticket"): fields["assignee"] = assignee
    if title and user.can("edit_any_ticket"): fields["title"] = title
    if description: fields["description"] = description
    if type and user.can("edit_any_ticket"): fields["type"] = type
    if story_points is not None and user.can("edit_any_ticket"):
        fields["story_points"] = int(story_points) if story_points.strip().isdigit() else None
    if sprint_id is not None and user.can("edit_any_ticket"):
        fields["sprint_id"] = sprint_id.strip() or None
    ts.update_ticket(ticket_id, **fields)
    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=303)


@app.post("/api/tickets/{ticket_id}/comment")
async def api_add_comment(
    request: Request,
    ticket_id: str,
    body: str = Form(...),
):
    user = _require(request, "add_comment")
    ts.add_comment(ticket_id, author=user.display_name, body=body)
    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=303)


@app.post("/api/tickets/{ticket_id}/delete")
async def api_delete_ticket(request: Request, ticket_id: str):
    _require(request, "delete_ticket")
    ts.delete_ticket(ticket_id)
    return RedirectResponse(url="/backlog", status_code=303)


@app.post("/api/tickets/{ticket_id}/triage")
async def api_triage(request: Request, ticket_id: str):
    _require(request)
    result = ai_agent.triage_ticket(ticket_id)
    return JSONResponse(result)


@app.post("/api/tickets/{ticket_id}/move")
async def api_move_ticket(request: Request, ticket_id: str):
    _require(request, "move_ticket")
    body = await request.json()
    new_status = body.get("status")
    if new_status not in STATUSES:
        raise HTTPException(400, "Invalid status")
    updated = ts.update_ticket(ticket_id, status=new_status)
    return JSONResponse(updated.to_dict() if updated else {})


# ── API: Sprints ─────────────────────────────────────────────────────────────

@app.post("/api/sprints")
async def api_create_sprint(
    request: Request,
    name: str = Form(""),
    goal: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
):
    _require(request, "manage_sprints")
    ts.create_sprint(name=name or None, goal=goal, start_date=start_date or None, end_date=end_date or None)
    return RedirectResponse(url="/sprints", status_code=303)


@app.post("/api/sprints/{sprint_id}/start")
async def api_start_sprint(request: Request, sprint_id: str):
    _require(request, "manage_sprints")
    ts.update_sprint(sprint_id, status="Active")
    return RedirectResponse(url="/sprints", status_code=303)


@app.post("/api/sprints/{sprint_id}/complete")
async def api_complete_sprint(request: Request, sprint_id: str):
    _require(request, "manage_sprints")
    ts.update_sprint(sprint_id, status="Completed")
    return RedirectResponse(url="/sprints", status_code=303)


@app.get("/api/sprints/{sprint_id}/summary")
async def api_sprint_summary(request: Request, sprint_id: str):
    _require(request)
    summary = ai_agent.sprint_summary(sprint_id)
    return JSONResponse({"summary": summary})


# ── API: AI Chat ─────────────────────────────────────────────────────────────

_chat_sessions = {}

@app.post("/api/ai/chat")
async def api_ai_chat(request: Request):
    user = _require(request)
    body = await request.json()
    session_id = f"{user.id}-{body.get('session_id', 'main')}"
    message = body.get("message", "")
    if not message:
        raise HTTPException(400, "message required")
    history = _chat_sessions.get(session_id, [])
    result = ai_agent.chat(history, message, user=user)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": result["reply"]})
    _chat_sessions[session_id] = history[-40:]
    return JSONResponse(result)


# ── API: List (JSON) ─────────────────────────────────────────────────────────

@app.get("/api/tickets")
async def api_list_tickets(
    request: Request,
    status: Optional[str] = None,
    sprint_id: Optional[str] = None,
    assignee: Optional[str] = None,
):
    _require(request)
    tickets = ts.list_tickets(status=status, sprint_id=sprint_id, assignee=assignee)
    return JSONResponse([t.to_dict() for t in tickets])


@app.get("/api/board")
async def api_board(request: Request, sprint_id: Optional[str] = None):
    _require(request)
    return JSONResponse(ts.board_data(sprint_id))


@app.get("/api/users")
async def api_users(request: Request):
    _require(request)
    return JSONResponse([u.to_safe_dict() for u in us.list_users() if u.active])


# ── Projects: pages ───────────────────────────────────────────────────────────

@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    _require(request)
    projects = ps.list_projects()
    project_data = []
    for p in projects:
        tickets = ts.list_tickets(project_id=p.id)
        stats = ps.project_stats(p.id, tickets)
        milestones = ps.list_milestones(p.id)
        project_data.append({"project": p, "stats": stats, "milestones": milestones})
    return templates.TemplateResponse("projects.html", _ctx(
        request, project_data=project_data, project_statuses=PROJECT_STATUSES,
        project_colors=PROJECT_COLORS,
    ))


@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: str):
    _require(request)
    project = ps.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    tickets = ts.list_tickets(project_id=project_id)
    milestones = ps.list_milestones(project_id)
    stats = ps.project_stats(project_id, tickets)
    all_tickets = ts.list_tickets()  # for linking
    sprints = ts.list_sprints()
    all_users = us.list_users()
    return templates.TemplateResponse("project_detail.html", _ctx(
        request, project=project, tickets=tickets, milestones=milestones,
        stats=stats, all_tickets=all_tickets, sprints=sprints,
        all_users=all_users, project_statuses=PROJECT_STATUSES,
        statuses=STATUSES, priorities=PRIORITIES, types=TYPES,
    ))


# ── Projects: API ─────────────────────────────────────────────────────────────

@app.post("/api/projects")
async def api_create_project(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    status: str = Form("Active"),
    color: str = Form(""),
):
    user = _require(request, "manage_sprints")
    ps.create_project(name=name, description=description, status=status,
                      color=color or "", owner=user.display_name)
    return RedirectResponse("/projects", status_code=303)


@app.post("/api/projects/{project_id}/update")
async def api_update_project(
    request: Request,
    project_id: str,
    name: str = Form(None),
    description: str = Form(None),
    status: str = Form(None),
    color: str = Form(None),
):
    _require(request, "manage_sprints")
    fields = {k: v for k, v in
              {"name": name, "description": description, "status": status, "color": color}.items()
              if v is not None}
    ps.update_project(project_id, **fields)
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@app.post("/api/projects/{project_id}/delete")
async def api_delete_project(request: Request, project_id: str):
    _require(request, "manage_sprints")
    ps.delete_project(project_id)
    return RedirectResponse("/projects", status_code=303)


# ── Milestones: API ───────────────────────────────────────────────────────────

@app.post("/api/projects/{project_id}/milestones")
async def api_create_milestone(
    request: Request,
    project_id: str,
    name: str = Form(...),
    description: str = Form(""),
    due_date: str = Form(""),
):
    _require(request, "manage_sprints")
    ps.create_milestone(project_id=project_id, name=name,
                        description=description, due_date=due_date or None)
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@app.post("/api/milestones/{milestone_id}/update")
async def api_update_milestone(
    request: Request,
    milestone_id: str,
    name: str = Form(None),
    description: str = Form(None),
    due_date: str = Form(None),
    status: str = Form(None),
):
    _require(request, "manage_sprints")
    fields = {}
    if name: fields["name"] = name
    if description is not None: fields["description"] = description
    if due_date is not None: fields["due_date"] = due_date or None
    if status: fields["status"] = status
    ms = ps.update_milestone(milestone_id, **fields)
    project_id = ms.project_id if ms else ""
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@app.post("/api/milestones/{milestone_id}/delete")
async def api_delete_milestone(request: Request, milestone_id: str):
    _require(request, "manage_sprints")
    ms = ps.get_milestone(milestone_id)
    project_id = ms.project_id if ms else ""
    ps.delete_milestone(milestone_id)
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


# ── Ticket ↔ Project/Milestone linking ───────────────────────────────────────

@app.post("/api/tickets/{ticket_id}/link")
async def api_link_ticket(
    request: Request,
    ticket_id: str,
    project_id: str = Form(""),
    milestone_id: str = Form(""),
):
    _require(request, "edit_any_ticket")
    fields = {
        "project_id": project_id or None,
        "milestone_id": milestone_id or None,
    }
    ts.update_ticket(ticket_id, **fields)
    return RedirectResponse(f"/tickets/{ticket_id}", status_code=303)


@app.get("/api/projects/{project_id}/stats")
async def api_project_stats(request: Request, project_id: str):
    _require(request)
    tickets = ts.list_tickets(project_id=project_id)
    return JSONResponse(ps.project_stats(project_id, tickets))
