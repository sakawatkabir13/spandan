from unittest.mock import AsyncMock
from uuid import UUID

from sqlalchemy import select

from app.api.routes import payments
from app.core.config import settings
from app.models.operations import Payment
from tests.test_operations import book
from tests.test_workflows import register, session


async def test_billing_selection_and_verified_checkout_return(client, db_session, monkeypatch):
    doctor, _, schedule, _ = await session(client, db_session)
    patient, user = await register(client, "patient", "billing-patient")
    other, _ = await register(client, "patient", "billing-other")
    appointment = await book(client, patient, schedule)
    listed = (await client.get("/api/v1/payments/appointments", headers=patient)).json()["data"]
    assert len(listed) == 1 and listed[0]["id"] == appointment["id"]
    assert listed[0]["payment_status"] == "unpaid"
    assert (await client.get("/api/v1/payments/appointments", headers=other)).json()["data"] == []
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_synthetic")
    provider = AsyncMock(return_value={"id": "cs_test_verified", "url": "https://checkout.stripe.com/test", "livemode": False})
    monkeypatch.setattr(payments, "stripe", provider)
    checkout_url = f"/api/v1/payments/appointment/{appointment['id']}/checkout"
    assert (await client.post(checkout_url, headers=doctor)).status_code == 403
    assert (await client.post(checkout_url, headers=patient)).status_code == 200
    sent = provider.call_args.args[2]
    assert sent["customer_email"] == user["email"]
    assert sent["client_reference_id"] == appointment["id"]
    assert f"appointment_id={appointment['id']}" in sent["success_url"]
    assert "{CHECKOUT_SESSION_ID}" in sent["success_url"]
    payment = await db_session.scalar(select(Payment).where(Payment.appointment_id == UUID(appointment["id"])))
    refresh_url = f"/api/v1/payments/{payment.id}/refresh"
    assert (await client.post(refresh_url, headers=other)).status_code == 403
    # A successful return URL or an unpaid provider session cannot mark a payment paid.
    assert (await client.get(f"/api/v1/payments/appointment/{appointment['id']}?checkout=success", headers=patient)).json()["data"]["payment"]["status"] == "pending"
    response = {"id": "cs_test_verified", "status": "complete", "payment_status": "unpaid", "amount_total": 50000, "currency": "bdt", "livemode": False}
    provider.return_value = response
    assert (await client.post(refresh_url, headers=patient)).json()["data"]["status"] == "pending"
    provider.return_value = {**response, "payment_status": "paid", "amount_total": 1}
    assert (await client.post(refresh_url, headers=patient)).status_code == 409
    await db_session.rollback()
    provider.return_value = {**response, "payment_status": "paid"}
    assert (await client.post(refresh_url, headers=patient)).json()["data"]["status"] == "paid"
    assert (await client.post(refresh_url, headers=patient)).json()["data"]["status"] == "paid"
    details = (await client.get(f"/api/v1/payments/appointment/{appointment['id']}", headers=patient)).json()["data"]
    assert not details["can_pay"] and details["appointment"]["doctor_name"]
    receipt = (await client.get(f"/api/v1/payments/{details['payment']['id']}/receipt", headers=patient)).json()["data"]
    assert receipt["patient_name"] == user["patient_profile"]["full_name"]
    assert receipt["doctor_name"] and receipt["chamber_name"] and receipt["is_test"]


async def test_cancelled_appointment_cannot_start_payment(client, db_session):
    _, _, schedule, _ = await session(client, db_session)
    patient, _ = await register(client, "patient", "billing-cancel")
    appointment = await book(client, patient, schedule)
    await client.patch(f"/api/v1/appointments/{appointment['id']}/status", headers=patient, json={"appointment_status": "cancelled"})
    details = (await client.get(f"/api/v1/payments/appointment/{appointment['id']}", headers=patient)).json()["data"]
    assert not details["can_pay"]
    assert (await client.post(f"/api/v1/payments/appointment/{appointment['id']}/checkout", headers=patient)).status_code == 409
