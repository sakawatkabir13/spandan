from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.core.exceptions import SpandanException, create_success_response
from app.db.session import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit import AuditLog
from app.models.doctor import DoctorProfile
from app.models.operations import (
    AvailabilityException,
    Dependent,
    Notification,
    Payment,
    PrivacyRequest,
    WaitlistEntry,
)
from app.models.schedule import Schedule, ScheduleStatus
from app.models.user import PatientProfile, User, UserRole
from app.repositories.user import patient_repo
from app.services.permissions import require_doctor_access

router = APIRouter(tags=["Chamber operations"])


@router.get("/system/status")
async def system_status(user=Depends(require_roles(UserRole.ADMINISTRATOR)), db=Depends(get_db)):
    from app.core.config import settings
    from app.models.recommendation import SpecialistRecommendation
    from app.models.schedule import QueueState

    now = datetime.now(timezone.utc)
    ai_where = SpecialistRecommendation.created_at >= now - timedelta(hours=24)
    total = await db.scalar(
        select(func.count(SpecialistRecommendation.id)).where(
            ai_where, SpecialistRecommendation.model_identifier != "rule-based-emergency-engine"
        )
    )
    fallback = await db.scalar(
        select(func.count(SpecialistRecommendation.id)).where(
            ai_where, SpecialistRecommendation.model_identifier == "fallback-general-medicine"
        )
    )
    overdue = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.channel.in_(["sms", "email"]),
            Notification.sent_at.is_(None),
            Notification.created_at < now - timedelta(hours=1),
        )
    )
    stale = await db.scalar(
        select(func.count(QueueState.id))
        .join(Schedule, Schedule.id == QueueState.schedule_id)
        .where(
            Schedule.schedule_date
            == now.astimezone(__import__("zoneinfo").ZoneInfo(settings.APP_TIMEZONE)).date(),
            QueueState.current_serial > 0,
            QueueState.updated_at < now - timedelta(hours=1),
        )
    )
    return create_success_response(
        "Operational service status.",
        {
            "ai_model": settings.GROQ_MODEL,
            "ai_requests_24h": total,
            "ai_fallbacks_24h": fallback,
            "delivery_jobs_overdue": overdue,
            "stale_active_queues": stale,
            "external_delivery_enabled": bool(settings.email_enabled or settings.TWILIO_ACCOUNT_SID),
            "offsite_backups_configured": bool(settings.S3_BACKUP_BUCKET),
        },
    )


@router.get("/service-capabilities")
async def capabilities():
    from app.core.config import settings

    return create_success_response(
        "Service capabilities.",
        {
            "demo_mode": settings.DEMO_MODE,
            "payment_mode": settings.STRIPE_MODE,
            "email": settings.email_enabled,
            "sms": bool(
                settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM
            ),
            "online_payments": settings.online_payments_enabled,
            "video": bool(settings.VIDEO_BASE_URL),
            "operator": settings.OPERATOR_NAME,
            "contact": settings.OPERATOR_EMAIL,
            "symptom_retention_days": settings.SYMPTOM_RETENTION_DAYS,
        },
    )


@router.get("/appointments/{id}/video")
async def video_room(id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    import secrets
    from urllib.parse import urlparse

    from app.api.routes.payments import authorize
    from app.core.config import settings
    from app.core.time import session_time
    from app.repositories.schedule import schedule_repo

    appointment = await authorize(db, user, id)
    schedule = await schedule_repo.get_by_id_with_queue(db, appointment.schedule_id, lock=True)
    await db.refresh(appointment)
    if appointment.consultation_mode != "video" or appointment.appointment_status in (
        AppointmentStatus.CANCELLED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.ABSENT,
    ):
        raise SpandanException("CONFLICT", "No active video consultation for this booking.", 409)
    if urlparse(settings.VIDEO_BASE_URL).scheme != "https":
        raise SpandanException("VIDEO_UNAVAILABLE", "Video consultation is not configured.", 503)
    now = datetime.now(timezone.utc)
    if (
        not session_time(schedule, schedule.start_time) - timedelta(minutes=15)
        <= now
        <= session_time(schedule, schedule.end_time) + timedelta(hours=1)
    ):
        raise SpandanException(
            "CONFLICT", "The consultation room opens 15 minutes before the session.", 409
        )
    if not appointment.video_room:
        appointment.video_room = secrets.token_urlsafe(32)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="video.room_accessed",
            entity_type="appointment",
            entity_id=str(id),
        )
    )
    await db.commit()
    return create_success_response(
        "Private consultation room.",
        {"url": settings.VIDEO_BASE_URL.rstrip("/") + "/" + appointment.video_room},
    )


