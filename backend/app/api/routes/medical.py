import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.dependencies.auth import require_roles
from app.core.exceptions import SpandanException, create_success_response
from app.core.time import local_now
from app.db.session import get_db
from app.models.appointment import AppointmentStatus
from app.models.audit import AuditLog
from app.models.doctor import DoctorVerificationStatus
from app.models.medical import MedicalHistory, MedicalReport
from app.models.user import PatientProfile, UserRole
from app.repositories.appointment import appointment_repo
from app.schemas.medical import (
    MedicalHistoryResponse,
    MedicalHistoryUpdate,
    MedicalReportResponse,
    ReportType,
)
from app.services import medical_records as storage

router = APIRouter(prefix="/medical-records", tags=["Private medical records"])


async def own_profile(db, user, lock=False):
    stmt = select(PatientProfile).where(PatientProfile.user_id == user.id)
    if lock:
        stmt = stmt.with_for_update()
    profile = await db.scalar(stmt)
    if not profile:
        raise SpandanException("NOT_FOUND", "Patient profile not found.", 404)
    return profile


def report_metadata(report):
    return MedicalReportResponse.model_validate(report).model_dump(mode="json")


async def medical_payload(db, profile):
    history = await db.get(MedicalHistory, profile.id)
    reports = list(await db.scalars(select(MedicalReport).where(MedicalReport.patient_id == profile.id).order_by(MedicalReport.report_date.desc().nullslast(), MedicalReport.created_at.desc())))
    steps = {
        "personal_details": bool(profile.date_of_birth and profile.gender and profile.emergency_contact),
        "medical_history": bool(history and history.history_reviewed),
    }
    return {
        "history": MedicalHistoryResponse.model_validate(history).model_dump(mode="json") if history else MedicalHistoryResponse().model_dump(mode="json"),
        "reports": [report_metadata(r) for r in reports],
        "completion": {"steps": steps, "percent": sum(steps.values()) * 50},
        "limits": {"max_file_bytes": storage.MAX_REPORT_BYTES, "max_reports": storage.MAX_REPORTS, "max_total_bytes": storage.MAX_PATIENT_BYTES, "used_bytes": sum(r.size_bytes for r in reports)},
    }


