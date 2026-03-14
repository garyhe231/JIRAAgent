from dataclasses import dataclass, asdict
from typing import Optional
import hashlib
import os

ROLES = ["Admin", "Manager", "Developer", "Viewer"]

# Permissions per role
PERMISSIONS = {
    "Admin": {
        "manage_users", "manage_sprints", "delete_ticket",
        "create_ticket", "edit_any_ticket", "edit_own_ticket",
        "move_ticket", "add_comment", "view",
    },
    "Manager": {
        "manage_sprints", "delete_ticket",
        "create_ticket", "edit_any_ticket", "edit_own_ticket",
        "move_ticket", "add_comment", "view",
    },
    "Developer": {
        "create_ticket", "edit_own_ticket",
        "move_ticket", "add_comment", "view",
    },
    "Viewer": {"view"},
}


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception:
        return False


@dataclass
class User:
    id: str
    username: str
    email: str
    password_hash: str
    role: str          # Admin | Manager | Developer | Viewer
    display_name: str
    avatar_color: str  # hex color for avatar circle
    active: bool
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_safe_dict(self) -> dict:
        """Dict without password_hash — safe to send to templates."""
        d = asdict(self)
        del d["password_hash"]
        return d

    def can(self, permission: str) -> bool:
        return permission in PERMISSIONS.get(self.role, set())

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        return cls(**d)
