"""Run periodically: reminders, delivery retries and configured retention cleanup."""

import asyncio
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import delete, func, select, text

from app.core.config import settings
from app.core.time import session_time
from app.db.session import async_session_maker
from app.models.appointment import Appointment, AppointmentStatus
from app.models.operations import AccountAction, Notification
from app.models.recommendation import SpecialistRecommendation
from app.models.schedule import Schedule, ScheduleStatus
from app.models.user import PatientProfile, User, UserRole
from app.services.notifications import notify

logger = logging.getLogger(__name__)


def send_email(user, notification):
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = user.email
    message["Subject"] = notification.subject
    message.set_content(notification.message)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_STARTTLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


async def run():
    now = datetime.now(timezone.utc)
    async with async_session_maker() as db:
        if db.bind.dialect.name == "postgresql" and not await db.scalar(
            text("SELECT pg_try_advisory_xact_lock(984322)")
        ):
            return
        appointments = await db.scalars(
            select(Appointment)
            .join(Schedule, Schedule.id == Appointment.schedule_id)
            .where(
                Appointment.appointment_status.in_(
                    [AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED]
                ),
                Schedule.schedule_date
                >= now.astimezone(__import__("zoneinfo").ZoneInfo(settings.APP_TIMEZONE)).date(),
                Schedule.schedule_date
                <= (now + timedelta(days=1))
                .astimezone(__import__("zoneinfo").ZoneInfo(settings.APP_TIMEZONE))
                .date(),
            )
        )
        for appointment in appointments:
            schedule = await db.get(Schedule, appointment.schedule_id)
            start = session_time(schedule, schedule.start_time)
            if now <= start <= now + timedelta(hours=24):
                profile = await db.get(PatientProfile, appointment.patient_id)
                user = await db.get(User, profile.user_id)
                if user.is_active:
                    await notify(
                        db,
                        user,
                        "Appointment reminder",
                        f"Your consultation is on {schedule.schedule_date}, serial {appointment.serial_number}. Please check your queue before travelling.",
                        f"reminder:{appointment.id}",
                    )
        await db.execute(
            delete(SpecialistRecommendation).where(
                SpecialistRecommendation.created_at
                < now - timedelta(days=max(1, settings.SYMPTOM_RETENTION_DAYS))
            )
        )
        await db.execute(
            delete(AccountAction).where(AccountAction.expires_at < now - timedelta(days=1))
        )
        await db.execute(
            delete(Notification).where(Notification.created_at < now - timedelta(days=90))
        )
        upcoming = await db.scalar(
            select(func.count(Schedule.id)).where(
                Schedule.schedule_date >= now.astimezone(ZoneInfo(settings.APP_TIMEZONE)).date(),
                Schedule.status.in_([ScheduleStatus.OPEN, ScheduleStatus.FULL]),
            )
        )
        ai_fallbacks = await db.scalar(
            select(func.count(SpecialistRecommendation.id)).where(
                SpecialistRecommendation.created_at >= now - timedelta(hours=1),
                SpecialistRecommendation.model_identifier == "fallback-general-medicine",
            )
        )
        if not upcoming or ai_fallbacks >= 5:
            for admin in await db.scalars(
                select(User).where(User.role == UserRole.ADMINISTRATOR, User.is_active.is_(True))
            ):
                if not upcoming:
                    await notify(
                        db,
                        admin,
                        "No bookable sessions",
                        "Approved doctors must publish upcoming sessions before patients can book.",
                        f"no-sessions:{admin.id}:{now.date()}",
                    )
                if ai_fallbacks >= 5:
                    await notify(
                        db,
                        admin,
                        "AI provider fallback alert",
                        f"{ai_fallbacks} AI checks used the fallback in the last hour. Check the provider configuration.",
                        f"ai-fallback:{admin.id}:{now:%Y%m%d%H}",
                    )
        await db.commit()
    delivered = 0
    for _ in range(100):
        async with async_session_maker() as db:
            notification = await db.scalar(
                select(Notification)
                .where(
                    Notification.channel.in_(["email", "sms"]),
                    Notification.sent_at.is_(None),
                    Notification.scheduled_at <= now,
                    Notification.attempts < 6,
                )
                .order_by(Notification.scheduled_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not notification:
                break
            user = await db.get(User, notification.user_id)
            if not user or not user.is_active:
                notification.sent_at = now
                await db.commit()
                continue
            if (
                notification.subject == "Spandan account security"
                and notification.created_at.replace(tzinfo=timezone.utc)
                < now - timedelta(minutes=15)
            ):
                notification.sent_at = now
                await db.commit()
                continue
            configured = (
                bool(settings.SMTP_HOST)
                if notification.channel == "email"
                else bool(settings.TWILIO_ACCOUNT_SID)
            )
            if not configured:
                break
            try:
                if notification.channel == "email":
                    await asyncio.to_thread(send_email, user, notification)
                else:
                    async with httpx.AsyncClient(timeout=15) as client:
                        response = await client.post(
                            f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
                            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                            data={
                                "From": settings.TWILIO_FROM,
                                "To": user.phone_number,
                                "Body": notification.message,
                            },
                        )
                        response.raise_for_status()
                notification.sent_at = datetime.now(timezone.utc)
                delivered += 1
            except Exception as exc:
                logger.warning(
                    "notification_delivery_failed id=%s type=%s",
                    notification.id,
                    type(exc).__name__,
                )
                notification.scheduled_at = now + timedelta(
                    minutes=2 ** (notification.attempts + 1)
                )
            notification.attempts += 1
            await db.commit()
    logger.info("notification_worker_completed delivered=%s", delivered)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
