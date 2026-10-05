import asyncio
import hashlib
import hmac
import json
import time
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.time import local_now
from app.db.session import get_db
from app.main import app
from app.models.operations import AccountAction, Notification, Payment
from app.services.account_security import totp
from tests.test_workflows import admin, register, session


async def book(client, headers, schedule, **extra):
    response = await client.post(
        "/api/v1/appointments", headers=headers, json={"schedule_id": schedule["id"], **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_family_ownership_waitlist_and_atomic_reschedule(client, db_session):
    staff, _, first, payload = await session(client, db_session, capacity=2)
    p1, _ = await register(client, "patient", "family")
    p2, _ = await register(client, "patient", "stranger")
    dependent = (
        await client.post(
            "/api/v1/dependents",
            headers=p1,
            json={"full_name": "Family member", "relationship_name": "Child"},
        )
    ).json()["data"]
    forbidden = await client.post(
        "/api/v1/appointments",
        headers=p2,
        json={"schedule_id": first["id"], "dependent_id": dependent["id"]},
    )
    assert forbidden.status_code in (403, 404)
    own = await book(client, p1, first)
    family = await book(client, p1, first, dependent_id=dependent["id"])
    assert family["attendee_name"] == "Family member"
    assert (await client.post(f"/api/v1/waitlist/{first['id']}", headers=p2)).status_code == 201
    second = (
        await client.post(
            "/api/v1/schedules",
            headers=staff,
            json={
                **payload,
                "maximum_patients": 1,
                "schedule_date": str(local_now().date() + timedelta(days=2)),
            },
        )
    ).json()["data"]
    other_booking = await book(client, p2, second)
    failed = await client.post(
        f"/api/v1/appointments/{own['id']}/reschedule",
        headers=p1,
        json={"schedule_id": second["id"]},
    )
    assert failed.status_code in (400, 409)
    await db_session.rollback()
    assert (await client.get(f"/api/v1/appointments/{own['id']}", headers=p1)).json()["data"][
        "appointment_status"
    ] == "booked"
    assert (
        await client.patch(
            f"/api/v1/appointments/{other_booking['id']}/status",
            headers=p2,
            json={"appointment_status": "cancelled"},
        )
    ).status_code == 200
    moved = await client.post(
        f"/api/v1/appointments/{own['id']}/reschedule",
        headers=p1,
        json={"schedule_id": second["id"]},
    )
    assert moved.status_code == 201, moved.text
    notifications = (await client.get("/api/v1/notifications", headers=p2)).json()["data"]
    assert any(row["subject"] == "A booking space is available" for row in notifications)
    assert (
        await client.get(f"/api/v1/appointments/{family['id']}/fhir", headers=p2)
    ).status_code == 403
    resource = (await client.get(f"/api/v1/appointments/{family['id']}/fhir", headers=p1)).json()[
        "data"
    ]
    assert (
        resource["resourceType"] == "Appointment"
        and resource["participant"][0]["actor"]["display"] == "Family member"
    )


async def test_recovery_expiry_attempt_limit_and_session_revocation(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "SMTP_HOST", "test.invalid")
    patient, user = await register(client, "patient", "recovery")
    assert (
        await client.post("/api/v1/auth/forgot-password", json={"email": user["email"]})
    ).status_code == 200
    notice = await db_session.scalar(select(Notification).where(Notification.channel == "email"))
    token = parse_qs(urlparse(notice.message).query)["token"][0]
    payload = {
        "email": user["email"],
        "purpose": "reset",
        "token": token,
        "new_password": "ReplacementPassword123!",
    }
    assert (await client.post("/api/v1/auth/account-action", json=payload)).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=patient)).status_code == 401
    assert (await client.post("/api/v1/auth/account-action", json=payload)).status_code == 400
    action = await db_session.scalar(select(AccountAction))
    action.consumed_at = None
    action.created_at = local_now() - timedelta(minutes=2)
    await db_session.commit()
    for _ in range(5):
        assert (
            await client.post(
                "/api/v1/auth/account-action", json={**payload, "token": "invalidtoken"}
            )
        ).status_code == 400
    assert (await client.post("/api/v1/auth/account-action", json=payload)).status_code == 400
    await db_session.refresh(action)
    assert action.attempts == 5
    action.attempts = 0
    action.expires_at = local_now() - timedelta(seconds=1)
    await db_session.commit()
    assert (await client.post("/api/v1/auth/account-action", json=payload)).status_code == 400


