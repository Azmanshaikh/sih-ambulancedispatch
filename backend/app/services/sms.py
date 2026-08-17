"""Outbound SMS / WhatsApp for corridor alerts. Falls back to an in-memory demo log."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

_log: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _settings():
    from app.core.config import settings

    return settings


def list_sms(limit: int = 40) -> list[dict[str, Any]]:
    return list(_log[:limit])


def _via_msg91(phone: str, body: str) -> tuple[str, str]:
    settings = _settings()
    key = (settings.MSG91_AUTH_KEY or "").strip()
    if not key:
        return "", ""
    sender = (settings.MSG91_SENDER or "JEEVAN").strip() or "JEEVAN"
    mobiles = phone.replace("+", "").replace(" ", "")
    url = "https://api.msg91.com/api/sendhttp.php?" + urlencode(
        {
            "authkey": key,
            "mobiles": mobiles,
            "message": body,
            "sender": sender[:6],
            "route": "4",
            "country": "91",
        }
    )
    try:
        res = requests.get(url, timeout=8)
        if res.ok:
            return "msg91", "sent"
        return "msg91", f"failed:{res.status_code}"
    except Exception as exc:
        return "msg91", f"failed:{exc}"


def _via_twilio(phone: str, body: str, whatsapp: bool) -> tuple[str, str]:
    settings = _settings()
    sid = (settings.TWILIO_ACCOUNT_SID or "").strip()
    token = (settings.TWILIO_AUTH_TOKEN or "").strip()
    if not sid or not token:
        return "", ""
    from_sms = (settings.TWILIO_FROM or "").strip()
    from_wa = (settings.TWILIO_WHATSAPP_FROM or "").strip()
    if whatsapp and from_wa:
        src = from_wa if from_wa.startswith("whatsapp:") else f"whatsapp:{from_wa}"
        dest = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        provider = "twilio-whatsapp"
    elif from_sms:
        src = from_sms
        dest = phone
        provider = "twilio"
    else:
        return "", ""
    try:
        res = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"From": src, "To": dest, "Body": body},
            timeout=8,
        )
        if res.ok:
            return provider, "sent"
        return provider, f"failed:{res.status_code}"
    except Exception as exc:
        return provider, f"failed:{exc}"


def send_sms(
    phone: str,
    body: str,
    *,
    post_id: str | None = None,
    post_name: str | None = None,
    mission_id: str | None = None,
    ambulance_id: str | None = None,
    channel: str = "sms",
) -> dict[str, Any]:
    settings = _settings()
    provider = "demo"
    status = "demo"
    if (settings.MSG91_AUTH_KEY or "").strip():
        provider, status = _via_msg91(phone, body)
    elif (settings.TWILIO_ACCOUNT_SID or "").strip():
        provider, status = _via_twilio(phone, body, whatsapp=channel == "whatsapp")
    if not provider:
        provider, status = "demo", "demo"

    row = {
        "id": str(uuid.uuid4()),
        "phone": phone,
        "body": body,
        "status": status,
        "provider": provider,
        "channel": "whatsapp" if channel == "whatsapp" else "sms",
        "post_id": post_id,
        "post_name": post_name,
        "mission_id": mission_id,
        "ambulance_id": ambulance_id,
        "created_at": _now(),
    }
    _log.insert(0, row)
    del _log[80:]
    return row
