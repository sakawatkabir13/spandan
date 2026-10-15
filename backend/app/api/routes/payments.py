import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.core.config import settings
from app.core.exceptions import SpandanException, create_success_response
from app.db.session import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.chamber import Chamber
from app.models.doctor import DoctorProfile
from app.models.operations import Payment
from app.models.schedule import Schedule
from app.models.user import PatientProfile, UserRole
from app.repositories.user import patient_repo
from app.services import billing
from app.services.billing import authorize

router = APIRouter(prefix="/payments", tags=["Payments and receipts"])






@router.get("/appointments")
async def billing_appointments(
    limit: int = Query(100, ge=1, le=100),
    user=Depends(get_current_active_user), db=Depends(get_db),
):
    stmt = select(Appointment, Payment, DoctorProfile.full_name, Chamber.name, Chamber.consultation_fee, Schedule.schedule_date, Schedule.start_time, PatientProfile.full_name).join(DoctorProfile, DoctorProfile.id == Appointment.doctor_id).join(Chamber, Chamber.id == Appointment.chamber_id).join(Schedule, Schedule.id == Appointment.schedule_id).join(PatientProfile, PatientProfile.id == Appointment.patient_id).outerjoin(Payment, Payment.appointment_id == Appointment.id)
    if user.role == UserRole.PATIENT:
        profile = await patient_repo.get_by_user_id(db, user.id)
        stmt = stmt.where(Appointment.patient_id == profile.id)
    elif user.role == UserRole.DOCTOR:
        stmt = stmt.where(Appointment.doctor_id == user.doctor_profile.id)
    elif user.role == UserRole.ASSISTANT:
        doctor_ids = [a.doctor_id for a in user.assistant_assignments if a.is_active and a.can_manage_appointments]
        stmt = stmt.where(Appointment.doctor_id.in_(doctor_ids))
    elif user.role != UserRole.ADMINISTRATOR:
        raise SpandanException("FORBIDDEN", "Billing access is not available.", 403)
    rows = await db.execute(stmt.order_by(Appointment.created_at.desc()).limit(limit))
    data = []
    for appointment, payment, doctor, chamber, fee, day, start, patient in rows:
        data.append({"id": appointment.id, "doctor_name": doctor, "chamber_name": chamber, "patient_name": appointment.attendee_name if appointment.dependent_id else patient, "session_date": day, "start_time": start, "serial_number": appointment.serial_number, "appointment_status": appointment.appointment_status.value, "amount": payment.amount if payment else fee, "currency": payment.currency if payment else settings.PAYMENT_CURRENCY, "payment_status": payment.status if payment else "unpaid", "payment_id": payment.id if payment else None})
    return create_success_response("Appointments and payments.", data)


@router.get("/appointment/{appointment_id}")
async def payment_details(
    appointment_id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)
):
    appointment = await authorize(db, user, appointment_id)
    payment = await db.scalar(select(Payment).where(Payment.appointment_id == appointment_id))
    from app.api.routes.operations import record

    return create_success_response(
        "Payment details.",
        {
            "payment": record(payment) if payment else None,
            "fee": payment.amount if payment else appointment.chamber.consultation_fee,
            "currency": settings.PAYMENT_CURRENCY,
            "online_enabled": settings.online_payments_enabled,
            "test_mode": True,
            "demo_enabled": bool(settings.DEMO_MODE and appointment.doctor.is_demo),
            "can_pay": appointment.appointment_status not in (AppointmentStatus.CANCELLED, AppointmentStatus.ABSENT) and (not payment or payment.status == "pending") and Decimal(payment.amount if payment else appointment.chamber.consultation_fee) > 0,
            "appointment": {"id": appointment.id, "doctor_name": appointment.doctor.full_name, "patient_name": appointment.attendee_name, "chamber_name": appointment.chamber.name, "session_date": appointment.schedule.schedule_date, "start_time": appointment.schedule.start_time, "serial_number": appointment.serial_number, "status": appointment.appointment_status.value},
        },
    )


@router.post("/appointment/{appointment_id}/checkout")
async def checkout(appointment_id: UUID, user=Depends(require_roles(UserRole.PATIENT)), db=Depends(get_db)):
    return await billing.checkout(appointment_id, user=user, db=db)


