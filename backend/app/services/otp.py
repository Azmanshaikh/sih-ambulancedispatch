from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.runtime_state import push_alert

_otps: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_otp(user_id: str, email: str, full_name: str | None, requested_role: str) -> dict[str, Any]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = {
        "user_id": user_id,
        "email": email,
        "full_name": full_name or email,
        "requested_role": requested_role,
        "code": code,
        "attempts": 0,
        "created_at": _now().isoformat(),
        "expires_at": (_now() + timedelta(minutes=15)).isoformat(),
        "used": False,
    }
    _otps[user_id] = row
    print(f"[JEEVAN OTP] {requested_role} for {email}: {code}")
    who = full_name or email
    push_alert(
        "staff",
        "ACCESS OTP",
        f"{who} ({email}) wants to join as {requested_role}. OTP: {code}. Give this code only if you know them.",
        extra={"otp": code, "otp_email": email, "otp_role": requested_role},
    )
    return {k: v for k, v in row.items() if k != "code"}


def list_active_otps() -> list[dict[str, Any]]:
    now = _now()
    out = []
    for row in _otps.values():
        if row.get("used"):
            continue
        exp = datetime.fromisoformat(row["expires_at"])
        if exp < now:
            continue
        out.append(dict(row))
    out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return out


def verify_otp(user_id: str, code: str) -> dict[str, Any]:
    row = _otps.get(user_id)
    if not row or row.get("used"):
        raise ValueError("No OTP pending. Choose Driver or Staff again.")
    exp = datetime.fromisoformat(row["expires_at"])
    if exp < _now():
        raise ValueError("OTP expired. Request a new one.")
    row["attempts"] = int(row.get("attempts") or 0) + 1
    if row["attempts"] > 8:
        raise ValueError("Too many attempts. Request a new OTP.")
    entered = "".join(ch for ch in (code or "") if ch.isdigit())
    if entered != row["code"]:
        raise ValueError("Wrong OTP. Ask staff for the current code.")
    row["used"] = True
    return row
