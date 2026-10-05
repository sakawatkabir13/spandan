import hashlib
import hmac
import json
import time
from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import Settings, settings
from app.core.time import local_now
from app.models.chamber import Chamber
from app.models.doctor import DoctorProfile, Specialization
from app.models.operations import Payment
from app.models.schedule import Schedule
from app.models.user import User
from app.services.mail import send_email as smtp_send_email
from scripts.import_directory import load_dataset
from scripts.seed_demo_directory import save_credentials, seed_demo_accounts
from tests.test_operations import book
from tests.test_workflows import admin, register, session


async def test_demo_seed_is_idempotent_and_disable_blocks_booking(
    client, db_session, monkeypatch, tmp_path
):
    rows = load_dataset()
    credentials = {}
    with pytest.raises(ValueError):
        await seed_demo_accounts(db_session, rows, credentials)
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    start = local_now().date() + timedelta(days=1)
    counts = await seed_demo_accounts(db_session, rows, credentials, start, 2)
    await db_session.commit()
    assert counts == {"accounts_created": len(rows), "sessions_created": len(rows) * 2}
    path = tmp_path / "private.json"
    save_credentials(path, credentials)
    assert path.stat().st_mode & 0o777 == 0o600
    snapshot = dict(credentials)
    assert await seed_demo_accounts(db_session, rows, credentials, start, 2) == {
        "accounts_created": 0,
        "sessions_created": 0,
    }
    await db_session.commit()
    assert credentials == snapshot
    for model in (User, DoctorProfile, Chamber):
        assert await db_session.scalar(select(func.count()).select_from(model)) == len(rows)
    specs = set(await db_session.scalars(select(Specialization.name)))
    assert {
        "General Medicine",
        "Cardiology",
        "Pediatrics",
        "Gynecology and Obstetrics",
        "Neurology",
        "Orthopedics",
        "Dermatology",
        "Gastroenterology",
        "Pulmonology / Respiratory Medicine",
        "Nephrology",
        "Endocrinology",
        "ENT",
        "Ophthalmology",
        "Psychiatry",
        "Emergency Medicine / ER",
    } <= specs
    listing = (await client.get("/api/v1/directory/doctors?query=Ekramuddaula")).json()["data"][
        "items"
    ][0]
    doctor_id = listing["demo_doctor_id"]
    assert listing["booking_status"] == "demo_only"
    profile = (await client.get(f"/api/v1/doctors/{doctor_id}")).json()["data"]
    assert profile["is_demo"] and profile["medical_registration_number"].startswith("DEMO-")
    ent = await db_session.scalar(select(Specialization).where(Specialization.name == "ENT"))
    assert (await client.get(f"/api/v1/directory/doctors?specialization_id={ent.id}")).json()[
        "data"
    ]["total"] >= 1
    assert (await client.get("/api/v1/directory/doctors?query=চোখ")).json()["data"]["total"] >= 1
    schedules = (await client.get(f"/api/v1/schedules/doctor/{doctor_id}")).json()["data"]
    login = credentials[next(r.listing_key for r in rows if "ekramuddaula" in r.listing_key)]
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": login["email"], "password": login["password"]}
        )
    ).status_code == 200
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert (await client.get("/api/v1/doctors")).json()["data"] == []
    assert (await client.get(f"/api/v1/doctors/{doctor_id}")).status_code == 404
    assert (await client.get(f"/api/v1/schedules/doctor/{doctor_id}")).json()["data"] == []
    assert (await client.get(f"/api/v1/directory/doctors/{listing['id']}")).json()["data"][
        "demo_doctor_id"
    ] is None
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": login["email"], "password": login["password"]}
        )
    ).status_code == 403
    patient, _ = await register(client, "patient", "disabled-demo")
    assert (
        await client.post(
            "/api/v1/appointments", headers=patient, json={"schedule_id": schedules[0]["id"]}
        )
    ).status_code == 400


