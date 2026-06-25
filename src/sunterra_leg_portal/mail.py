from __future__ import annotations

from email.message import EmailMessage
import os
import smtplib


class MailDeliveryError(RuntimeError):
    pass


def production_smtp_enabled() -> bool:
    return os.environ.get("SUNTERRA_ENV") == "production"


def _smtp_port() -> int:
    configured = os.environ.get("SUNTERRA_SMTP_PORT", "")
    try:
        return int(configured)
    except ValueError as exc:
        raise MailDeliveryError("SUNTERRA_SMTP_PORT must be an integer") from exc


def send_transactional_email(
    *,
    recipient_email: str,
    subject: str,
    body: str,
) -> None:
    host = os.environ.get("SUNTERRA_SMTP_HOST")
    from_email = os.environ.get("SUNTERRA_SMTP_FROM_EMAIL")
    if not host or not from_email:
        raise MailDeliveryError("SMTP configuration is incomplete")

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(host, _smtp_port(), timeout=10) as smtp:
        if os.environ.get("SUNTERRA_SMTP_STARTTLS") == "1":
            smtp.starttls()
        username = os.environ.get("SUNTERRA_SMTP_USERNAME")
        password = os.environ.get("SUNTERRA_SMTP_PASSWORD")
        if username:
            smtp.login(username, password or "")
        smtp.send_message(message)
