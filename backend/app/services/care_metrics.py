"""Aggregate operational measures without returning clinical text or report contents."""
from datetime import timedelta

from sqlalchemy import select

from app.core.time import aware
from app.models.appointment import AppointmentStatus, BookingSource
from app.models.audit import AuditLog
from app.models.care import BookingEvent
from app.models.operations import Payment


async def care_metrics(db, appointments, cutoff, doctor_ids):
    starts_query = select(BookingEvent).where(BookingEvent.created_at >= cutoff)
    if doctor_ids is not None:
        starts_query = starts_query.where(BookingEvent.doctor_id.in_(doctor_ids))
    starts = list(await db.scalars(starts_query))
    completed = sum(any(a.patient_id == event.patient_id and a.doctor_id == event.doctor_id and a.booking_source == BookingSource.ONLINE and aware(event.created_at) <= aware(a.created_at) <= aware(event.created_at) + timedelta(minutes=30) for a in appointments) for event in starts)
    ids = {str(a.id): a for a in appointments}
    payments = list(await db.scalars(select(Payment).where(Payment.appointment_id.in_([a.id for a in appointments]))))
    failures = list(await db.scalars(select(AuditLog).where(AuditLog.action == "payment.checkout_failed", AuditLog.entity_id.in_([str(p.id) for p in payments]), AuditLog.created_at >= cutoff)))
    views = list(await db.scalars(select(AuditLog).where(AuditLog.action == "medical.records_viewed", AuditLog.created_at >= cutoff, AuditLog.metadata_json["appointment_id"].as_string().in_(list(ids)))))
    prepared = {str((log.metadata_json or {}).get("appointment_id")) for log in views if str((log.metadata_json or {}).get("appointment_id")) in ids and ids[str(log.metadata_json["appointment_id"])].actual_consultation_started_at and aware(log.created_at) <= aware(ids[str(log.metadata_json["appointment_id"])].actual_consultation_started_at)}
    errors = [abs((aware(a.actual_consultation_started_at) - aware(a.estimated_consultation_at)).total_seconds() / 60) for a in appointments if a.actual_consultation_started_at and a.estimated_consultation_at]
    attended = sum(a.appointment_status == AppointmentStatus.COMPLETED for a in appointments)
    absent = sum(a.appointment_status == AppointmentStatus.ABSENT for a in appointments)
    return {
        "booking_starts": len(starts), "booking_completions": completed,
        "booking_completion_percent": round(100 * completed / len(starts), 1) if starts else None,
        "payment_failures": len(failures), "pending_payments": sum(p.status == "pending" for p in payments),
        "no_show_percent": round(100 * absent / (attended + absent), 1) if attended + absent else None,
        "booking_estimate_mean_error_minutes": round(sum(errors) / len(errors), 1) if errors else None,
        "booking_estimate_sample_count": len(errors), "charts_reviewed_before_consultation": len(prepared),
        "consultations_started": sum(bool(a.actual_consultation_started_at) for a in appointments),
    }
