# JIRAAgent

AI-powered project management system built with FastAPI + Claude. Replaces JIRA with a clean dark UI, kanban board, sprints, multi-user auth, role-based permissions, and an AI assistant for natural-language ticket management.

## Features

- **Kanban board** — drag-and-drop tickets across lanes
- **Backlog & sprints** — full agile workflow
- **Multi-user auth** — login, sessions, profile management
- **Role-based permissions** — Admin / Manager / Developer / Viewer
- **AI Assistant** — create tickets from plain English, triage issues, sprint summaries
- **Admin panel** — invite users, change roles, reset passwords

---

## Quick Start (Local)

```bash
git clone https://github.com/garyhe231/JIRAAgent.git
cd JIRAAgent

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set SECRET_KEY and ANTHROPIC_API_KEY

python3 run.py
# Open http://localhost:8009
# Login: admin / admin123  (change immediately)
```

Optionally seed demo data:
```bash
python3 seed.py
```

---

## Deploy with Docker (Recommended)

### 1. Install Docker & Docker Compose

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### 2. Clone and configure

```bash
git clone https://github.com/garyhe231/JIRAAgent.git
cd JIRAAgent

cp .env.example .env
```

Edit `.env`:
```env
SECRET_KEY=<long-random-string>        # required — never share this
ANTHROPIC_API_KEY=sk-ant-...           # required for AI features
ADMIN_PASSWORD=<strong-password>       # change from default
PORT=8009
WORKERS=4
```

Generate a secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Build and run

```bash
docker compose up -d
```

App is now running on `http://your-server-ip:8009`.

### 4. View logs

```bash
docker compose logs -f
```

### 5. Update to latest version

```bash
git pull
docker compose up -d --build
```

Data persists in the `jiraagent_data` Docker volume across rebuilds.

---

## Deploy with Nginx (HTTPS)

### 1. Start the app with Docker Compose (as above)

### 2. Install nginx

```bash
sudo apt install nginx
```

### 3. Configure nginx

Edit `nginx.conf` and set your domain:
```nginx
server_name your-domain.com;
```

Copy to nginx sites:
```bash
sudo cp nginx.conf /etc/nginx/conf.d/jiraagent.conf
sudo nginx -t && sudo systemctl reload nginx
```

### 4. Get HTTPS certificate (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

Certbot will automatically configure HTTPS and set up auto-renewal.

---

## Deploy to a Cloud VM (AWS/GCP/DigitalOcean)

### DigitalOcean / AWS EC2 / Any Ubuntu VM

```bash
# 1. SSH into your server
ssh user@your-server-ip

# 2. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# 3. Clone and configure
git clone https://github.com/garyhe231/JIRAAgent.git
cd JIRAAgent
cp .env.example .env
nano .env   # fill in SECRET_KEY and ANTHROPIC_API_KEY

# 4. Run
docker compose up -d

# 5. Open firewall port (if needed)
# AWS: add inbound rule for port 8009 in Security Group
# GCP: gcloud compute firewall-rules create allow-jiraagent --allow tcp:8009
# DigitalOcean: UFW — sudo ufw allow 8009
```

App is now accessible at `http://your-server-ip:8009` from any browser.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(insecure default)* | **Required in production.** Signs session cookies. |
| `ANTHROPIC_API_KEY` | — | Required for AI chat, triage, and sprint summaries. |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8009` | Listen port |
| `WORKERS` | `1` | Uvicorn worker processes |
| `RELOAD` | `false` | Hot-reload (dev only) |
| `ADMIN_USERNAME` | `admin` | Default admin username (first run only) |
| `ADMIN_PASSWORD` | `admin123` | Default admin password — **change this** |
| `ADMIN_EMAIL` | `admin@jiraagent.local` | Default admin email |

---

## Roles & Permissions

| Role | Permissions |
|---|---|
| **Admin** | Full access: manage users, sprints, delete tickets, edit anything |
| **Manager** | Manage sprints & tickets, delete tickets — no user management |
| **Developer** | Create tickets, edit own tickets, move board cards, comment |
| **Viewer** | Read-only access |

---

## Data

All data is stored as JSON files in `./data/` (or the Docker volume `jiraagent_data`):

```
data/
  tickets/    # one JSON file per ticket
  sprints/    # one JSON file per sprint
  users/      # one JSON file per user
  counter.json
```

To back up: copy the entire `data/` directory or snapshot the Docker volume.

---

## Tech Stack

- **Backend:** FastAPI + Uvicorn
- **Templates:** Jinja2 + vanilla JS
- **AI:** Anthropic Claude (`claude-opus-4-6`)
- **Auth:** itsdangerous signed cookies
- **Storage:** JSON files (no external database required)
