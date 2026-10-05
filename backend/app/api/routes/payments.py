import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.core.config import settings
from app.core.exceptions import SpandanException, create_success_response
from app.db.session import get_db
from app.models.appointment import AppointmentStatus
from app.models.operations import Payment
from app.models.user import UserRole
from app.repositories.appointment import appointment_repo
from app.repositories.user import patient_repo
from app.services.permissions import require_doctor_access

router = APIRouter(prefix="/payments", tags=["Payments and receipts"])


async def authorize(db, user, appointment_id, staff_only=False):
    appointment = await appointment_repo.get_by_id_with_details(db, appointment_id)
    if not appointment:
        raise SpandanException("NOT_FOUND", "Appointment not found.", 404)
    if user.role == UserRole.PATIENT and not staff_only:
        profile = await patient_repo.get_by_user_id(db, user.id)
        if profile.id != appointment.patient_id:
            raise SpandanException("FORBIDDEN", "This is not your appointment.", 403)
    else:
        require_doctor_access(user, appointment.doctor_id, "can_manage_appointments")
    return appointment


async def stripe(method, path, data=None, key=None):
    if not settings.STRIPE_SECRET_KEY:
        raise SpandanException(
            "PAYMENTS_UNAVAILABLE", "Online payment is not enabled. Pay at the chamber.", 503
        )
    headers = {"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"}
    if key:
        headers["Idempotency-Key"] = key
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(
            method, f"https://api.stripe.com/v1/{path}", data=data, headers=headers
        )
    if response.status_code >= 400:
        raise SpandanException(
            "PAYMENT_PROVIDER_ERROR", "The payment provider could not process this request.", 502
        )
    return response.json()


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
            "fee": appointment.chamber.consultation_fee,
            "currency": settings.PAYMENT_CURRENCY,
            "online_enabled": bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET),
        },
    )


@router.post("/appointment/{appointment_id}/checkout")
async def checkout(appointment_id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    appointment = await authorize(db, user, appointment_id)
    if appointment.appointment_status in (AppointmentStatus.CANCELLED, AppointmentStatus.ABSENT):
        raise SpandanException("CONFLICT", "This appointment cannot be paid.", 409)
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise SpandanException(
            "PAYMENTS_UNAVAILABLE", "Online payment is not enabled. Pay at the chamber.", 503
        )
    # Serialize payment creation alongside appointment changes.
    from app.models.schedule import Schedule

    await db.execute(
        select(Schedule.id).where(Schedule.id == appointment.schedule_id).with_for_update()
    )
    await db.refresh(appointment)
    if appointment.appointment_status in (AppointmentStatus.CANCELLED, AppointmentStatus.ABSENT):
        raise SpandanException("CONFLICT", "This appointment cannot be paid.", 409)
    payment = await db.scalar(
        select(Payment).where(Payment.appointment_id == appointment_id).with_for_update()
    )
    if payment and payment.status != "pending":
        raise SpandanException("CONFLICT", "This payment has already been processed.", 409)
    if not payment:
        payment = Payment(
            appointment_id=appointment_id,
            amount=appointment.chamber.consultation_fee,
            currency=settings.PAYMENT_CURRENCY,
        )
        db.add(payment)
        await db.flush()
    amount = int(Decimal(payment.amount) * 100)
    if amount <= 0:
        raise SpandanException("CONFLICT", "This consultation has no fee.", 409)
    session = await stripe(
        "POST",
        "checkout/sessions",
        {
            "mode": "payment",
            "success_url": f"{settings.FRONTEND_URL}/dashboard/patient?payment=returned",
            "cancel_url": f"{settings.FRONTEND_URL}/dashboard/patient?payment=cancelled",
            "metadata[payment_id]": str(payment.id),
            "line_items[0][price_data][currency]": payment.currency,
            "line_items[0][price_data][unit_amount]": str(amount),
            "line_items[0][price_data][product_data][name]": "Spandan consultation",
            "line_items[0][quantity]": "1",
        },
        f"checkout:{payment.id}",
    )
    payment.provider_reference = session["id"]
    await db.commit()
    return create_success_response(
        "Continue to the secure payment provider.", {"url": session["url"]}
    )


class CashBody(BaseModel):
    method: str = "cash"


@router.post("/appointment/{appointment_id}/cash")
async def record_cash(
    appointment_id: UUID,
    request: CashBody,
    user=Depends(require_roles(UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR)),
    db=Depends(get_db),
):
    from app.models.audit import AuditLog

    appointment = await authorize(db, user, appointment_id, staff_only=True)
    from app.models.schedule import Schedule

    await db.execute(
        select(Schedule.id).where(Schedule.id == appointment.schedule_id).with_for_update()
    )
    await db.refresh(appointment)
    if await db.scalar(select(Payment.id).where(Payment.appointment_id == appointment_id)):
        raise SpandanException("CONFLICT", "Payment already exists for this appointment.", 409)
    if request.method != "cash" or appointment.appointment_status in (
        AppointmentStatus.CANCELLED,
        AppointmentStatus.ABSENT,
    ):
        raise SpandanException(
            "CONFLICT", "Cash payment cannot be recorded for this appointment.", 409
        )
    payment = Payment(
        appointment_id=appointment_id,
        amount=appointment.chamber.consultation_fee,
        currency=settings.PAYMENT_CURRENCY,
        status="paid",
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    await db.flush()
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="payment.cash_recorded",
            entity_type="payment",
            entity_id=str(payment.id),
        )
    )
    await db.commit()
    return create_success_response("Payment recorded. A receipt is available.")


