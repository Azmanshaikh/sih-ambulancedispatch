"""Best-effort email to head staff. Uses SMTP when configured."""

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
) -> dict:
    recipients = head_staff_emails()
    if not recipients:
        return {"sent": False, "to": [], "error": "STAFF_BOOTSTRAP_EMAILS is empty"}

    host = (settings.SMTP_HOST or "").strip()
    password = (settings.SMTP_PASSWORD or "").strip()
    user = (settings.SMTP_USER or "").strip() or (recipients[0] if host else "")
    from_addr = (settings.SMTP_FROM or "").strip() or user or recipients[0]
    port = int(settings.SMTP_PORT or 587)

    if not host or not password or not user:
        print(f"[JEEVAN OTP EMAIL] skipped (set SMTP_HOST / SMTP_USER / SMTP_PASSWORD). Would send {code} to {recipients}")
        return {"sent": False, "to": recipients, "error": "smtp not configured"}

    who = applicant_name or applicant_email
    msg = EmailMessage()
    msg["Subject"] = f"JEEVAN access OTP · {requested_role}"
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.set_content(
        f"{who} ({applicant_email}) wants to join JEEVAN as {requested_role}.\n\n"
        f"OTP: {code}\n\n"
        "Give this code only if you know them. It expires in 15 minutes.\n"
        "You can also see pending codes under Staff → OTP codes."
    )

    try:
        with smtplib.SMTP(host, port, timeout=12) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)
        print(f"[JEEVAN OTP EMAIL] sent {requested_role} OTP for {applicant_email} to {recipients}")
        return {"sent": True, "to": recipients, "error": None}
    except Exception as exc:
        print(f"[JEEVAN OTP EMAIL] failed: {exc}")
        return {"sent": False, "to": recipients, "error": str(exc)}
