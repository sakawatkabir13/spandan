"""Visit preparation, doctor-authored follow-up, discovery and operational review."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.api.dependencies.auth import require_roles
from app.api.routes.medical import chart_history, medical_payload, own_profile, shared_report_ids
from app.core.exceptions import SpandanException, create_success_response
from app.core.time import aware, local_now, session_time
from app.db.session import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit import AuditLog
from app.models.care import AppointmentSharing, BookingEvent, FavoriteDoctor, VisitSummary
from app.models.doctor import DoctorProfile, DoctorVerificationStatus
from app.models.medical import MedicalReport
from app.models.schedule import Schedule, ScheduleStatus
from app.models.user import User, UserRole
from app.repositories.appointment import appointment_repo
from app.schemas.appointment import AppointmentResponse
from app.services.billing import authorize
from app.services.notifications import notify
from app.services.permissions import require_doctor_access

router = APIRouter(tags=["Care journey"])


async def patient_appointment(db, user, id, lock=False):
    profile = await own_profile(db, user, lock=lock)
    appointment = await appointment_repo.get_by_id_with_details(db, id)
    if not appointment or appointment.patient_id != profile.id:
        raise SpandanException("NOT_FOUND", "Appointment not found.", 404)
    return appointment


class SharingBody(BaseModel):
    share_history: bool = False
    report_ids: list[UUID] = Field(default_factory=list, max_length=30)
    model_config = ConfigDict(extra="forbid")


@router.get("/appointments/{id}/sharing")
async def get_sharing(id: UUID, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    appointment = await patient_appointment(db, user, id)
    chart = await medical_payload(db, appointment.patient, appointment.dependent_id)
    preference = await db.get(AppointmentSharing, id)
    history = await chart_history(db, appointment.patient, appointment.dependent_id)
    return create_success_response("Sharing for this visit.", {
        "share_history": bool(preference.share_history if preference else history and history.share_with_doctors),
        "report_ids": sorted(await shared_report_ids(db, appointment)),
        "reports": chart["reports"], "attendee_name": appointment.attendee_name,
        "dependent_id": appointment.dependent_id,
    })


@router.put("/appointments/{id}/sharing")
async def save_sharing(id: UUID, request: SharingBody, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    appointment = await patient_appointment(db, user, id, lock=True)
    permitted = set(await db.scalars(select(MedicalReport.id).where(MedicalReport.patient_id == appointment.patient_id, MedicalReport.dependent_id == appointment.dependent_id, MedicalReport.share_with_doctors.is_(True))))
    if not set(request.report_ids) <= permitted:
        raise SpandanException("VALIDATION_ERROR", "Choose shareable reports from this patient's chart.")
    preference = await db.get(AppointmentSharing, id)
    if not preference:
        preference = AppointmentSharing(appointment_id=id)
        db.add(preference)
    preference.share_history = request.share_history
    preference.report_ids = sorted({str(id) for id in request.report_ids})
    db.add(AuditLog(actor_user_id=user.id, action="medical.visit_sharing_updated", entity_type="appointment", entity_id=str(id), metadata_json={"share_history": request.share_history, "report_count": len(request.report_ids)}))
    await db.commit()
    return create_success_response("Sharing saved for this visit.")


@router.get("/medical-records/access-history")
async def access_history(limit: int = Query(30, ge=1, le=100), user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    profile = await own_profile(db, user)
    appointment_ids = {str(id) for id in await db.scalars(select(Appointment.id).where(Appointment.patient_id == profile.id))}
    report_ids = {str(id) for id in await db.scalars(select(MedicalReport.id).where(MedicalReport.patient_id == profile.id))}
    # SQL ownership bounds the query; never scan or return another patient's access events.
    rows = await db.execute(select(AuditLog, DoctorProfile.full_name).join(DoctorProfile, DoctorProfile.user_id == AuditLog.actor_user_id).where(
        AuditLog.action.in_(["medical.records_viewed", "medical.report_downloaded", "medical.report_previewed"]),
        ((AuditLog.entity_type == "patient") & (AuditLog.entity_id == str(profile.id))) |
        ((AuditLog.entity_type == "medical_report") & AuditLog.entity_id.in_(report_ids)),
    ).order_by(AuditLog.created_at.desc()).limit(limit))
    return create_success_response("Doctor access history.", [{"id": str(log.id), "doctor_name": name, "action": log.action, "created_at": log.created_at, "appointment_id": (log.metadata_json or {}).get("appointment_id") if (log.metadata_json or {}).get("appointment_id") in appointment_ids else None} for log, name in rows])


class SummaryBody(BaseModel):
    summary: str = Field(default="", max_length=12000)
    prescription: str = Field(default="", max_length=12000)
    follow_up_instructions: str = Field(default="", max_length=6000)
    follow_up_date: date | None = None
    revision: int = Field(ge=0)
    publish: bool = False
    model_config = ConfigDict(extra="forbid")


def summary_payload(row):
    return {name: getattr(row, name) for name in ("summary", "prescription", "follow_up_instructions", "follow_up_date", "revision", "published_at", "updated_at")} if row else None


@router.get("/appointments/{id}/visit-summary")
async def get_summary(id: UUID, user=Depends(require_roles(UserRole.PATIENT, UserRole.DOCTOR)), db=Depends(get_db)):
    appointment = await authorize(db, user, id)
    row = await db.get(VisitSummary, appointment.id)
    if user.role == UserRole.PATIENT and row and not row.published_at:
        row = None
    return create_success_response("Visit summary.", summary_payload(row))


@router.put("/appointments/{id}/visit-summary")
async def save_summary(id: UUID, request: SummaryBody, user=Depends(require_roles(UserRole.DOCTOR)), db=Depends(get_db)):
    appointment = await authorize(db, user, id)
    if user.doctor_profile.verification_status != DoctorVerificationStatus.APPROVED:
        raise SpandanException("FORBIDDEN", "Doctor approval is required.", 403)
    await db.execute(select(Appointment.id).where(Appointment.id == id).with_for_update())
    await db.refresh(appointment, attribute_names=["appointment_status"])
    if appointment.appointment_status not in (AppointmentStatus.IN_CONSULTATION, AppointmentStatus.COMPLETED):
        raise SpandanException("CONFLICT", "Start the consultation before writing a visit record.", 409)
    row = await db.get(VisitSummary, id, populate_existing=True)
    if request.revision != (row.revision if row else 0):
        raise SpandanException("CONFLICT", "This record changed in another window. Reload before saving.", 409)
    if request.publish and not request.summary.strip():
        raise SpandanException("VALIDATION_ERROR", "Review and add a visit summary before publishing.")
    if not row:
        row = VisitSummary(appointment_id=id, doctor_id=appointment.doctor_id, revision=0)
        db.add(row)
    # Published versions cannot be turned into hidden drafts. Explicit approval is required to update them.
    if row.published_at and not request.publish:
        raise SpandanException("CONFLICT", "Review and publish changes to an already published record.", 409)
    for key in ("summary", "prescription", "follow_up_instructions", "follow_up_date"):
        setattr(row, key, getattr(request, key))
    row.revision += 1
    if request.publish:
        row.published_at = datetime.now(timezone.utc)
        patient_user = await db.get(User, appointment.patient.user_id)
        from app.core.config import settings
        await notify(db, patient_user, "Your visit summary is ready", f"Your doctor has published your visit summary and follow-up instructions. View them at {settings.FRONTEND_URL}/dashboard/patient/appointments/{id}", f"visit-summary:{id}:{row.revision}")
    db.add(AuditLog(actor_user_id=user.id, action="medical.visit_published" if request.publish else "medical.visit_drafted", entity_type="appointment", entity_id=str(id), metadata_json={"revision": row.revision}))
    await db.commit()
    return create_success_response("Visit record published." if request.publish else "Draft saved.", summary_payload(row))


@router.get("/workspace/today")
async def today(user=Depends(require_roles(UserRole.DOCTOR)), db=Depends(get_db)):
    if user.doctor_profile.verification_status != DoctorVerificationStatus.APPROVED:
        raise SpandanException("FORBIDDEN", "Doctor approval is required.", 403)
    from app.services.schedule import schedule_service
    schedules = [s for s in await schedule_service.get_my_schedules(db, user) if s.schedule_date == local_now().date()]
    result = []
    for session in schedules:
        for appointment in await appointment_repo.get_by_schedule_id(db, session.id):
            if appointment.appointment_status in (AppointmentStatus.CANCELLED, AppointmentStatus.ABSENT):
                continue
            history = await chart_history(db, appointment.patient, appointment.dependent_id)
            sharing = await db.get(AppointmentSharing, appointment.id)
            history_shared = bool(sharing.share_history if sharing else history and history.share_with_doctors)
            report_ids = await shared_report_ids(db, appointment)
            latest = await db.scalar(select(func.max(MedicalReport.created_at)).where(MedicalReport.id.in_([UUID(id) for id in report_ids]))) if report_ids else None
            summary = await db.get(VisitSummary, appointment.id)
            result.append({"appointment": AppointmentResponse.model_validate(appointment).model_dump(mode="json"), "history_reviewed": bool(history_shared and history and history.history_reviewed), "history_shared": history_shared, "shared_report_count": len(report_ids), "latest_report_at": latest, "summary_published": bool(summary and summary.published_at)})
    return create_success_response("Today's patients.", result)


@router.get("/workspace/review")
async def review(user=Depends(require_roles(UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR)), db=Depends(get_db)):
    today_date = local_now().date()
    rows = await db.scalars(select(Appointment).join(Schedule, Schedule.id == Appointment.schedule_id).where(
        Schedule.schedule_date.between(today_date - timedelta(days=14), today_date),
        Appointment.appointment_status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED]),
    ).order_by(Schedule.schedule_date).limit(500))
    result = []
    for row in rows:
        try:
            require_doctor_access(user, row.doctor_id, "can_read_queue")
        except SpandanException:
            continue
        app = await appointment_repo.get_by_id_with_details(db, row.id)
        stale = session_time(app.schedule, app.schedule.end_time) < local_now()
        long_visit = app.actual_consultation_started_at and aware(app.actual_consultation_started_at) < datetime.now(timezone.utc) - timedelta(hours=1)
        if stale or long_visit or app.appointment_status == AppointmentStatus.ABSENT:
            result.append({"appointment": AppointmentResponse.model_validate(app).model_dump(mode="json"), "reason": "Consultation open over an hour" if long_visit else "Missed visit" if app.appointment_status == AppointmentStatus.ABSENT else "Session ended; visit unresolved"})
    return create_success_response("Visits needing review.", result)


@router.get("/patients/me/favorites")
async def favorites(user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    profile = await own_profile(db, user)
    return create_success_response("Saved doctors.", [str(id) for id in await db.scalars(select(FavoriteDoctor.doctor_id).where(FavoriteDoctor.patient_id == profile.id))])


@router.get("/patients/me/favorite-doctors")
async def favorite_doctors(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=20), user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    from app.core.config import settings
    from app.repositories.doctor import doctor_repo
    from app.schemas.doctor import DoctorProfileResponse
    profile = await own_profile(db, user)
    stmt = select(FavoriteDoctor.doctor_id).join(DoctorProfile, DoctorProfile.id == FavoriteDoctor.doctor_id).join(User, User.id == DoctorProfile.user_id).where(FavoriteDoctor.patient_id == profile.id, DoctorProfile.verification_status == DoctorVerificationStatus.APPROVED, User.is_active.is_(True))
    if not settings.DEMO_MODE:
        stmt = stmt.where(DoctorProfile.is_demo.is_(False))
    ids = list(await db.scalars(stmt.order_by(FavoriteDoctor.created_at.desc()).offset(skip).limit(limit)))
    return create_success_response("Saved doctor profiles.", [DoctorProfileResponse.model_validate(await doctor_repo.get_by_id_with_details(db, id)).model_dump(mode="json") for id in ids])


@router.put("/patients/me/favorites/{doctor_id}")
async def favorite(doctor_id: UUID, saved: bool = Query(...), user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    profile = await own_profile(db, user, lock=True)
    if not await db.get(DoctorProfile, doctor_id):
        raise SpandanException("NOT_FOUND", "Doctor not found.", 404)
    row = await db.get(FavoriteDoctor, (profile.id, doctor_id))
    if saved and not row:
        db.add(FavoriteDoctor(patient_id=profile.id, doctor_id=doctor_id))
    elif not saved and row:
        await db.delete(row)
    await db.commit()
    return create_success_response("Saved doctor updated.")


@router.get("/doctors/{doctor_id}/booking-facts")
async def booking_facts(doctor_id: UUID, db=Depends(get_db)):
    from app.models.chamber import Chamber
    from app.services.doctor import doctor_service
    doctor = await doctor_service.get_doctor_profile(db, doctor_id)
    if not doctor or doctor.verification_status != DoctorVerificationStatus.APPROVED or not await db.scalar(select(User.is_active).where(User.id == doctor.user_id)):
        raise SpandanException("NOT_FOUND", "Doctor not found.", 404)
    chambers = list(await db.scalars(select(Chamber).where(Chamber.doctor_id == doctor_id, Chamber.is_active.is_(True))))
    sessions = list(await db.scalars(select(Schedule).where(Schedule.doctor_id == doctor_id, Schedule.chamber_id.in_([c.id for c in chambers]), Schedule.schedule_date >= local_now().date(), Schedule.status == ScheduleStatus.OPEN).order_by(Schedule.schedule_date, Schedule.start_time).limit(30)))
    next_session = next((s for s in sessions if session_time(s, s.end_time) > local_now()), None)
    return create_success_response("Current booking information.", {"languages": doctor.languages, "minimum_patient_age": doctor.minimum_patient_age, "maximum_patient_age": doctor.maximum_patient_age,
        "chambers": [{"id": c.id, "name": c.name, "area": c.area, "district": c.district, "consultation_fee": c.consultation_fee, "follow_up_fee": c.follow_up_fee} for c in chambers],
        "next_session": {"id": next_session.id, "date": next_session.schedule_date, "start_time": next_session.start_time, "confirmed_at": next_session.confirmed_at, "chamber_id": next_session.chamber_id} if next_session else None})


class FunnelBody(BaseModel):
    doctor_id: UUID
    event: Literal["booking_started"]


@router.get("/discovery/booking-facts")
async def discovery_facts(doctor_ids: list[UUID] = Query(..., max_length=20), db=Depends(get_db)):
    result = {}
    for id in dict.fromkeys(doctor_ids):
        try:
            result[str(id)] = (await booking_facts(id, db))["data"]
        except SpandanException as exc:
            if exc.status_code != 404:
                raise
    return create_success_response("Doctor booking information.", result)


@router.post("/patients/me/booking-events", status_code=201)
async def booking_event(request: FunnelBody, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    profile = await own_profile(db, user, lock=True)
    if not await db.get(DoctorProfile, request.doctor_id):
        raise SpandanException("NOT_FOUND", "Doctor not found.", 404)
    recent = await db.scalar(select(BookingEvent.id).where(BookingEvent.patient_id == profile.id, BookingEvent.doctor_id == request.doctor_id, BookingEvent.created_at >= datetime.now(timezone.utc) - timedelta(minutes=30)).limit(1))
    if not recent:
        db.add(BookingEvent(patient_id=profile.id, doctor_id=request.doctor_id, event=request.event))
        await db.commit()
    return create_success_response("Booking progress recorded.")