@router.post("/{id}/refund")
async def refund(
    id: UUID,
    user=Depends(require_roles(UserRole.DOCTOR, UserRole.ADMINISTRATOR)),
    db=Depends(get_db),
):
    from app.models.audit import AuditLog

    payment = await db.scalar(select(Payment).where(Payment.id == id).with_for_update())
    if not payment:
        raise SpandanException("NOT_FOUND", "Payment not found.", 404)
    appointment = await authorize(db, user, payment.appointment_id, staff_only=True)
    if payment.status != "paid" or appointment.appointment_status != AppointmentStatus.CANCELLED:
        raise SpandanException(
            "CONFLICT", "Cancel the appointment before refunding a paid consultation.", 409
        )
    if payment.provider_reference:
        session = await stripe("GET", f"checkout/sessions/{payment.provider_reference}")
        result = await stripe(
            "POST",
            "refunds",
            {"payment_intent": session["payment_intent"], "metadata[payment_id]": str(payment.id)},
            f"refund:{payment.id}",
        )
        payment.refund_reference = result["id"]
        payment.status = "refunded" if result["status"] == "succeeded" else "refund_pending"
    else:
        payment.status = "refunded"
        payment.refund_reference = f"cash:{payment.id}"
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="payment.refund_recorded",
            entity_type="payment",
            entity_id=str(payment.id),
        )
    )
    await db.commit()
    return create_success_response(
        "Refund recorded. For cash payments, the chamber must return the money to the patient."
    )


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
            "operator": settings.OPERATOR_NAME,
            "contact": settings.OPERATOR_EMAIL,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "paid_at": payment.paid_at,
            "appointment_id": appointment.id,
            "serial_number": appointment.serial_number,
            "session_date": appointment.schedule.schedule_date,
        },
    )


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
        payment_id = UUID(obj["metadata"]["payment_id"])
    except (ValueError, KeyError, StopIteration, TypeError):
        raise SpandanException("INVALID_SIGNATURE", "Invalid webhook.", 400)
    payment = await db.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
    if not payment:
        return create_success_response("Ignored unknown payment.")
    event_type = event.get("type")
    if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if (
            obj.get("id") != payment.provider_reference
            or obj.get("amount_total") != int(Decimal(payment.amount) * 100)
            or obj.get("currency") != payment.currency
            or obj.get("payment_status") != "paid"
        ):
            raise SpandanException("PAYMENT_MISMATCH", "Payment details do not match.", 400)
        if payment.status == "pending":
            payment.status = "paid"
            payment.paid_at = datetime.now(timezone.utc)
    elif event_type == "refund.updated" and obj.get("id") == payment.refund_reference:
        if obj.get("status") == "succeeded":
            payment.status = "refunded"
        elif obj.get("status") in ("failed", "canceled"):
            payment.status = "paid"
    await db.commit()
    return create_success_response("Webhook processed.")