async def test_simulator_ownership_decline_receipt_refund(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    await seed_demo_accounts(
        db_session, load_dataset()[:1], {}, local_now().date() + timedelta(days=1), 1
    )
    await db_session.commit()
    schedule = await db_session.scalar(select(Schedule))
    patient, _ = await register(client, "patient", "demo-paying")
    other, _ = await register(client, "patient", "demo-stranger")
    appointment = await book(client, patient, {"id": str(schedule.id)})
    path = f"/api/v1/payments/appointment/{appointment['id']}/demo"
    assert (await client.post(path, headers=other, json={})).status_code == 403
    assert (await client.post(path, headers=patient, json={"outcome": "declined"})).json()["data"][
        "outcome"
    ] == "declined"
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 0
    assert (await client.post(path, headers=patient, json={})).status_code == 200
    assert (await client.post(path, headers=patient, json={})).status_code == 409
    payment = await db_session.scalar(select(Payment))
    assert payment.provider == "demo" and payment.is_test and not payment.provider_reference
    assert (
        await client.get(f"/api/v1/payments/{payment.id}/receipt", headers=other)
    ).status_code == 403
    receipt = (await client.get(f"/api/v1/payments/{payment.id}/receipt", headers=patient)).json()[
        "data"
    ]
    assert receipt["is_test"] and receipt["is_demo"]
    await client.patch(
        f"/api/v1/appointments/{appointment['id']}/status",
        headers=patient,
        json={"appointment_status": "cancelled"},
    )
    a = await admin(client, db_session)
    assert (
        await client.post(f"/api/v1/payments/{payment.id}/refund", headers=a)
    ).status_code == 200
    await db_session.refresh(payment)
    assert payment.status == "refunded"


async def test_stripe_checkout_reuse_retry_webhook_and_refund(client, db_session, monkeypatch):
    from app.api.routes import payments

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_synthetic")
    staff, _, schedule, _ = await session(client, db_session)
    patient, _ = await register(client, "patient", "stripe-test")
    appointment = await book(client, patient, schedule)
    requests = []
    state = {"status": "open"}

    async def provider(method, path, data=None, key=None):
        requests.append((method, path, data, key))
        if path == "refunds":
            return {"id": "re_test", "status": "succeeded"}
        return {
            "id": "cs_test",
            "url": "https://checkout.stripe.com/test",
            "status": state["status"],
            "payment_intent": "pi_test",
            "livemode": False,
        }

    monkeypatch.setattr(payments, "stripe", provider)
    url = f"/api/v1/payments/appointment/{appointment['id']}/checkout"
    assert (await client.post(url, headers=patient)).status_code == 200
    assert (await client.post(url, headers=patient)).status_code == 200
    assert len([r for r in requests if r[0] == "POST"]) == 1
    state["status"] = "expired"
    assert (await client.post(url, headers=patient)).status_code == 200
    keys = [r[3] for r in requests if r[0] == "POST"]
    assert len(set(keys)) == 2
    payment = await db_session.scalar(select(Payment))
    assert payment.provider == "stripe" and payment.is_test

    async def deliver(event):
        raw = json.dumps(event).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(
            settings.STRIPE_WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
        return await client.post(
            "/api/v1/payments/webhook",
            content=raw,
            headers={"stripe-signature": f"t={timestamp},v1={signature}"},
        )

    assert (await deliver({"type": "customer.created", "data": {"object": {}}})).status_code == 200
    assert (await deliver({"livemode": True, "data": {"object": {}}})).status_code == 400
    event = {
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_test",
                "amount_total": int(payment.amount * 100),
                "currency": payment.currency,
                "payment_status": "paid",
                "metadata": {"payment_id": str(payment.id)},
            }
        },
    }
    unpaid = json.loads(json.dumps(event))
    unpaid["data"]["object"]["payment_status"] = "unpaid"
    assert (await deliver(unpaid)).status_code == 200
    await db_session.refresh(payment)
    assert payment.status == "pending"
    assert (await deliver(event)).status_code == 200
    await db_session.refresh(payment)
    paid_at = payment.paid_at
    assert (await deliver(event)).status_code == 200
    await db_session.refresh(payment)
    assert payment.paid_at == paid_at
    await client.patch(
        f"/api/v1/appointments/{appointment['id']}/status",
        headers=patient,
        json={"appointment_status": "cancelled"},
    )
    assert (
        await client.post(f"/api/v1/payments/{payment.id}/refund", headers=staff)
    ).status_code == 200
    assert (await deliver(event)).status_code == 200
    await db_session.refresh(payment)
    assert payment.status == "refunded"


def test_test_only_keys_and_google_smtp_readiness(monkeypatch):
    with pytest.raises(ValidationError):
        Settings(STRIPE_SECRET_KEY="sk_live_forbidden", _env_file=None)
    config = Settings(
        SMTP_HOST="smtp.gmail.com",
        SMTP_USERNAME="community.cuetinsights@gmail.com",
        SMTP_PASSWORD="",
        _env_file=None,
    )
    assert not config.email_enabled
    config.SMTP_PASSWORD = "synthetic-app-password"
    assert config.email_enabled
    from app.services import mail

    calls = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, **kwargs):
            assert kwargs["context"].check_hostname

        def login(self, username, password):
            calls.append((username, password))

        def send_message(self, message):
            calls.append(message["To"])

    monkeypatch.setattr(mail, "settings", config)
    monkeypatch.setattr(mail, "send_email", smtp_send_email)
    monkeypatch.setattr(mail.smtplib, "SMTP", SMTP)
    mail.send_email("patient@example.com", "Test", "Synthetic test only")
    assert "patient@example.com" in calls
    with pytest.raises(ValueError):
        mail.send_email("fixture@demo.spandan.example.com", "Test", "Test")


async def test_cancel_pending_stripe_checkout_allows_rescheduling(client, db_session, monkeypatch):
    from app.api.routes import payments

    staff, _, schedule, payload = await session(client, db_session)
    patient, _ = await register(client, "patient", "stripe-cancel")
    other, _ = await register(client, "patient", "stripe-cancel-other")
    appointment = await book(client, patient, schedule)
    second = (
        await client.post(
            "/api/v1/schedules",
            headers=staff,
            json={**payload, "schedule_date": str(local_now().date() + timedelta(days=2))},
        )
    ).json()["data"]
    payment = Payment(
        appointment_id=UUID(appointment["id"]),
        amount=500,
        currency="bdt",
        provider="stripe",
        is_test=True,
        provider_reference="cs_cancel",
    )
    db_session.add(payment)
    await db_session.commit()
    calls = []

    async def provider(method, path, data=None, key=None):
        calls.append((method, path))
        return {"status": "open" if method == "GET" else "expired"}

    monkeypatch.setattr(payments, "stripe", provider)
    path = f"/api/v1/payments/{payment.id}/cancel-checkout"
    assert (await client.post(path, headers=other)).status_code == 403
    assert (await client.post(path, headers=patient)).status_code == 200
    assert calls == [
        ("GET", "checkout/sessions/cs_cancel"),
        ("POST", "checkout/sessions/cs_cancel/expire"),
    ]
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 0
    assert (
        await client.post(
            f"/api/v1/appointments/{appointment['id']}/reschedule",
            headers=patient,
            json={"schedule_id": second["id"]},
        )
    ).status_code == 201
