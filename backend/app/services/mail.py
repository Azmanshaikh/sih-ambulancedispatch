"""Best-effort OTP email to the applicant. Uses SMTP when configured."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


def head_staff_emails() -> list[str]:
    return [e.strip() for e in (settings.STAFF_BOOTSTRAP_EMAILS or "").split(",") if e.strip()]


def send_staff_otp_email(
    applicant_email: str,
    applicant_name: str | None,
    requested_role: str,
    code: str,
    hospital_name: str | None = None,
) -> dict:
    recipient = (applicant_email or "").strip()
    if not recipient:
        return {"sent": False, "to": [], "error": "applicant email is empty"}

    host = (settings.SMTP_HOST or "").strip()
    password = (settings.SMTP_PASSWORD or "").strip().replace(" ", "")
    user = (settings.SMTP_USER or "").strip()
    from_addr = (settings.SMTP_FROM or "").strip() or user
    port = int(settings.SMTP_PORT or 587)

    if not host or not password or not user or not from_addr:
        missing = []
        if not host:
            missing.append("SMTP_HOST")
        if not user:
            missing.append("SMTP_USER")
        if not password:
            missing.append("SMTP_PASSWORD")
        if not from_addr:
            missing.append("SMTP_FROM")
        print(
            f"[JEEVAN OTP EMAIL] skipped (missing {', '.join(missing)}). "
            f"Would send {code} to {recipient}"
        )
        return {
            "sent": False,
            "to": [recipient],
            "error": f"smtp not configured (set {', '.join(missing)} in .env)",
        }

    who = applicant_name or applicant_email
    hospital_line = f" Hospital: {hospital_name}." if hospital_name else ""
    msg = EmailMessage()
    msg["Subject"] = f"Your JEEVAN OTP · {requested_role}"
    msg["From"] = from_addr
    msg["To"] = recipient
    msg.set_content(
        f"Hi {who},\n\n"
        f"Your JEEVAN OTP to join as {requested_role} is: {code}.{hospital_line}\n\n"
        "It expires in 15 minutes. Do not share this code.\n"
        "If you did not request this, you can ignore this email.\n"
    )

    try:
        with smtplib.SMTP(host, port, timeout=12) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)
        print(f"[JEEVAN OTP EMAIL] sent {requested_role} OTP to {recipient}")
        return {"sent": True, "to": [recipient], "error": None}
    except Exception as exc:
        print(f"[JEEVAN OTP EMAIL] failed: {exc}")
        return {"sent": False, "to": [recipient], "error": str(exc)}
