"""Shared operational mutations with caller-owned transaction support."""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from app.core.exceptions import SpandanException, create_success_response
from app.models.appointment import AppointmentStatus
from app.models.audit import AuditLog
from app.models.doctor import AssistantAssignment, DoctorProfile
from app.models.operations import WaitlistEntry
from app.models.schedule import ScheduleStatus
from app.models.user import User, UserRole
from app.repositories.user import patient_repo
from app.services.permissions import require_doctor_access


class RescheduleBody(BaseModel):
    schedule_id: UUID


def record(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


async def update_assistant_permissions(db, user, assignment_id, changes, *, commit=True):
    if user.role not in (UserRole.DOCTOR, UserRole.ADMINISTRATOR):
        raise SpandanException(
            "FORBIDDEN", "Only doctors and administrators may manage assistants.", 403
        )
    assignment = await db.scalar(
        select(AssistantAssignment).where(AssistantAssignment.id == assignment_id).with_for_update()
    )
    if not assignment:
        raise SpandanException("NOT_FOUND", "Assistant assignment not found.", 404)
    require_doctor_access(user, assignment.doctor_id, "can_manage_appointments")
    for key in ("is_active", "can_manage_schedules", "can_manage_appointments", "can_update_queue"):
        setattr(assignment, key, changes[key])
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="assistant.permissions_updated",
            entity_type="assistant_assignment",
            entity_id=str(assignment.id),
            metadata_json={"changed_fields": sorted(changes)},
        )
    )
    if commit:
        await db.commit()
    else:
        await db.flush()
    return assignment


async def update_user_status(db, user, user_id, is_active, *, commit=True):
    if user.role != UserRole.ADMINISTRATOR:
        raise SpandanException("FORBIDDEN", "Administrator access is required.", 403)
    target = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not target:
        raise SpandanException("NOT_FOUND", "Account not found.", 404)
    if target.role == UserRole.ADMINISTRATOR and not is_active:
        raise SpandanException(
            "FORBIDDEN", "Administrator accounts cannot be deactivated here.", 403
        )
    previous = target.is_active
    target.is_active = is_active
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="user.status_updated",
            entity_type="user",
            entity_id=str(target.id),
            metadata_json={"previous_is_active": previous, "new_is_active": is_active},
        )
    )
    if commit:
        await db.commit()
    else:
        await db.flush()
    return target


async def join_waitlist(schedule_id: UUID, user, db, *, commit: bool = True):
    if user.role != UserRole.PATIENT:
        raise SpandanException("FORBIDDEN", "Patient access is required.", 403)
    from app.models.doctor import DoctorVerificationStatus
    from app.repositories.appointment import appointment_repo
    from app.repositories.schedule import schedule_repo

    schedule = await schedule_repo.get_by_id_with_queue(db, schedule_id, lock=True)
    if not schedule or schedule.status not in (ScheduleStatus.OPEN, ScheduleStatus.FULL):
        raise SpandanException("SCHEDULE_CLOSED", "This session is unavailable.")
    from app.core.time import session_time

    doctor = await db.get(DoctorProfile, schedule.doctor_id)
    owner = await db.get(User, doctor.user_id)
    if (
        session_time(schedule, schedule.end_time) <= datetime.now(timezone.utc)
        or doctor.verification_status != DoctorVerificationStatus.APPROVED
        or (not owner.is_active)
        or (not schedule.chamber.is_active)
    ):
        raise SpandanException("SCHEDULE_CLOSED", "This session is unavailable.")
    profile = await patient_repo.get_by_user_id(db, user.id)
    if await appointment_repo.check_patient_already_booked(db, schedule_id, profile.id):
        raise SpandanException("CONFLICT", "You already have a booking for this session.", 409)
    entry = await db.scalar(
        select(WaitlistEntry).where(
            WaitlistEntry.schedule_id == schedule_id, WaitlistEntry.patient_id == profile.id
        )
    )
    if not entry:
        entry = WaitlistEntry(schedule_id=schedule_id, patient_id=profile.id)
        db.add(entry)
    entry.status = "waiting"
    if commit:
        await db.commit()
    else:
        await db.flush()
    return create_success_response(
        "Joined the cancellation waitlist. You will be notified when space becomes available.",
        record(entry),
    )