async def test_mfa_replay_and_private_verification_notes(client, db_session):
    staff, doctor, _, _ = await session(client, db_session)
    doctor.verification_notes = "Private review text"
    await db_session.commit()
    assert (
        "verification_notes"
        not in (await client.get(f"/api/v1/doctors/{doctor.id}")).json()["data"]
    )
    a = await admin(client, db_session)
    assert (await client.get("/api/v1/doctors/admin/all", headers=a)).json()["data"][0][
        "verification_notes"
    ] == "Private review text"
    setup = await client.post(
        "/api/v1/auth/mfa/setup", headers=staff, json={"password": "Password123!"}
    )
    secret = setup.json()["data"]["secret"]
    counter = int(time.time() // 30)
    assert (
        await client.post(
            "/api/v1/auth/mfa/enable",
            headers=staff,
            json={"password": "Password123!", "code": totp(secret, counter)},
        )
    ).status_code == 200
    login = {"email": "doctor@example.com", "password": "Password123!"}
    assert (await client.post("/api/v1/auth/login", json=login)).json()["error"][
        "code"
    ] == "MFA_REQUIRED"
    assert (
        await client.post("/api/v1/auth/login", json={**login, "mfa_code": totp(secret, counter)})
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", json={**login, "mfa_code": totp(secret, counter + 1)}
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/auth/login", json={**login, "mfa_code": totp(secret, counter + 1)}
        )
    ).status_code == 401


async def test_cash_receipts_refunds_and_signed_payment_mismatch(client, db_session, monkeypatch):
    staff, _, schedule, _ = await session(client, db_session)
    patient, _ = await register(client, "patient", "cash")
    booking = await book(client, patient, schedule)
    assert (
        await client.post(
            f"/api/v1/payments/appointment/{booking['id']}/cash", headers=patient, json={}
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/payments/appointment/{booking['id']}/cash", headers=staff, json={}
        )
    ).status_code == 200
    payment = await db_session.scalar(select(Payment))
    assert (
        await client.get(f"/api/v1/payments/{payment.id}/receipt", headers=patient)
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/payments/{payment.id}/refund", headers=staff)
    ).status_code == 409
    await db_session.rollback()
    await db_session.refresh(payment)
    await client.patch(
        f"/api/v1/appointments/{booking['id']}/status",
        headers=patient,
        json={"appointment_status": "cancelled"},
    )
    assert (
        await client.post(f"/api/v1/payments/{payment.id}/refund", headers=staff)
    ).status_code == 200
    await db_session.refresh(payment)
    assert payment.status == "refunded"
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "test-webhook-secret")
    payment.status, payment.provider_reference, payment.provider = "pending", "cs_test_expected", "stripe"
    await db_session.commit()
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_wrong",
                "metadata": {"payment_id": str(payment.id)},
                "amount_total": 50000,
                "currency": "bdt",
                "payment_status": "paid",
            }
        },
    }
    raw = json.dumps(event).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(
        settings.STRIPE_WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    headers = {
        "stripe-signature": f"t={timestamp},v1={signature}",
        "content-type": "application/json",
    }
    assert (
        await client.post("/api/v1/payments/webhook", content=raw, headers=headers)
    ).status_code == 400
    await db_session.refresh(payment)
    assert payment.status == "pending"


async def test_walkin_holidays_and_privacy_anonymization(client, db_session):
    staff, _, schedule, _ = await session(client, db_session)
    response = await client.post(
        "/api/v1/appointments/intake",
        headers=staff,
        json={"schedule_id": schedule["id"], "full_name": "Walk in", "phone_number": "01898765432"},
    )
    assert response.status_code == 201, response.text
    holiday = str(local_now().date() + timedelta(days=7))
    assert (
        await client.post(
            "/api/v1/availability/exceptions",
            headers=staff,
            json={"exception_date": holiday, "reason": "Holiday"},
        )
    ).status_code == 201
    conflict = await client.post(
        "/api/v1/schedules",
        headers=staff,
        json={
            "chamber_id": schedule["chamber_id"],
            "schedule_date": holiday,
            "start_time": "09:00",
            "end_time": "12:00",
            "maximum_patients": 4,
        },
    )
    assert conflict.status_code == 409
    await db_session.rollback()
    patient, _ = await register(client, "patient", "privacy")
    booking = await book(client, patient, schedule, patient_note="Private note")
    request = (
        await client.post("/api/v1/privacy/requests", headers=patient, json={"kind": "deletion"})
    ).json()["data"]
    a = await admin(client, db_session)
    assert (
        await client.post(f"/api/v1/privacy/requests/{request['id']}/resolve", headers=a)
    ).status_code == 409
    await db_session.rollback()
    await client.patch(
        f"/api/v1/appointments/{booking['id']}/status",
        headers=patient,
        json={"appointment_status": "cancelled"},
    )
    assert (
        await client.post(f"/api/v1/privacy/requests/{request['id']}/resolve", headers=a)
    ).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=patient)).status_code in (401, 403)


