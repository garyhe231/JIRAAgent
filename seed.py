"""Seed demo data — run once: python3 seed.py"""
import os
os.makedirs("data/tickets", exist_ok=True)
os.makedirs("data/sprints", exist_ok=True)

from app.services.ticket_store import create_ticket, create_sprint, update_ticket, update_sprint, add_comment

# Create a sprint
s1 = create_sprint(name="Sprint 1 — Auth & Onboarding", goal="Ship login, signup, and user profile flows", start_date="2026-03-10", end_date="2026-03-24")
update_sprint(s1.id, status="Active")

s2 = create_sprint(name="Sprint 2 — Dashboard & Reports", goal="Build analytics dashboard and PDF export", start_date="2026-03-25", end_date="2026-04-07")

# Tickets in Sprint 1
t1 = create_ticket("Fix login loop on mobile Safari", description="Users on iOS 17 Safari get redirected back to login even after successful auth. Likely a cookie SameSite issue.", type="Bug", priority="Critical", assignee="Alice", labels=["auth","mobile"], sprint_id=s1.id, story_points=5)
update_ticket(t1.id, status="In Progress")
add_comment(t1.id, "Alice", "Reproduced on iPhone 14. It's the SameSite=Lax cookie not being accepted in cross-site iframes. Working on a fix.")

t2 = create_ticket("Implement Google OAuth 2.0 sign-in", description="Allow users to sign in using their Google account. Need to add the OAuth flow, handle callback, and create/link user accounts.", type="Feature", priority="High", assignee="Bob", labels=["auth","oauth"], sprint_id=s1.id, story_points=8)
update_ticket(t2.id, status="In Review")

t3 = create_ticket("Add email verification on signup", description="Send a verification email when a new user registers. Block login until email is confirmed.", type="Feature", priority="Medium", assignee="Carol", labels=["auth","email"], sprint_id=s1.id, story_points=3)
update_ticket(t3.id, status="Done")

t4 = create_ticket("Design user profile page", description="Create the UI for user profile: avatar, display name, email, timezone, notification preferences.", type="Task", priority="Medium", assignee="Dave", labels=["frontend","profile"], sprint_id=s1.id, story_points=5)
update_ticket(t4.id, status="To Do")

t5 = create_ticket("Rate limiting on auth endpoints", description="Protect /login and /signup with rate limiting to prevent brute force attacks.", type="Improvement", priority="High", assignee="Alice", labels=["security","auth"], sprint_id=s1.id, story_points=3)
update_ticket(t5.id, status="To Do")

# Backlog tickets
t6 = create_ticket("Build analytics dashboard", description="Real-time charts for DAU, MAU, revenue, churn rate. Use Chart.js.", type="Feature", priority="High", assignee="Unassigned", labels=["dashboard","analytics"], story_points=13)
t7 = create_ticket("PDF export for reports", description="Allow users to export any report as a formatted PDF.", type="Feature", priority="Medium", assignee="Unassigned", labels=["reports","export"], story_points=5)
t8 = create_ticket("Dark mode support", description="Add a dark/light theme toggle. Persist preference in localStorage.", type="Improvement", priority="Low", assignee="Dave", labels=["frontend","ux"], story_points=3)
t9 = create_ticket("Write API documentation", description="Document all REST endpoints using OpenAPI. Include request/response examples.", type="Task", priority="Low", assignee="Unassigned", labels=["docs"])
t10 = create_ticket("Investigate memory leak in WebSocket service", description="Memory usage grows ~50MB/hour under load. Heap dump attached.", type="Bug", priority="Critical", assignee="Bob", labels=["backend","performance","blocked"])

print("Seeded successfully!")
print(f"  Sprint 1 (Active): {s1.id}")
print(f"  Sprint 2 (Planning): {s2.id}")
print(f"  Tickets: {t1.key}, {t2.key}, {t3.key}, {t4.key}, {t5.key}, {t6.key}, {t7.key}, {t8.key}, {t9.key}, {t10.key}")