async def leave_waitlist(id: UUID, user, db, *, commit: bool = True):
    if user.role != UserRole.PATIENT:
        raise SpandanException("FORBIDDEN", "Patient access is required.", 403)
    profile = await patient_repo.get_by_user_id(db, user.id)
    row = await db.get(WaitlistEntry, id)
    if not row or row.patient_id != profile.id:
        raise SpandanException("NOT_FOUND", "Waitlist entry not found.", 404)
    row.status = "cancelled"
    if commit:
        await db.commit()
    else:
        await db.flush()
    return create_success_response("Left the waitlist.")


async def reschedule(id: UUID, request: RescheduleBody, user, db, *, commit: bool = True):
    from app.core.time import session_time
    from app.models.operations import Payment
    from app.repositories.appointment import appointment_repo
    from app.repositories.schedule import schedule_repo
    from app.schemas.appointment import AppointmentCreate, AppointmentResponse
    from app.services.appointment import appointment_service

    original = await appointment_repo.get_by_id_with_details(db, id)
    if not original:
        raise SpandanException("NOT_FOUND", "Appointment not found.", 404)
    if user.role == UserRole.PATIENT:
        profile = await patient_repo.get_by_user_id(db, user.id)
        if not profile or profile.id != original.patient_id:
            raise SpandanException("FORBIDDEN", "This is not your appointment.", 403)
    else:
        require_doctor_access(user, original.doctor_id, "can_manage_appointments")
    if original.schedule_id == request.schedule_id:
        raise SpandanException("CONFLICT", "Choose a different session.", 409)
    for schedule_id in sorted((original.schedule_id, request.schedule_id), key=str):
        await schedule_repo.get_by_id_with_queue(db, schedule_id, lock=True)
    await db.refresh(original)
    if original.appointment_status not in (AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED):
        raise SpandanException(
            "CONFLICT", "Only booked or confirmed visits may be rescheduled.", 409
        )
    target = await schedule_repo.get_by_id_with_queue(db, request.schedule_id)
    if not target or target.doctor_id != original.doctor_id:
        raise SpandanException("CONFLICT", "Choose another session with the same doctor.", 409)
    payment = await db.scalar(
        select(Payment).where(Payment.appointment_id == original.id).with_for_update()
    )
    if (
        payment
        and payment.status == "paid"
        and (target.chamber.consultation_fee != original.chamber.consultation_fee)
    ):
        raise SpandanException(
            "CONFLICT",
            "Paid appointments can only move to a session with the same fee. Contact the chamber for a refund.",
            409,
        )
    original.appointment_status = AppointmentStatus.CANCELLED
    original.cancelled_at = datetime.now(timezone.utc)
    original.cancellation_reason = "Rescheduled"
    old_schedule = await schedule_repo.get_by_id_with_queue(db, original.schedule_id)
    if old_schedule.status == ScheduleStatus.FULL and session_time(
        old_schedule, old_schedule.end_time
    ) > datetime.now(timezone.utc):
        old_schedule.status = ScheduleStatus.OPEN
    await db.flush()
    new = await appointment_service.book_appointment(
        db,
        user,
        AppointmentCreate(
            schedule_id=target.id,
            patient_id=original.patient_id,
            dependent_id=original.dependent_id,
            patient_note=original.patient_note,
            consultation_mode=original.consultation_mode,
            booking_source=original.booking_source,
        ),
        commit=False,
    )
    if payment:
        if payment.status != "paid":
            raise SpandanException(
                "CONFLICT", "Finish or cancel the pending payment before rescheduling.", 409
            )
        payment.appointment_id = new.id
    await appointment_service.notify_waitlist(db, old_schedule)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="appointment.rescheduled",
            entity_type="appointment",
            entity_id=str(new.id),
            metadata_json={"previous_appointment_id": str(original.id)},
        )
    )
    if commit:
        await db.commit()
    else:
        await db.flush()
    return create_success_response(
        "Appointment rescheduled.", AppointmentResponse.model_validate(new)
    )
