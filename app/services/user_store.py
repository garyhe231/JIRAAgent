import json
import os
import uuid
from typing import List, Optional

from app.models.user import User, hash_password, verify_password, ROLES

USERS_DIR = "data/users"
AVATAR_COLORS = [
    "#4f7ef8", "#22c55e", "#f59e0b", "#ef4444",
    "#a855f7", "#06b6d4", "#f97316", "#ec4899",
]


def _save_user(user: User):
    os.makedirs(USERS_DIR, exist_ok=True)
    with open(os.path.join(USERS_DIR, f"{user.id}.json"), "w") as f:
        json.dump(user.to_dict(), f, indent=2)


def create_user(
    username: str,
    email: str,
    password: str,
    role: str = "Developer",
    display_name: str = "",
) -> User:
    from datetime import datetime
    existing = list_users()
    color = AVATAR_COLORS[len(existing) % len(AVATAR_COLORS)]
    user = User(
        id=str(uuid.uuid4()),
        username=username.lower().strip(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
        display_name=display_name or username,
        avatar_color=color,
        active=True,
        created_at=datetime.utcnow().isoformat(),
    )
    _save_user(user)
    return user


def get_user(user_id: str) -> Optional[User]:
    path = os.path.join(USERS_DIR, f"{user_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return User.from_dict(json.load(f))


def get_user_by_username(username: str) -> Optional[User]:
    for u in list_users():
        if u.username == username.lower().strip():
            return u
    return None


def list_users() -> List[User]:
    users = []
    if not os.path.exists(USERS_DIR):
        return users
    for fname in os.listdir(USERS_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(USERS_DIR, fname)) as f:
            users.append(User.from_dict(json.load(f)))
    users.sort(key=lambda u: u.created_at)
    return users


def authenticate(username: str, password: str) -> Optional[User]:
    user = get_user_by_username(username)
    if user and user.active and verify_password(password, user.password_hash):
        return user
    return None


def update_user(user_id: str, **kwargs) -> Optional[User]:
    user = get_user(user_id)
    if not user:
        return None
    for k, v in kwargs.items():
        if hasattr(user, k) and k != "password_hash":
            setattr(user, k, v)
    _save_user(user)
    return user


def change_password(user_id: str, new_password: str) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    user.password_hash = hash_password(new_password)
    _save_user(user)
    return True


def ensure_admin_exists():
    """Create a default admin if no users exist."""
    if not list_users():
        create_user(
            username="admin",
            email="admin@jiraagent.local",
            password="admin123",
            role="Admin",
            display_name="Admin",
        )
