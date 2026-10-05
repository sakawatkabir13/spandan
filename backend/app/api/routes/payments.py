import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
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
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(
                method, f"https://api.stripe.com/v1/{path}", data=data, headers=headers
            )
    except httpx.RequestError:
        raise SpandanException(
            "PAYMENT_PROVIDER_ERROR", "Payment provider unavailable. Please retry.", 502
        )
    if response.status_code >= 400:
        raise SpandanException(
            "PAYMENT_PROVIDER_ERROR", "The payment provider could not process this request.", 502
        )
    try:
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except ValueError:
        raise SpandanException("PAYMENT_PROVIDER_ERROR", "Invalid payment provider response.", 502)


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
            "online_enabled": settings.online_payments_enabled,
            "test_mode": True,
            "demo_enabled": bool(settings.DEMO_MODE and appointment.doctor.is_demo),
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
            provider="stripe",
            is_test=True,
        )
        db.add(payment)
        await db.flush()
    if payment.provider_reference and payment.provider == "stripe":
        existing = await stripe("GET", f"checkout/sessions/{payment.provider_reference}")
        if existing.get("status") == "open" and existing.get("url"):
            return create_success_response(
                "Continue to Stripe test checkout.", {"url": existing["url"]}
            )
        if existing.get("status") == "complete":
            raise SpandanException(
                "PAYMENT_PROCESSING",
                "Stripe is confirming this test payment. Refresh shortly.",
                409,
            )
        if existing.get("status") != "expired":
            raise SpandanException(
                "PAYMENT_PROVIDER_ERROR", "Unable to confirm the previous checkout.", 502
            )
        payment.checkout_attempt += 1
    payment.provider = "stripe"
    payment.is_test = True
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
        f"checkout:{payment.id}:{payment.checkout_attempt}",
    )
    if session.get("livemode") is True or not session.get("id") or not session.get("url"):
        raise SpandanException(
            "PAYMENT_PROVIDER_ERROR", "Expected a Stripe test checkout session.", 502
        )
    payment.provider_reference = session["id"]
    await db.commit()
    return create_success_response(
        "Continue to Stripe test checkout. No real money will be charged.", {"url": session["url"]}
    )


@router.post("/{id}/cancel-checkout")
async def cancel_checkout(id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    from app.models.audit import AuditLog
    from app.models.schedule import Schedule

    initial = await db.get(Payment, id)
    if not initial:
        raise SpandanException("NOT_FOUND", "Payment not found.", 404)
    appointment = await authorize(db, user, initial.appointment_id)
    await db.execute(
        select(Schedule.id).where(Schedule.id == appointment.schedule_id).with_for_update()
    )
    payment = await db.scalar(
        select(Payment)
        .where(Payment.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not payment or payment.status != "pending" or payment.provider != "stripe":
        raise SpandanException("CONFLICT", "Only a pending Stripe checkout can be cancelled.", 409)
    if payment.provider_reference:
        session = await stripe("GET", f"checkout/sessions/{payment.provider_reference}")
        if session.get("status") == "open":
            session = await stripe(
                "POST",
                f"checkout/sessions/{payment.provider_reference}/expire",
                key=f"expire:{payment.id}",
            )
        if session.get("status") != "expired":
            raise SpandanException(
                "PAYMENT_PROCESSING",
                "This checkout is processing or already complete. Refresh its payment status.",
                409,
            )
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="payment.checkout_cancelled",
            entity_type="payment",
            entity_id=str(payment.id),
        )
    )
    await db.delete(payment)
    await db.commit()
    return create_success_response(
        "Test checkout cancelled. You can reschedule or choose another payment method."
    )


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
        provider="cash",
        is_test=appointment.doctor.is_demo,
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
    if payment.provider == "stripe" and payment.provider_reference:
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
        payment.refund_reference = f"{payment.provider}:{payment.id}"
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
    if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if (
            payment.provider != "stripe"
            or obj.get("id") != payment.provider_reference
            or obj.get("amount_total") != int(Decimal(payment.amount) * 100)
            or obj.get("currency") != payment.currency
        ):
            raise SpandanException("PAYMENT_MISMATCH", "Payment details do not match.", 400)
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
