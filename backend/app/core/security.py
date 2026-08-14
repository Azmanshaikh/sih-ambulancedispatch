from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.core.supabase import auth_user_from_token
from app.services.profiles import ensure_profile


def _bootstrap_emails() -> set[str]:
    return {e.strip().lower() for e in (settings.STAFF_BOOTSTRAP_EMAILS or "").split(",") if e.strip()}


def _user_from_bearer(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")

    payload = auth_user_from_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    user_id = payload.get("id")
    email = payload.get("email")
    meta = payload.get("user_metadata") or {}
    full_name = meta.get("full_name") or meta.get("name")

    if not user_id or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    bootstrap = email.lower() in _bootstrap_emails()
    profile = ensure_profile(str(user_id), email, full_name, bootstrap_staff=bootstrap)
    if bootstrap:
        profile["onboarded"] = True
    elif profile.get("role") in ("driver", "staff") and profile.get("status") == "active":
        profile["onboarded"] = True
    else:
        profile.setdefault("onboarded", False)
    return {"id": str(user_id), "email": email, "full_name": full_name, "profile": profile, "token": token}


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    return _user_from_bearer(authorization)


def require_roles(*roles: str):
    def _dep(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        role = (user.get("profile") or {}).get("role")
        status_flag = (user.get("profile") or {}).get("status")
        if status_flag != "active" or role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for this role")
        return user

    return _dep