@router.post("/{id}/cancel-checkout")
async def cancel_checkout(id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    return await billing.cancel_checkout(id, user=user, db=db)


@router.post("/{id}/refresh")
async def refresh_payment(id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    initial = await db.get(Payment, id)
    if not initial:
        raise SpandanException("NOT_FOUND", "Payment not found.", 404)
    await authorize(db, user, initial.appointment_id)
    payment = await db.scalar(select(Payment).where(Payment.id == id).with_for_update().execution_options(populate_existing=True))
    if payment.provider == "stripe" and payment.status == "pending" and payment.provider_reference:
        session = await billing.stripe("GET", f"checkout/sessions/{payment.provider_reference}")
        if session.get("livemode") is True or session.get("id") != payment.provider_reference or session.get("amount_total") != int(Decimal(payment.amount) * 100) or session.get("currency") != payment.currency:
            raise SpandanException("PAYMENT_MISMATCH", "Payment details could not be verified.", 409)
        if session.get("status") == "complete" and session.get("payment_status") == "paid":
            payment.status = "paid"
            payment.paid_at = datetime.now(timezone.utc)
            from app.models.audit import AuditLog
            db.add(AuditLog(actor_user_id=user.id, action="payment.confirmed", entity_type="payment", entity_id=str(id)))
    await db.commit()
    return create_success_response("Payment status refreshed.", {"status": payment.status})


class DemoPaymentBody(BaseModel):
    outcome: Literal["success", "declined"] = "success"


@router.post("/appointment/{appointment_id}/demo")
async def demo_payment(
    appointment_id: UUID,
    request: DemoPaymentBody,
    user=Depends(require_roles(UserRole.PATIENT)),
    db=Depends(get_db),
):
    from app.models.audit import AuditLog
    from app.models.schedule import Schedule

    appointment = await authorize(db, user, appointment_id)
    if not settings.DEMO_MODE or not appointment.doctor.is_demo:
        raise SpandanException(
            "NOT_FOUND", "Payment simulation is unavailable for this appointment.", 404
        )
    await db.execute(
        select(Schedule.id).where(Schedule.id == appointment.schedule_id).with_for_update()
    )
    await db.refresh(appointment)
    if appointment.appointment_status in (AppointmentStatus.CANCELLED, AppointmentStatus.ABSENT):
        raise SpandanException("CONFLICT", "This appointment cannot be paid.", 409)
    payment = await db.scalar(
        select(Payment).where(Payment.appointment_id == appointment_id).with_for_update()
    )
    if payment:
        raise SpandanException(
            "CONFLICT", "Payment already exists. Finish its checkout or view its receipt.", 409
        )
    if request.outcome == "declined":
        return create_success_response(
            "Simulated card declined. No transaction was created.", {"outcome": "declined"}
        )
    payment = Payment(
        appointment_id=appointment_id,
        amount=appointment.chamber.consultation_fee,
        currency=settings.PAYMENT_CURRENCY,
        provider="demo",
        is_test=True,
        status="paid",
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    await db.flush()
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="payment.demo_simulated",
            entity_type="payment",
            entity_id=str(payment.id),
        )
    )
    await db.commit()
    return create_success_response(
        "Test payment recorded. No money was charged and no Stripe transaction was created.",
        {"outcome": "success"},
    )


class CashBody(BaseModel):
    method: str = "cash"


@router.post("/appointment/{appointment_id}/cash")
async def record_cash(appointment_id: UUID, request: CashBody, user=Depends(require_roles(UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR)), db=Depends(get_db)):
    return await billing.record_cash(appointment_id, request, user=user, db=db)


@router.post("/{id}/refund")
async def refund(id: UUID, user=Depends(require_roles(UserRole.DOCTOR, UserRole.ADMINISTRATOR)), db=Depends(get_db)):
    return await billing.refund(id, user=user, db=db)


@router.get("/{id}/receipt")
async def receipt(id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    payment = await db.get(Payment, id)
    if not payment:
        raise SpandanException("NOT_FOUND", "Receipt not found.", 404)
    appointment = await authorize(db, user, payment.appointment_id)
    if payment.status not in ("paid", "refunded", "refund_pending"):
        raise SpandanException("CONFLICT", "A receipt is available after payment.", 409)
    return create_success_response(
        "Receipt.",
        {
            "receipt_number": str(payment.id),
            "is_test": payment.is_test,
            "provider": payment.provider,
            "is_demo": appointment.doctor.is_demo,
            "operator": settings.OPERATOR_NAME,
            "contact": settings.OPERATOR_EMAIL,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "paid_at": payment.paid_at,
            "appointment_id": appointment.id,
            "serial_number": appointment.serial_number,
            "session_date": appointment.schedule.schedule_date,
            "patient_name": appointment.attendee_name,
            "doctor_name": appointment.doctor.full_name,
            "chamber_name": appointment.chamber.name,
        },
    )


async def record_checkout_failure(db, payment, event):
    from app.models.audit import AuditLog
    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id.startswith("evt_") or len(event_id) > 200:
        raise SpandanException("INVALID_EVENT", "Invalid payment failure event.", 400)
    # The payment row lock serializes redelivery; no card details or failure text are retained.
    existing = await db.scalar(select(AuditLog.id).where(
        AuditLog.action == "payment.checkout_failed", AuditLog.entity_id == str(payment.id),
        AuditLog.metadata_json["provider_event_id"].as_string() == event_id,
    ))
    if not existing:
        db.add(AuditLog(action="payment.checkout_failed", entity_type="payment", entity_id=str(payment.id), metadata_json={"provider_event_id": event_id}))


@router.post("/webhook")
async def webhook(request: Request, db=Depends(get_db)):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise SpandanException("PAYMENTS_UNAVAILABLE", "Webhook is not configured.", 503)
    raw = await request.body()
    header = request.headers.get("stripe-signature", "")
    try:
        parts = [pair.split("=", 1) for pair in header.split(",")]
        timestamp = next(value for name, value in parts if name == "t")
        signatures = [value for name, value in parts if name == "v1"]
        expected = hmac.new(
            settings.STRIPE_WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
        if abs(time.time() - int(timestamp)) > 300 or not any(
            hmac.compare_digest(expected, value) for value in signatures
        ):
            raise ValueError()
        event = json.loads(raw)
        obj = event["data"]["object"]
        if not isinstance(obj, dict) or not isinstance(obj.get("metadata", {}), dict):
            raise ValueError()

    except (ValueError, KeyError, StopIteration, TypeError):
        raise SpandanException("INVALID_SIGNATURE", "Invalid webhook.", 400)
    if event.get("livemode") is True or obj.get("livemode") is True:
        raise SpandanException(
            "LIVE_PAYMENTS_DISABLED", "Only test-mode webhooks are accepted.", 400
        )
    event_type = event.get("type")
    supported = {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
        "payment_intent.payment_failed",
        "refund.updated",
    }
    if event_type not in supported or not obj.get("metadata", {}).get("payment_id"):
        return create_success_response("Ignored unrelated event.")
    try:
        payment_id = UUID(obj["metadata"]["payment_id"])
    except (ValueError, TypeError):
        raise SpandanException("INVALID_EVENT", "Invalid payment reference.", 400)
    payment = await db.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
    if not payment:
        return create_success_response("Ignored unknown payment.")
    if event_type == "payment_intent.payment_failed":
        if payment.provider != "stripe" or not payment.provider_reference:
            raise SpandanException("PAYMENT_MISMATCH", "Payment details do not match.", 400)
        session = await billing.stripe("GET", f"checkout/sessions/{payment.provider_reference}")
        intent = session.get("payment_intent")
        intent_id = intent.get("id") if isinstance(intent, dict) else intent
        if (
            session.get("livemode") is True
            or intent_id != obj.get("id")
            or obj.get("amount") != int(Decimal(payment.amount) * 100)
            or obj.get("currency") != payment.currency
            or session.get("metadata", {}).get("payment_id") != str(payment.id)
        ):
            raise SpandanException("PAYMENT_MISMATCH", "Payment details do not match.", 400)
        await record_checkout_failure(db, payment, event)
        await db.commit()
        return create_success_response("Payment failure recorded. The patient can retry checkout.")
    if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded", "checkout.session.async_payment_failed"):
        if (
            payment.provider != "stripe"
            or obj.get("id") != payment.provider_reference
            or obj.get("amount_total") != int(Decimal(payment.amount) * 100)
            or obj.get("currency") != payment.currency
        ):
            raise SpandanException("PAYMENT_MISMATCH", "Payment details do not match.", 400)
        if event_type == "checkout.session.async_payment_failed":
            await record_checkout_failure(db, payment, event)
            await db.commit()
            return create_success_response("Payment failure recorded. The patient can retry checkout.")
        if obj.get("payment_status") != "paid":
            return create_success_response("Test payment is awaiting confirmation.")
        if payment.status == "pending":
            payment.status = "paid"
            payment.paid_at = datetime.now(timezone.utc)
    elif (
        event_type == "refund.updated"
        and payment.provider == "stripe"
        and obj.get("id") == payment.refund_reference
        and payment.status == "refund_pending"
    ):
        if obj.get("status") == "succeeded":
            payment.status = "refunded"
        elif obj.get("status") in ("failed", "canceled"):
            payment.status = "paid"
    await db.commit()
    return create_success_response("Webhook processed.")
