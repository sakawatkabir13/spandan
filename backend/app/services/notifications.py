from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.models.operations import Notification


async def notify(db, user, subject, message, key: Optional[str] = None, scheduled_at=None):
    """Queue minimal operational messages without symptom or clinical details."""
    channels = ["in_app"]
    if settings.email_enabled and user.is_email_verified and not user.email.endswith((".invalid", "@demo.spandan.example.com")):
        channels.append("email")
    if settings.TWILIO_ACCOUNT_SID and user.is_phone_verified:
        channels.append("sms")
    for channel in channels:
        dedup = f"{key}:{channel}" if key else None
        if dedup and await db.scalar(
            select(Notification.id).where(Notification.deduplication_key == dedup)
        ):
            continue
        db.add(
            Notification(
                user_id=user.id,
                channel=channel,
                subject=subject,
                message=message,
                deduplication_key=dedup,
                scheduled_at=scheduled_at or datetime.now(timezone.utc),
            )
        )