@router.get("/appointments/{id}/fhir")
async def export_fhir(id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    from app.api.routes.payments import authorize
    from app.core.time import session_time

    appointment = await authorize(db, user, id)
    status = {
        "booked": "booked",
        "confirmed": "booked",
        "checked_in": "checked-in",
        "waiting": "arrived",
        "in_consultation": "arrived",
        "completed": "fulfilled",
        "cancelled": "cancelled",
        "absent": "noshow",
        "skipped": "pending",
    }[appointment.appointment_status.value]
    return create_success_response(
        "FHIR R4 Appointment export.",
        {
            "resourceType": "Appointment",
            "id": str(id),
            "status": status,
            "start": session_time(
                appointment.schedule, appointment.schedule.start_time
            ).isoformat(),
            "end": session_time(appointment.schedule, appointment.schedule.end_time).isoformat(),
            "participant": [
                {
                    "actor": {
                        "reference": f"Patient/{appointment.dependent_id or appointment.patient_id}",
                        "display": appointment.attendee_name,
                    },
                    "status": "accepted",
                },
                {
                    "actor": {
                        "reference": f"Practitioner/{appointment.doctor_id}",
                        "display": appointment.doctor.full_name,
                    },
                    "status": "accepted",
                },
            ],
            "description": "Video consultation"
            if appointment.consultation_mode == "video"
            else "Chamber consultation",
        },
    )


def record(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


class DependentRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    relationship_name: str = Field(min_length=2, max_length=50)
    date_of_birth: str | None = None


@router.get("/dependents")
async def list_dependents(user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    profile = await patient_repo.get_by_user_id(db, user.id)
    rows = await db.scalars(
        select(Dependent).where(Dependent.patient_id == profile.id, Dependent.is_active.is_(True))
    )
    return create_success_response("Family members fetched.", [record(row) for row in rows])


@router.post("/dependents", status_code=201)
async def create_dependent(
    request: DependentRequest, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)
):
    from datetime import date

    profile = await patient_repo.get_by_user_id(db, user.id)
    try:
        dob = date.fromisoformat(request.date_of_birth) if request.date_of_birth else None
    except ValueError:
        raise SpandanException("VALIDATION_ERROR", "Use YYYY-MM-DD for date of birth.")
    if dob and dob > date.today():
        raise SpandanException("VALIDATION_ERROR", "Date of birth cannot be in the future.")
    row = Dependent(
        patient_id=profile.id,
        full_name=request.full_name,
        relationship_name=request.relationship_name,
        date_of_birth=dob,
    )
    db.add(row)
    await db.commit()
    return create_success_response("Family member added.", record(row))


@router.delete("/dependents/{id}")
async def archive_dependent(
    id: UUID, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)
):
    profile = await patient_repo.get_by_user_id(db, user.id)
    row = await db.get(Dependent, id)
    if not row or row.patient_id != profile.id:
        raise SpandanException("NOT_FOUND", "Family member not found.", 404)
    row.is_active = False
    await db.commit()
    return create_success_response("Family member archived.")


@router.get("/notifications")
async def list_notifications(
    skip: int = Query(0, ge=0), user=Depends(get_current_active_user), db=Depends(get_db)
):
    rows = await db.scalars(
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.channel == "in_app",
            Notification.scheduled_at <= datetime.now(timezone.utc),
        )
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(50)
    )
    return create_success_response("Notifications fetched.", [record(row) for row in rows])


