from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional, List
import json

from app.services import ticket_store as ts
from app.services import ai_agent
from app.models.ticket import STATUSES, PRIORITIES, TYPES

app = FastAPI(title="JIRAAgent")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── Page routes ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
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
    return templates.TemplateResponse("index.html", {
        "request": request,
        "active_sprint": active_sprint,
        "sprints": sprints,
        "stats": stats,
    })


@app.get("/board", response_class=HTMLResponse)
async def board_page(request: Request, sprint_id: Optional[str] = None):
    active = ts.get_active_sprint()
    selected_sprint_id = sprint_id or (active.id if active else None)
    data = ts.board_data(selected_sprint_id)
    sprints = ts.list_sprints()
    sprint = ts.get_sprint(selected_sprint_id) if selected_sprint_id else None
    return templates.TemplateResponse("board.html", {
        "request": request,
        "lanes": data["lanes"],
        "sprint": sprint,
        "sprints": sprints,
        "statuses": STATUSES,
    })


@app.get("/backlog", response_class=HTMLResponse)
async def backlog_page(request: Request):
    backlog = ts.list_tickets(backlog_only=True)
    sprints = [s for s in ts.list_sprints() if s.status in ("Planning", "Active")]
    return templates.TemplateResponse("backlog.html", {
        "request": request,
        "tickets": backlog,
        "sprints": sprints,
        "priorities": PRIORITIES,
        "types": TYPES,
    })


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def ticket_detail(request: Request, ticket_id: str):
    ticket = ts.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    sprints = ts.list_sprints()
    return templates.TemplateResponse("ticket_detail.html", {
        "request": request,
        "ticket": ticket,
        "sprints": sprints,
        "statuses": STATUSES,
        "priorities": PRIORITIES,
        "types": TYPES,
    })


@app.get("/sprints", response_class=HTMLResponse)
async def sprints_page(request: Request):
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
    return templates.TemplateResponse("sprints.html", {
        "request": request,
        "sprint_data": sprint_data,
    })


@app.get("/ai", response_class=HTMLResponse)
async def ai_page(request: Request):
    return templates.TemplateResponse("ai.html", {"request": request})


# ── API: Tickets ─────────────────────────────────────────────────────────────

@app.post("/api/tickets")
async def api_create_ticket(
    title: str = Form(...),
    description: str = Form(""),
    type: str = Form("Task"),
    priority: str = Form("Medium"),
    assignee: str = Form("Unassigned"),
    reporter: str = Form("You"),
    labels: str = Form(""),
    sprint_id: str = Form(""),
    story_points: str = Form(""),
):
    label_list = [l.strip() for l in labels.split(",") if l.strip()]
    sp = int(story_points) if story_points.strip().isdigit() else None
    sid = sprint_id.strip() or None
    ticket = ts.create_ticket(
        title=title, description=description, type=type, priority=priority,
        assignee=assignee, reporter=reporter, labels=label_list,
        sprint_id=sid, story_points=sp,
    )
    return RedirectResponse(url=f"/tickets/{ticket.id}", status_code=303)


@app.post("/api/tickets/{ticket_id}/update")
async def api_update_ticket(
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
    fields = {}
    if status: fields["status"] = status
    if priority: fields["priority"] = priority
    if assignee: fields["assignee"] = assignee
    if title: fields["title"] = title
    if description: fields["description"] = description
    if type: fields["type"] = type
    if story_points is not None:
        fields["story_points"] = int(story_points) if story_points.strip().isdigit() else None
    if sprint_id is not None:
        fields["sprint_id"] = sprint_id.strip() or None
    ts.update_ticket(ticket_id, **fields)
    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=303)


@app.post("/api/tickets/{ticket_id}/comment")
async def api_add_comment(ticket_id: str, author: str = Form("You"), body: str = Form(...)):
    ts.add_comment(ticket_id, author=author, body=body)
    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=303)


@app.post("/api/tickets/{ticket_id}/delete")
async def api_delete_ticket(ticket_id: str):
    ts.delete_ticket(ticket_id)
    return RedirectResponse(url="/backlog", status_code=303)


@app.post("/api/tickets/{ticket_id}/triage")
async def api_triage(ticket_id: str):
    result = ai_agent.triage_ticket(ticket_id)
    return JSONResponse(result)


# ── API: Status drag-drop ────────────────────────────────────────────────────

@app.post("/api/tickets/{ticket_id}/move")
async def api_move_ticket(ticket_id: str, request: Request):
    body = await request.json()
    new_status = body.get("status")
    if new_status not in STATUSES:
        raise HTTPException(400, "Invalid status")
    updated = ts.update_ticket(ticket_id, status=new_status)
    return JSONResponse(updated.to_dict() if updated else {})


# ── API: Sprints ─────────────────────────────────────────────────────────────

@app.post("/api/sprints")
async def api_create_sprint(
    name: str = Form(""),
    goal: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
):
    sprint = ts.create_sprint(
        name=name or None,
        goal=goal,
        start_date=start_date or None,
        end_date=end_date or None,
    )
    return RedirectResponse(url="/sprints", status_code=303)


@app.post("/api/sprints/{sprint_id}/start")
async def api_start_sprint(sprint_id: str):
    ts.update_sprint(sprint_id, status="Active")
    return RedirectResponse(url="/sprints", status_code=303)


@app.post("/api/sprints/{sprint_id}/complete")
async def api_complete_sprint(sprint_id: str):
    ts.update_sprint(sprint_id, status="Completed")
    return RedirectResponse(url="/sprints", status_code=303)


@app.get("/api/sprints/{sprint_id}/summary")
async def api_sprint_summary(sprint_id: str):
    summary = ai_agent.sprint_summary(sprint_id)
    return JSONResponse({"summary": summary})


# ── API: AI Chat ─────────────────────────────────────────────────────────────

_chat_sessions = {}

@app.post("/api/ai/chat")
async def api_ai_chat(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "default")
    message = body.get("message", "")
    if not message:
        raise HTTPException(400, "message required")
    history = _chat_sessions.get(session_id, [])
    result = ai_agent.chat(history, message)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": result["reply"]})
    _chat_sessions[session_id] = history[-40:]
    return JSONResponse(result)


# ── API: List (JSON) ─────────────────────────────────────────────────────────

@app.get("/api/tickets")
async def api_list_tickets(
    status: Optional[str] = None,
    sprint_id: Optional[str] = None,
    assignee: Optional[str] = None,
):
    tickets = ts.list_tickets(status=status, sprint_id=sprint_id, assignee=assignee)
    return JSONResponse([t.to_dict() for t in tickets])


@app.get("/api/board")
async def api_board(sprint_id: Optional[str] = None):
    return JSONResponse(ts.board_data(sprint_id))
