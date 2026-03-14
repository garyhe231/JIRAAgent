"""
AI Agent: natural-language ticket creation, triage, Q&A, and suggestions.
"""
import json
import os
from typing import Optional, List, Dict

import anthropic

from app.services.ticket_store import (
    list_tickets, list_sprints, get_active_sprint, board_data,
    create_ticket, update_ticket, add_comment, create_sprint,
)
from app.models.ticket import STATUSES, PRIORITIES, TYPES

client = anthropic.Anthropic()
MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """You are an expert project manager AI assistant embedded in a JIRA-like ticketing system.

You help users:
1. Create tickets from natural-language descriptions
2. Triage and prioritize tickets
3. Suggest assignees and story points
4. Answer questions about the project status
5. Summarize sprint progress
6. Identify blockers and risks

When the user asks to CREATE a ticket, respond ONLY with a JSON object (no markdown fences) like:
{
  "action": "create_ticket",
  "title": "...",
  "description": "...",
  "type": "Bug|Feature|Task|Story|Epic|Improvement",
  "priority": "Critical|High|Medium|Low",
  "assignee": "Unassigned",
  "labels": [],
  "story_points": null
}

When the user asks to UPDATE a ticket (e.g. "close JIRA-3", "assign JIRA-5 to Alice"), respond ONLY with JSON:
{
  "action": "update_ticket",
  "key": "JIRA-X",
  "fields": { "status": "Done" }
}

When the user asks to ADD A COMMENT, respond ONLY with JSON:
{
  "action": "add_comment",
  "key": "JIRA-X",
  "body": "..."
}

For all other questions (status, summaries, advice), respond in plain conversational text. Be concise and helpful.
"""


def _context_summary() -> str:
    sprints = list_sprints()
    active = get_active_sprint()
    all_tickets = list_tickets()
    by_status = {}
    for t in all_tickets:
        by_status.setdefault(t.status, 0)
        by_status[t.status] += 1

    lines = [f"Total tickets: {len(all_tickets)}"]
    for s, c in sorted(by_status.items()):
        lines.append(f"  {s}: {c}")
    if active:
        sprint_tickets = list_tickets(sprint_id=active.id)
        lines.append(f"Active sprint: {active.name} ({len(sprint_tickets)} tickets)")
    else:
        lines.append("No active sprint.")
    return "\n".join(lines)


def chat(history: List[Dict], user_message: str) -> Dict:
    """
    Send a message to the AI. Returns dict with:
      - reply: str (the text to show the user)
      - action_result: dict or None (if an action was taken)
    """
    context = _context_summary()

    messages = []
    for h in history[-20:]:  # keep last 20 turns
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})

    full_system = SYSTEM_PROMPT + f"\n\nCurrent project context:\n{context}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=full_system,
        messages=messages,
    )

    raw = response.content[0].text.strip()

    # Try to parse as action JSON
    action_result = None
    reply = raw
    try:
        data = json.loads(raw)
        action = data.get("action")

        if action == "create_ticket":
            ticket = create_ticket(
                title=data.get("title", "Untitled"),
                description=data.get("description", ""),
                type=data.get("type", "Task"),
                priority=data.get("priority", "Medium"),
                assignee=data.get("assignee", "Unassigned"),
                labels=data.get("labels", []),
                story_points=data.get("story_points"),
            )
            reply = f"Created ticket **{ticket.key}**: {ticket.title}"
            action_result = {"type": "created", "ticket": ticket.to_dict()}

        elif action == "update_ticket":
            from app.services.ticket_store import get_ticket_by_key
            key = data.get("key", "")
            t = get_ticket_by_key(key)
            if t:
                fields = data.get("fields", {})
                updated = update_ticket(t.id, **fields)
                reply = f"Updated {key}: " + ", ".join(f"{k}={v}" for k, v in fields.items())
                action_result = {"type": "updated", "ticket": updated.to_dict() if updated else None}
            else:
                reply = f"Could not find ticket {key}."

        elif action == "add_comment":
            from app.services.ticket_store import get_ticket_by_key
            key = data.get("key", "")
            t = get_ticket_by_key(key)
            if t:
                comment = add_comment(t.id, author="AI Assistant", body=data.get("body", ""))
                reply = f"Added comment to {key}."
                action_result = {"type": "comment", "comment": comment.to_dict() if comment else None}
            else:
                reply = f"Could not find ticket {key}."

    except (json.JSONDecodeError, KeyError):
        pass  # plain text reply

    return {"reply": reply, "action_result": action_result}


def triage_ticket(ticket_id: str) -> Dict:
    """AI analysis of a single ticket: priority, points, risks."""
    from app.services.ticket_store import get_ticket
    ticket = get_ticket(ticket_id)
    if not ticket:
        return {"error": "Ticket not found"}

    prompt = f"""Analyze this ticket and respond ONLY with a JSON object (no fences):
{{
  "suggested_priority": "Critical|High|Medium|Low",
  "suggested_story_points": <integer 1-13>,
  "suggested_type": "Bug|Feature|Task|Story|Epic|Improvement",
  "summary": "<2-sentence plain-text analysis>",
  "risks": ["<risk1>", "<risk2>"],
  "suggested_labels": ["<label>"]
}}

Ticket:
Title: {ticket.title}
Description: {ticket.description}
Current priority: {ticket.priority}
Type: {ticket.type}
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system="You are an expert software project manager.",
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return json.loads(response.content[0].text.strip())
    except Exception:
        return {"summary": response.content[0].text.strip()}


def sprint_summary(sprint_id: Optional[str] = None) -> str:
    """AI-generated sprint health summary."""
    active = get_active_sprint() if not sprint_id else None
    if sprint_id:
        from app.services.ticket_store import get_sprint
        sprint = get_sprint(sprint_id)
    else:
        sprint = active

    if not sprint:
        return "No sprint found."

    tickets = list_tickets(sprint_id=sprint.id)
    total = len(tickets)
    done = sum(1 for t in tickets if t.status == "Done")
    in_progress = sum(1 for t in tickets if t.status == "In Progress")
    blocked = [t for t in tickets if "blocked" in [l.lower() for l in t.labels]]
    points_done = sum(t.story_points or 0 for t in tickets if t.status == "Done")
    points_total = sum(t.story_points or 0 for t in tickets)

    ticket_list = "\n".join(
        f"- [{t.key}] {t.title} | {t.status} | {t.priority} | {t.assignee}"
        for t in tickets
    )

    prompt = f"""Sprint: {sprint.name}
Goal: {sprint.goal}
Status: {sprint.status}
Total tickets: {total} | Done: {done} | In Progress: {in_progress} | Blocked: {len(blocked)}
Story points: {points_done}/{points_total} completed

Tickets:
{ticket_list}

Write a concise 3-5 sentence sprint health summary for the team. Highlight risks and blocked items.
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system="You are an expert agile coach.",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
