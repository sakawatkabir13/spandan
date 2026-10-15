"""Shared payment mutations used by website routes and confirmed chat actions."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import httpx
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import SpandanException, create_success_response
from app.models.appointment import AppointmentStatus
from app.models.operations import Payment
from app.models.user import UserRole
from app.repositories.appointment import appointment_repo
from app.repositories.user import patient_repo
from app.services.permissions import require_doctor_access


class CashBody(BaseModel):
    method: str = "cash"


async def authorize(db, user, appointment_id, staff_only=False):
    appointment = await appointment_repo.get_by_id_with_details(db, appointment_id)
    if not appointment:
        raise SpandanException("NOT_FOUND", "Appointment not found.", 404)
    if user.role == UserRole.PATIENT and (not staff_only):
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


async def checkout(appointment_id: UUID, user, db, *, commit: bool = True, payment_id=None):
    if user.role not in (UserRole.PATIENT,):
        raise SpandanException("FORBIDDEN", "This payment action is not permitted.", 403)
    appointment = await authorize(db, user, appointment_id)
    if appointment.appointment_status in (AppointmentStatus.CANCELLED, AppointmentStatus.ABSENT):
        raise SpandanException("CONFLICT", "This appointment cannot be paid.", 409)
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise SpandanException(
            "PAYMENTS_UNAVAILABLE", "Online payment is not enabled. Pay at the chamber.", 503
        )
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
        from uuid import uuid4

        payment = Payment(
            id=payment_id or uuid4(),
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
            return create_success_response("Continue to secure checkout.", {"url": existing["url"]})
        if existing.get("status") == "complete":
            raise SpandanException(
                "PAYMENT_PROCESSING",
                "Stripe is confirming your payment. Refresh the payment status shortly.",
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
            "payment_method_types[0]": "card",
            "success_url": f"{settings.FRONTEND_URL}/dashboard/patient/tools?tab=billing&appointment_id={appointment.id}&checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.FRONTEND_URL}/dashboard/patient/tools?tab=billing&appointment_id={appointment.id}&checkout=cancelled",
            "client_reference_id": str(appointment.id),
            "customer_email": user.email,
            "metadata[payment_id]": str(payment.id),
            "payment_intent_data[metadata][payment_id]": str(payment.id),
            "line_items[0][price_data][currency]": payment.currency,
            "line_items[0][price_data][unit_amount]": str(amount),
            "line_items[0][price_data][product_data][name]": "Spandan consultation",
            "line_items[0][quantity]": "1",
        },
        f"checkout:{payment.id}:{payment.checkout_attempt}",
    )
    if session.get("livemode") is True or not session.get("id") or (not session.get("url")):
        raise SpandanException(
            "PAYMENT_PROVIDER_ERROR", "Expected a Stripe test checkout session.", 502
        )
    payment.provider_reference = session["id"]
    await db.flush()
    if commit:
        await db.commit()
    else:
        await db.flush()
    return create_success_response("Continue to secure checkout.", {"url": session["url"]})


async def cancel_checkout(id: UUID, user, db, *, commit: bool = True):
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
                key=f"expire:{payment.id}:{payment.checkout_attempt}",
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
    await db.flush()
    if commit:
        await db.commit()
    else:
        await db.flush()
    return create_success_response(
        "Checkout cancelled. You can reschedule or choose another payment method."
    )


async def record_cash(appointment_id: UUID, request: CashBody, user, db, *, commit: bool = True):
    if user.role not in (UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR):
        raise SpandanException("FORBIDDEN", "This payment action is not permitted.", 403)
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
    await db.flush()
    if commit:
        await db.commit()
    else:
        await db.flush()
    return create_success_response("Payment recorded. A receipt is available.")


async def refund(id: UUID, user, db, *, commit: bool = True):
    if user.role not in (UserRole.DOCTOR, UserRole.ADMINISTRATOR):
        raise SpandanException("FORBIDDEN", "This payment action is not permitted.", 403)
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
    await db.flush()
    if commit:
        await db.commit()
    else:
        await db.flush()
    return create_success_response(
        "Refund recorded. For cash payments, the chamber must return the money to the patient."
    )