@router.get("/me")
async def own_records(user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    return create_success_response("Medical profile fetched.", await medical_payload(db, await own_profile(db, user)))


@router.patch("/me/history")
async def update_history(request: MedicalHistoryUpdate, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    profile = await own_profile(db, user, lock=True)
    history = await db.get(MedicalHistory, profile.id)
    if not history:
        history = MedicalHistory(patient_id=profile.id)
        db.add(history)
    for name, value in request.model_dump(exclude_unset=True).items():
        setattr(history, name, value)
    db.add(AuditLog(actor_user_id=user.id, action="medical.history_updated", entity_type="patient", entity_id=str(profile.id), metadata_json={"changed_fields": list(request.model_fields_set), "share_with_doctors": bool(history.share_with_doctors)}))
    await db.commit()
    return create_success_response("Medical history and sharing preferences saved.", await medical_payload(db, profile))


@router.post("/me/reports", status_code=201)
async def upload_report(
    title: str = Form(..., min_length=2, max_length=120),
    report_type: ReportType = Form("other"),
    report_date: date | None = Form(None),
    notes: str = Form("", max_length=1000),
    file: UploadFile = File(...),
    user=Depends(require_roles(UserRole.PATIENT)),
    db=Depends(get_db),
):
    if len(title.strip()) < 2 or (report_date and report_date > local_now().date()):
        raise SpandanException("VALIDATION_ERROR", "Enter a report title and a report date that is not in the future.")
    content = await file.read(storage.MAX_REPORT_BYTES + 1)
    await file.close()
    if len(content) > storage.MAX_REPORT_BYTES:
        raise SpandanException("PAYLOAD_TOO_LARGE", "Reports must be 5 MB or smaller.", 413)
    mime = storage.detect_report_type(content)
    if len(content) < 16 or not mime or file.content_type != mime:
        raise SpandanException("VALIDATION_ERROR", "Upload a PDF, JPEG, PNG, or WebP report with a matching file type.")
    profile = await own_profile(db, user, lock=True)
    count, used = (await db.execute(select(func.count(MedicalReport.id), func.coalesce(func.sum(MedicalReport.size_bytes), 0)).where(MedicalReport.patient_id == profile.id))).one()
    if count >= storage.MAX_REPORTS or used + len(content) > storage.MAX_PATIENT_BYTES:
        raise SpandanException("STORAGE_LIMIT", "Your medical report storage is full. Remove an older report before uploading.", 409)
    filename = re.sub(r"[\x00-\x1f\x7f]", "", Path((file.filename or "report").replace("\\", "/")).name)[:180] or "report"
    report = MedicalReport(patient_id=profile.id, title=title.strip(), report_type=report_type, report_date=report_date, notes=notes.strip(), original_filename=filename, content_type=mime, size_bytes=len(content), storage_key=uuid4().hex)
    await storage.store_report(report.storage_key, content)
    try:
        db.add(report)
        await db.flush()
        db.add(AuditLog(actor_user_id=user.id, action="medical.report_uploaded", entity_type="medical_report", entity_id=str(report.id)))
        await db.commit()
    except Exception:
        await storage.remove_report(report.storage_key)
        raise
    return create_success_response("Medical report uploaded securely.", report_metadata(report))


async def owned_report(db, user, report_id, lock=False):
    profile = await own_profile(db, user, lock=lock)
    report = await db.scalar(select(MedicalReport).where(MedicalReport.id == report_id, MedicalReport.patient_id == profile.id))
    if not report:
        raise SpandanException("NOT_FOUND", "Medical report not found.", 404)
    return report


async def download_response(db, user, report):
    content = await storage.read_report(report.storage_key)
    db.add(AuditLog(actor_user_id=user.id, action="medical.report_downloaded", entity_type="medical_report", entity_id=str(report.id)))
    await db.commit()
    return Response(content, media_type=report.content_type, headers={"Content-Disposition": f"attachment; filename=\"medical-report\"; filename*=UTF-8''{quote(report.original_filename, safe='')}", "Cache-Control": "no-store, private", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"})


@router.get("/me/reports/{id}/download")
async def download_own_report(id: UUID, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    return await download_response(db, user, await owned_report(db, user, id))


@router.delete("/me/reports/{id}")
async def delete_report(id: UUID, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    report = await owned_report(db, user, id, lock=True)
    key = report.storage_key
    db.add(AuditLog(actor_user_id=user.id, action="medical.report_deleted", entity_type="medical_report", entity_id=str(id)))
    await db.delete(report)
    await db.commit()
    await storage.remove_report(key)
    return create_success_response("Medical report removed.")


async def doctor_appointment(db, user, id):
    appointment = await appointment_repo.get_by_id_with_details(db, id)
    if not appointment or not user.doctor_profile or appointment.doctor_id != user.doctor_profile.id:
        raise SpandanException("NOT_FOUND", "Appointment not found.", 404)
    if user.doctor_profile.verification_status != DoctorVerificationStatus.APPROVED:
        raise SpandanException("FORBIDDEN", "Practitioner approval is required to access patient medical records.", 403)
    if appointment.appointment_status in (AppointmentStatus.CANCELLED, AppointmentStatus.ABSENT) or appointment.schedule.schedule_date < local_now().date() - timedelta(days=30):
        raise SpandanException("FORBIDDEN", "Medical records are available for active appointments and 30 days of follow-up.", 403)
    history = await db.get(MedicalHistory, appointment.patient_id)
    shared = bool(not appointment.dependent_id and history and history.share_with_doctors)
    return appointment, shared


@router.get("/appointments/{id}")
async def appointment_records(id: UUID, user=Depends(require_roles(UserRole.DOCTOR)), db=Depends(get_db)):
    appointment, shared = await doctor_appointment(db, user, id)
    result = {"appointment_id": str(id), "patient": {"full_name": appointment.attendee_name}, "shared": shared, "dependent_booking": bool(appointment.dependent_id)}
    if shared:
        profile = appointment.patient
        result["patient"].update({"date_of_birth": profile.date_of_birth, "gender": profile.gender, "emergency_contact": profile.emergency_contact})
        result.update(await medical_payload(db, profile))
        db.add(AuditLog(actor_user_id=user.id, action="medical.records_viewed", entity_type="patient", entity_id=str(profile.id), metadata_json={"appointment_id": str(id)}))
        await db.commit()
    return create_success_response("Patient medical records.", result)


@router.get("/appointments/{id}/reports/{report_id}/download")
async def download_for_doctor(id: UUID, report_id: UUID, user=Depends(require_roles(UserRole.DOCTOR)), db=Depends(get_db)):
    appointment, shared = await doctor_appointment(db, user, id)
    if not shared:
        raise SpandanException("FORBIDDEN", "The patient has not shared medical records for this appointment.", 403)
    report = await db.scalar(select(MedicalReport).where(MedicalReport.id == report_id, MedicalReport.patient_id == appointment.patient_id))
    if not report:
        raise SpandanException("NOT_FOUND", "Medical report not found.", 404)
    return await download_response(db, user, report)