@router.post("/notifications/{id}/read")
async def read_notification(id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    row = await db.get(Notification, id)
    if not row or row.user_id != user.id or row.channel != "in_app":
        raise SpandanException("NOT_FOUND", "Notification not found.", 404)
    row.read_at = datetime.now(timezone.utc)
    await db.commit()
    return create_success_response("Notification marked read.")


@router.post("/waitlist/{schedule_id}", status_code=201)
async def join_waitlist(
    schedule_id: UUID, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)
):
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
        or not owner.is_active
        or not schedule.chamber.is_active
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
    await db.commit()
    return create_success_response(
        "Joined the cancellation waitlist. You will be notified when space becomes available.",
        record(entry),
    )


@router.get("/waitlist")
async def my_waitlist(user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    profile = await patient_repo.get_by_user_id(db, user.id)
    rows = await db.scalars(
        select(WaitlistEntry).where(
            WaitlistEntry.patient_id == profile.id, WaitlistEntry.status == "waiting"
        )
    )
    return create_success_response("Waitlist fetched.", [record(row) for row in rows])


@router.delete("/waitlist/{id}")
async def leave_waitlist(
    id: UUID, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)
):
    profile = await patient_repo.get_by_user_id(db, user.id)
    row = await db.get(WaitlistEntry, id)
    if not row or row.patient_id != profile.id:
        raise SpandanException("NOT_FOUND", "Waitlist entry not found.", 404)
    row.status = "cancelled"
    await db.commit()
    return create_success_response("Left the waitlist.")


class PrivacyRequestBody(BaseModel):
    kind: str = Field(pattern="^(access|deletion)$")


@router.post("/privacy/requests", status_code=201)
async def request_privacy(
    request: PrivacyRequestBody, user=Depends(get_current_active_user), db=Depends(get_db)
):
    existing = await db.scalar(
        select(PrivacyRequest).where(
            PrivacyRequest.user_id == user.id,
            PrivacyRequest.kind == request.kind,
            PrivacyRequest.status == "pending",
        )
    )
    if existing:
        return create_success_response("Your request is already pending.", record(existing))
    row = PrivacyRequest(user_id=user.id, kind=request.kind)
    db.add(row)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="privacy.requested",
            entity_type="user",
            entity_id=str(user.id),
            metadata_json={"kind": request.kind},
        )
    )
    await db.commit()
    return create_success_response("Privacy request submitted.", record(row))


@router.get("/privacy/requests")
async def privacy_requests(user=Depends(get_current_active_user), db=Depends(get_db)):
    stmt = select(PrivacyRequest).order_by(PrivacyRequest.created_at.desc()).limit(100)
    if user.role != UserRole.ADMINISTRATOR:
        stmt = stmt.where(PrivacyRequest.user_id == user.id)
    return create_success_response(
        "Privacy requests fetched.", [record(row) for row in await db.scalars(stmt)]
    )


@router.get("/privacy/export")
async def export_personal_data(user=Depends(get_current_active_user), db=Depends(get_db)):
    from app.models.recommendation import SpecialistRecommendation

    data = {
        "account": {
            "email": user.email,
            "phone_number": user.phone_number,
            "name": user.full_name,
            "created_at": user.created_at,
        }
    }
    profile = await patient_repo.get_by_user_id(db, user.id)
    if profile:
        data["profile"] = record(profile)
        data["appointments"] = [
            {key: value for key, value in record(row).items() if key != "video_room"}
            for row in await db.scalars(
                select(Appointment).where(Appointment.patient_id == profile.id)
            )
        ]
        data["recommendations"] = [
            record(row)
            for row in await db.scalars(
                select(SpecialistRecommendation).where(
                    SpecialistRecommendation.patient_id == profile.id
                )
            )
        ]
        for name, model in (("dependents", Dependent), ("waitlist", WaitlistEntry)):
            data[name] = [record(row) for row in await db.scalars(select(model).where(model.patient_id == profile.id))]
        data["payments"] = [record(row) for row in await db.scalars(
            select(Payment).join(Appointment, Appointment.id == Payment.appointment_id)
            .where(Appointment.patient_id == profile.id)
        )]
    data["notifications"] = [
        record(row) for row in await db.scalars(
            select(Notification).where(Notification.user_id == user.id, Notification.channel == "in_app")
        )
    ]
    data["privacy_requests"] = [
        record(row) for row in await db.scalars(select(PrivacyRequest).where(PrivacyRequest.user_id == user.id))
    ]
    return create_success_response("Personal data export.", data)