async def test_postgresql_concurrent_capacity_and_overlap(client, db_session):
    from tests.conftest import TEST_DATABASE_URL, test_async_session_maker

    if TEST_DATABASE_URL.startswith("sqlite"):
        pytest.skip("PostgreSQL row-lock integration test")
    staff, _, schedule, payload = await session(client, db_session, capacity=1)
    p1, _ = await register(client, "patient", "race1")
    p2, _ = await register(client, "patient", "race2")

    async def independent_db():
        async with test_async_session_maker() as db:
            try:
                yield db
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = independent_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        bookings = await asyncio.gather(
            *[
                ac.post("/api/v1/appointments", headers=h, json={"schedule_id": schedule["id"]})
                for h in (p1, p2)
            ]
        )
        assert sorted(r.status_code for r in bookings) == [201, 400]
        next_payload = {
            **payload,
            "maximum_patients": 3,
            "schedule_date": str(local_now().date() + timedelta(days=3)),
        }
        sessions = await asyncio.gather(
            *[ac.post("/api/v1/schedules", headers=staff, json=next_payload) for _ in range(2)]
        )
        assert sorted(r.status_code for r in sessions) == [201, 409]
        more = next(r.json()["data"] for r in sessions if r.status_code == 201)
        first = await book(ac, p1, more)
        second = await book(ac, p2, more)
        calls = await asyncio.gather(
            *[
                ac.post(f"/api/v1/schedules/{more['id']}/queue/increment", headers=staff)
                for _ in range(2)
            ]
        )
        assert all(r.status_code == 200 for r in calls)
        roster = (
            await ac.get(f"/api/v1/appointments/schedule/{more['id']}", headers=staff)
        ).json()["data"]
        assert [row["appointment_status"] for row in roster] == ["completed", "in_consultation"]
        assert roster[0]["id"] == first["id"] and roster[1]["id"] == second["id"]


async def test_queue_only_permission_and_location_fee_filters(client, db_session):
    from app.models.doctor import AssistantAssignment

    staff, doctor, schedule, _ = await session(client, db_session)
    patient, _ = await register(client, "patient", "queueonly")
    booking = await book(client, patient, schedule)
    response = await client.post(
        "/api/v1/auth/register/assistant",
        headers=staff,
        json={
            "email": "assistantqueue@example.com",
            "password": "Password123!",
            "phone_number": "+8801812349876",
            "full_name": "Queue assistant",
            "doctor_id": str(doctor.id),
        },
    )
    assert response.status_code == 201, response.text
    assistant = {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
    assignment = await db_session.scalar(select(AssistantAssignment))
    assignment.can_manage_appointments = assignment.can_manage_schedules = False
    assignment.can_update_queue = True
    await db_session.commit()
    assert (
        await client.get(f"/api/v1/appointments/schedule/{schedule['id']}", headers=assistant)
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/appointments/{booking['id']}/status",
            headers=assistant,
            json={"appointment_status": "checked_in"},
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/appointments",
            headers=assistant,
            json={"schedule_id": schedule["id"], "patient_phone": "+8801712340000"},
        )
    ).status_code == 403
    assert (
        len(
            (
                await client.get(
                    "/api/v1/doctors",
                    params={
                        "district": "Dhaka",
                        "max_fee": 500,
                        "available_on": schedule["schedule_date"],
                    },
                )
            ).json()["data"]
        )
        == 1
    )
    assert (
        await client.get(
            "/api/v1/doctors",
            params={"district": "Chattogram", "available_on": schedule["schedule_date"]},
        )
    ).json()["data"] == []
