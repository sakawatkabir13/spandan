"""Durable, expiring offers. Every capacity writer owns the same schedule lock."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.time import aware, session_time
from app.models.doctor import DoctorProfile, DoctorVerificationStatus
from app.models.operations import WaitlistEntry
from app.models.schedule import ScheduleStatus
from app.models.user import PatientProfile, User
from app.repositories.appointment import appointment_repo
from app.services.notifications import notify


async def expire_offers(db, schedule_id):
    now = datetime.now(timezone.utc)
    for entry in await db.scalars(select(WaitlistEntry).where(WaitlistEntry.schedule_id == schedule_id, WaitlistEntry.status == "offered")):
        if not entry.offer_expires_at or aware(entry.offer_expires_at) <= now:
            entry.status = "expired"
    await db.flush()


async def reserved_places(db, schedule_id, *, except_patient=None):
    await expire_offers(db, schedule_id)
    stmt = select(func.count(WaitlistEntry.id)).where(WaitlistEntry.schedule_id == schedule_id, WaitlistEntry.status == "offered")
    if except_patient:
        stmt = stmt.where(WaitlistEntry.patient_id != except_patient)
    return await db.scalar(stmt) or 0


async def offer_places(db, schedule):
    await db.flush()
    await expire_offers(db, schedule.id)
    now = datetime.now(timezone.utc)
    doctor = await db.get(DoctorProfile, schedule.doctor_id)
    owner = await db.get(User, doctor.user_id)
    unavailable = schedule.status in (ScheduleStatus.CANCELLED, ScheduleStatus.COMPLETED) or session_time(schedule, schedule.end_time) <= now or doctor.verification_status != DoctorVerificationStatus.APPROVED or not owner.is_active or not schedule.chamber.is_active or bool(schedule.booking_close_at and aware(schedule.booking_close_at) <= now)
    if unavailable:
        for entry in await db.scalars(select(WaitlistEntry).where(WaitlistEntry.schedule_id == schedule.id, WaitlistEntry.status.in_(["waiting", "offered"]))):
            entry.status = "unavailable"
            profile = await db.get(PatientProfile, entry.patient_id)
            user = await db.get(User, profile.user_id)
            if user and user.is_active:
                await notify(db, user, "Waitlist session unavailable", f"The session on {schedule.schedule_date} can no longer offer a place. Review your waitlist at {settings.FRONTEND_URL}/dashboard/patient/tools?tab=waitlist and choose another session.", f"waitlist-unavailable:{entry.id}:{entry.created_at.isoformat()}")
        return
    if schedule.status not in (ScheduleStatus.OPEN, ScheduleStatus.FULL) or bool(schedule.booking_open_at and aware(schedule.booking_open_at) > now):
        for entry in await db.scalars(select(WaitlistEntry).where(WaitlistEntry.schedule_id == schedule.id, WaitlistEntry.status == "offered")):
            entry.status = "waiting"
            entry.offer_expires_at = None
        return
    places = schedule.maximum_patients - await appointment_repo.count_active_by_schedule(db, schedule.id) - await reserved_places(db, schedule.id)
    if places <= 0:
        return
    waiting = list(await db.scalars(select(WaitlistEntry).where(WaitlistEntry.schedule_id == schedule.id, WaitlistEntry.status == "waiting").order_by(WaitlistEntry.created_at, WaitlistEntry.id)))
    for entry in waiting:
        profile = await db.get(PatientProfile, entry.patient_id)
        user = await db.get(User, profile.user_id)
        if not user or not user.is_active or await appointment_repo.check_patient_already_booked(db, schedule.id, profile.id):
            entry.status = "cancelled"
            continue
        now = datetime.now(timezone.utc)
        entry.status = "offered"
        entry.offered_at = now
        entry.offer_expires_at = min(now + timedelta(minutes=15), session_time(schedule, schedule.end_time))
        await notify(db, user, "A waitlist place is reserved for you", f"Accept your place for {schedule.schedule_date} before {entry.offer_expires_at.isoformat()}. Open {settings.FRONTEND_URL}/dashboard/patient/tools?tab=waitlist to accept. The offer expires after 15 minutes or when the session ends.", f"waitlist-offer:{entry.id}:{now.isoformat()}")
        places -= 1
        if places <= 0:
            break