@router.post("/privacy/requests/{id}/resolve")
async def resolve_privacy(
    id: UUID, user=Depends(require_roles(UserRole.ADMINISTRATOR)), db=Depends(get_db)
):
    from app.models.recommendation import SpecialistRecommendation

    row = await db.scalar(select(PrivacyRequest).where(PrivacyRequest.id == id).with_for_update())
    if not row or row.status != "pending":
        raise SpandanException("NOT_FOUND", "Pending privacy request not found.", 404)
    target = await db.get(User, row.user_id)
    if row.kind == "deletion":
        if target.role == UserRole.ADMINISTRATOR:
            raise SpandanException(
                "FORBIDDEN", "Administrator deletion requires an operator review.", 403
            )
        if target.role != UserRole.PATIENT:
            raise SpandanException(
                "CONFLICT",
                "Staff deletion requires an operator review of chamber records. Contact support.",
                409,
            )
        profile = await patient_repo.get_by_user_id(db, target.id)
        if profile:
            await db.execute(
                select(PatientProfile.id).where(PatientProfile.id == profile.id).with_for_update()
            )
            active = await db.scalar(
                select(Appointment.id)
                .where(
                    Appointment.patient_id == profile.id,
                    Appointment.appointment_status.notin_(
                        [
                            AppointmentStatus.COMPLETED,
                            AppointmentStatus.CANCELLED,
                            AppointmentStatus.ABSENT,
                        ]
                    ),
                )
                .limit(1)
            )
            if active:
                raise SpandanException(
                    "CONFLICT", "Resolve active appointments before anonymizing this account.", 409
                )
            for rec in await db.scalars(
                select(SpecialistRecommendation).where(
                    SpecialistRecommendation.patient_id == profile.id
                )
            ):
                await db.delete(rec)
            profile.full_name = "Deleted patient"
            from app.services.profile_photo import remove_profile_photo

            await remove_profile_photo(profile.profile_photo_url)
            profile.date_of_birth = profile.address = profile.gender = profile.emergency_contact = (
                profile.profile_photo_url
            ) = None
            for dependent in await db.scalars(
                select(Dependent).where(Dependent.patient_id == profile.id)
            ):
                dependent.full_name = "Deleted dependent"
                dependent.date_of_birth = None
                dependent.is_active = False
                dependent.relationship_name = "Deleted"
            for appointment in await db.scalars(
                select(Appointment).where(Appointment.patient_id == profile.id)
            ):
                appointment.patient_note = appointment.cancellation_reason = (
                    appointment.video_room
                ) = None
            for entry in await db.scalars(
                select(WaitlistEntry).where(WaitlistEntry.patient_id == profile.id)
            ):
                await db.delete(entry)
        from app.models.operations import AccountAction

        for action in await db.scalars(
            select(AccountAction).where(AccountAction.user_id == target.id)
        ):
            await db.delete(action)
        target.email = f"deleted-{target.id}@deleted.invalid"
        target.phone_number = None
        target.display_name = "Deleted user"
        target.is_active = False
        target.token_version += 1
        target.mfa_secret = None
        target.mfa_enabled = target.is_email_verified = target.is_phone_verified = False
        for notification in await db.scalars(
            select(Notification).where(Notification.user_id == target.id)
        ):
            await db.delete(notification)
    row.status = "resolved"
    row.resolved_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="privacy.resolved",
            entity_type="privacy_request",
            entity_id=str(row.id),
            metadata_json={"kind": row.kind},
        )
    )
    await db.commit()
    return create_success_response(
        "Request resolved. Appointment transaction records remain subject to retention obligations."
    )


