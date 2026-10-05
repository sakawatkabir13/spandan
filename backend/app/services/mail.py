"""SMTP delivery shared by immediate security codes and the notification worker."""

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def send_email(recipient: str, subject: str, body: str):
    if not settings.email_enabled or recipient.endswith((".invalid", "@demo.spandan.example.com")):
        raise ValueError("Email delivery is unavailable for this recipient")
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    context = ssl.create_default_context()
    connection = (
        smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, context=context)
        if settings.SMTP_SSL
        else smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
    )
    with connection as smtp:
        if settings.SMTP_STARTTLS:
            smtp.starttls(context=context)
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)
