from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.supabase import rest_select, rest_update
from app.services.mail import head_staff_emails
from app.services.runtime_state import push_alert

_otps: dict[str, dict[str, Any]] = {}
_OTP_TITLE = "ACCESS OTP"
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
    except Exception:
        return None


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k != "code"}


def _from_alert(alert: dict[str, Any]) -> dict[str, Any] | None:
    payload = alert.get("payload") if isinstance(alert.get("payload"), dict) else {}
    merged = {**payload, **alert}
    code = str(merged.get("otp") or payload.get("otp") or "")
    user_id = str(merged.get("otp_user_id") or payload.get("otp_user_id") or "")
    if not code or not user_id:
        return None
    if merged.get("otp_used") or payload.get("otp_used"):
        return None
    return {
        "alert_id": str(alert.get("id") or ""),
        "user_id": user_id,
        "email": merged.get("otp_email") or payload.get("otp_email") or "",
        "full_name": merged.get("otp_name") or payload.get("otp_name") or merged.get("otp_email") or "",
        "requested_role": merged.get("otp_role") or payload.get("otp_role") or "",
        "hospital_id": merged.get("otp_hospital_id") or payload.get("otp_hospital_id"),
        "hospital_name": merged.get("otp_hospital") or payload.get("otp_hospital") or "",
        "code": code,
        "attempts": int(merged.get("otp_attempts") or payload.get("otp_attempts") or 0),
        "created_at": merged.get("created_at") or payload.get("created_at"),
        "expires_at": merged.get("otp_expires_at") or payload.get("otp_expires_at"),
        "used": False,
        "emailed_to": merged.get("otp_emailed_to") or payload.get("otp_emailed_to") or [],
        "email_sent": bool(merged.get("otp_email_sent") or payload.get("otp_email_sent")),
    }


def _load_persisted() -> dict[str, dict[str, Any]]:
    rows = rest_select(
        "dispatch_alerts",
        {"title": f"eq.{_OTP_TITLE}", "select": "*", "order": "created_at.desc", "limit": "40"},
    )
    found: dict[str, dict[str, Any]] = {}
    now = _now()
    for alert in rows:
        row = _from_alert(alert)
        if not row:
            continue
        exp = _parse_dt(row.get("expires_at"))
        if exp and exp < now:
            continue
        user_id = row["user_id"]
        if user_id not in found:
            found[user_id] = row
    return found


def _mark_used(row: dict[str, Any]) -> None:
    row["used"] = True
    alert_id = row.get("alert_id")
    if not alert_id:
        return
    payload = {
        "otp": row.get("code"),
        "otp_email": row.get("email"),
        "otp_name": row.get("full_name"),
        "otp_role": row.get("requested_role"),
        "otp_hospital_id": row.get("hospital_id"),
        "otp_hospital": row.get("hospital_name"),
        "otp_user_id": row.get("user_id"),
        "otp_expires_at": row.get("expires_at"),
        "otp_emailed_to": row.get("emailed_to") or [],
        "otp_email_sent": row.get("email_sent"),
        "otp_used": True,
        "otp_attempts": row.get("attempts") or 0,
        "kind": "access_otp",
    }
    rest_update("dispatch_alerts", {"id": f"eq.{alert_id}"}, {"payload": payload, "read": True})


def issue_otp(
    user_id: str,
    email: str,
    full_name: str | None,
    requested_role: str,
    hospital_id: int | None = None,
    hospital_name: str | None = None,
) -> dict[str, Any]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = (_now() + timedelta(minutes=15)).isoformat()
    admin_emails = head_staff_emails()
    row = {
        "user_id": user_id,
        "email": email,
        "full_name": full_name or email,
        "requested_role": requested_role,
        "hospital_id": hospital_id,
        "hospital_name": hospital_name or "",
        "code": code,
        "attempts": 0,
        "created_at": _now().isoformat(),
        "expires_at": expires_at,
        "used": False,
        "emailed_to": admin_emails,
        "email_sent": False,
        "email_error": None,
    }
    _otps[user_id] = row
    logger.info("OTP issued for role %s", requested_role)
    who = full_name or email
    alert = push_alert(
        "staff",
        _OTP_TITLE,
        f"{who} ({email}) wants to join as {requested_role}"
        + (f" at {hospital_name}" if hospital_name else "")
        + f". OTP: {code} — share this code with the applicant. Also visible on Staff → OTP codes.",
        extra={
            "kind": "access_otp",
            "otp": code,
            "otp_email": email,
            "otp_name": who,
            "otp_role": requested_role,
            "otp_hospital_id": hospital_id,
            "otp_hospital": hospital_name or "",
            "otp_user_id": user_id,
            "otp_expires_at": expires_at,
            "otp_emailed_to": admin_emails,
            "otp_email_sent": False,
            "otp_used": False,
        },
    )
    row["alert_id"] = alert.get("id")
    out = _public(row)
    return out


def list_active_otps() -> list[dict[str, Any]]:
    now = _now()
    merged: dict[str, dict[str, Any]] = dict(_load_persisted())
    for user_id, row in _otps.items():
        if row.get("used"):
            continue
        exp = _parse_dt(row.get("expires_at"))
        if exp and exp < now:
            continue
        merged[user_id] = dict(row)
    out = list(merged.values())
    out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return out


def verify_otp(user_id: str, code: str) -> dict[str, Any]:
    persisted = _load_persisted()
    row = _otps.get(user_id) or persisted.get(user_id)
    if not row or row.get("used"):
        raise ValueError("No OTP pending. Choose Driver, Doctor, or Staff again.")
    exp = _parse_dt(row.get("expires_at"))
    if exp and exp < _now():
        raise ValueError("OTP expired. Request a new one.")
    row["attempts"] = int(row.get("attempts") or 0) + 1
    if row["attempts"] > 8:
        raise ValueError("Too many attempts. Request a new OTP.")
    entered = "".join(ch for ch in (code or "") if ch.isdigit())
    if entered != str(row.get("code") or ""):
        _otps[user_id] = row
        raise ValueError("Wrong OTP. Ask the admin for the current code.")
    row["used"] = True
    _otps[user_id] = row
    _mark_used(row)
    return row