@router.get("/analytics")
async def analytics(
    days: int = Query(30, ge=1, le=365),
    user=Depends(require_roles(UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR)),
    db=Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(Appointment).where(Appointment.created_at >= cutoff)
    doctor_ids = None
    if user.role == UserRole.DOCTOR:
        doctor_ids = [user.doctor_profile.id]
    elif user.role == UserRole.ASSISTANT:
        doctor_ids = [
            a.doctor_id
            for a in user.assistant_assignments
            if a.is_active and (a.can_manage_appointments or a.can_update_queue)
        ]
    if doctor_ids is not None:
        stmt = stmt.where(Appointment.doctor_id.in_(doctor_ids))
    rows = list((await db.scalars(stmt)).all())
    counts = {
        status.value: sum(a.appointment_status == status for a in rows)
        for status in AppointmentStatus
    }
    durations = [
        (a.actual_consultation_completed_at - a.actual_consultation_started_at).total_seconds() / 60
        for a in rows
        if a.actual_consultation_started_at and a.actual_consultation_completed_at
    ]
    schedule_query = select(func.count(Schedule.id)).where(
        Schedule.schedule_date >= datetime.now(timezone.utc).date(),
        Schedule.status.in_([ScheduleStatus.OPEN, ScheduleStatus.FULL]),
    )
    if doctor_ids is not None:
        schedule_query = schedule_query.where(Schedule.doctor_id.in_(doctor_ids))
    return create_success_response(
        "Operational analytics.",
        {
            "days": days,
            "total_bookings": len(rows),
            "status_counts": counts,
            "average_consultation_minutes": round(sum(durations) / len(durations), 1)
            if durations
            else None,
            "upcoming_sessions": await db.scalar(schedule_query),
            "attendance_rate": round(100 * counts["completed"] / len(rows), 1) if rows else 0,
            "waiting_patients": sum(
                a.appointment_status
                in (
                    AppointmentStatus.BOOKED,
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.CHECKED_IN,
                    AppointmentStatus.WAITING,
                )
                for a in rows
            ),
            "chamber_workload": {
                str(chamber_id): sum(a.chamber_id == chamber_id for a in rows)
                for chamber_id in {a.chamber_id for a in rows}
            },
        },
    )


class ExceptionBody(BaseModel):
    exception_date: str
    reason: str = Field(min_length=2, max_length=200)


class IntakeBody(BaseModel):
    schedule_id: UUID
    full_name: str = Field(min_length=2, max_length=100)
    phone_number: str
    email: str | None = None


@router.post("/appointments/intake", status_code=201)
async def intake_patient(
    request: IntakeBody,
    user=Depends(require_roles(UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR)),
    db=Depends(get_db),
):
    import secrets
    import uuid

    from pydantic import EmailStr, TypeAdapter

    from app.core.security import get_password_hash
    from app.models.appointment import BookingSource
    from app.repositories.schedule import schedule_repo
    from app.repositories.user import user_repo
    from app.schemas.appointment import AppointmentCreate, AppointmentResponse
    from app.schemas.auth import clean_and_validate_phone
    from app.services.appointment import appointment_service

    schedule = await schedule_repo.get_by_id_with_queue(db, request.schedule_id, lock=True)
    if not schedule:
        raise SpandanException("NOT_FOUND", "Session not found.", 404)
    require_doctor_access(user, schedule.doctor_id, "can_manage_appointments")
    try:
        phone = clean_and_validate_phone(request.phone_number)
    except ValueError as exc:
        raise SpandanException("VALIDATION_ERROR", str(exc))
    existing = await user_repo.get_by_phone(db, phone)
    if existing:
        raise SpandanException(
            "CONFLICT",
            "This phone already belongs to an account. Use the registered-patient booking form.",
            409,
        )
    email = request.email or f"walkin-{uuid.uuid4().hex}@accounts.spandan.cuetinsights.dev"
    try:
        email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    except ValueError:
        raise SpandanException("VALIDATION_ERROR", "Enter a valid email address.")
    if await user_repo.get_by_email(db, email):
        raise SpandanException("CONFLICT", "Email already belongs to an account.", 409)
    patient_user = User(
        email=email,
        phone_number=phone,
        role=UserRole.PATIENT,
        password_hash=get_password_hash(secrets.token_urlsafe(32)),
        is_active=True,
    )
    db.add(patient_user)
    await db.flush()
    profile = PatientProfile(user_id=patient_user.id, full_name=request.full_name)
    db.add(profile)
    await db.flush()
    appointment = await appointment_service.book_appointment(
        db,
        user,
        AppointmentCreate(
            schedule_id=schedule.id, patient_id=profile.id, booking_source=BookingSource.WALK_IN
        ),
        commit=False,
    )
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="patient.intake",
            entity_type="patient",
            entity_id=str(profile.id),
        )
    )
    await db.commit()
    return create_success_response(
        "Walk-in patient registered and booked. No shared or default login password was created.",
        AppointmentResponse.model_validate(appointment),
    )


