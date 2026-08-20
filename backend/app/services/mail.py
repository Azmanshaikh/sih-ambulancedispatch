"""Staff notification helpers (OTP codes are shown to admin in-app, not emailed to applicants)."""

from __future__ import annotations

from app.core.config import settings


def head_staff_emails() -> list[str]:
    raw = settings.MAIN_ADMIN_BOOTSTRAP_EMAILS or settings.STAFF_BOOTSTRAP_EMAILS or ""
    emails = [e.strip() for e in raw.split(",") if e.strip()]
    return emails
