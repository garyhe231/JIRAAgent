"""
Session-based authentication helpers.
Sessions stored as signed cookies (itsdangerous).
"""
import os
from typing import Optional

from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.models.user import User
from app.services.user_store import get_user

SECRET_KEY = os.environ.get("SECRET_KEY", "jiraagent-secret-key-change-in-prod")
SESSION_COOKIE = "jira_session"
_signer = URLSafeTimedSerializer(SECRET_KEY)


def create_session_token(user_id: str) -> str:
    return _signer.dumps(user_id)


def decode_session_token(token: str) -> Optional[str]:
    try:
        return _signer.loads(token, max_age=86400 * 30)  # 30 days
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request) -> Optional[User]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user_id = decode_session_token(token)
    if not user_id:
        return None
    user = get_user(user_id)
    return user if (user and user.active) else None


def require_user(request: Request) -> User:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


def require_permission(request: Request, permission: str) -> User:
    user = require_user(request)
    if not user.can(permission):
        raise HTTPException(status_code=403, detail=f"Permission denied: requires '{permission}'")
    return user