class RescheduleBody(BaseModel):
    schedule_id: UUID


@router.post("/appointments/{id}/reschedule", status_code=201)
async def reschedule(
    id: UUID, request: RescheduleBody, user=Depends(get_current_active_user), db=Depends(get_db)
):
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
        and target.chamber.consultation_fee != original.chamber.consultation_fee
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
    await db.commit()
    return create_success_response(
        "Appointment rescheduled.", AppointmentResponse.model_validate(new)
    )


@router.get("/availability/exceptions")
async def list_exceptions(user=Depends(require_roles(UserRole.DOCTOR)), db=Depends(get_db)):
    return create_success_response(
        "Availability exceptions.",
        [
            record(row)
            for row in await db.scalars(
                select(AvailabilityException).where(
                    AvailabilityException.doctor_id == user.doctor_profile.id
                )
            )
        ],
    )


@router.post("/availability/exceptions", status_code=201)
async def add_exception(
    request: ExceptionBody, user=Depends(require_roles(UserRole.DOCTOR)), db=Depends(get_db)
):
    from datetime import date

    from app.models.doctor import DoctorProfile

    doctor_id = user.doctor_profile.id
    try:
        exception_date = date.fromisoformat(request.exception_date)
    except ValueError:
        raise SpandanException("VALIDATION_ERROR", "Use YYYY-MM-DD for closure date.")
    await db.execute(
        select(DoctorProfile.id).where(DoctorProfile.id == doctor_id).with_for_update()
    )
    overlapping = await db.scalar(
        select(Schedule.id)
        .where(
            Schedule.doctor_id == doctor_id,
            Schedule.schedule_date == exception_date,
            Schedule.status.notin_([ScheduleStatus.CANCELLED, ScheduleStatus.COMPLETED]),
        )
        .limit(1)
    )
    if overlapping:
        raise SpandanException(
            "CONFLICT",
            "Cancel or complete existing sessions on this date before adding a closure.",
            409,
        )
    existing = await db.scalar(
        select(AvailabilityException).where(
            AvailabilityException.doctor_id == doctor_id,
            AvailabilityException.exception_date == exception_date,
        )
    )
    if existing:
        raise SpandanException("CONFLICT", "This date is already closed.", 409)
    row = AvailabilityException(
        doctor_id=doctor_id, exception_date=exception_date, reason=request.reason
    )
    db.add(row)
    await db.commit()
    return create_success_response("Closure added.", record(row))


@router.delete("/availability/exceptions/{id}")
async def remove_exception(
    id: UUID, user=Depends(require_roles(UserRole.DOCTOR)), db=Depends(get_db)
):
    row = await db.get(AvailabilityException, id)
    if not row or row.doctor_id != user.doctor_profile.id:
        raise SpandanException("NOT_FOUND", "Closure not found.", 404)
    await db.delete(row)
    await db.commit()
    return create_success_response("Closure removed.")
