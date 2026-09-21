from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.core.time import local_now
from app.models.audit import AuditLog
from app.models.doctor import AssistantAssignment, DoctorProfile, DoctorVerificationStatus
from app.models.user import User, UserRole
from app.schemas.ai import SymptomCheckRequest
from app.services.ai import triage_service


async def register(client, role, suffix):
    payload = dict(
        email=f"{suffix}@example.com", password="Password123!", full_name=f"Test {suffix}"
    )
    # Allocate a distinct valid number independently of alphanumeric suffixes.
    payload["phone_number"] = "+88017" + str(
        int.from_bytes(suffix.encode(), "big") % 100000000
    ).zfill(8)
    if role == "doctor":
        payload["medical_registration_number"] = f"BMDC-{suffix}"
    response = await client.post(f"/api/v1/auth/register/{role}", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def session(client, db, capacity=3):
    headers, user = await register(client, "doctor", "doctor")
    doctor = await db.get(DoctorProfile, UUID(user["doctor_profile"]["id"]))
    doctor.verification_status = DoctorVerificationStatus.APPROVED
    await db.commit()
    chamber = await client.post(
        "/api/v1/chambers",
        headers=headers,
        json=dict(
            name="Test chamber",
            address="Dhaka Road 10",
            district="Dhaka",
            area="Dhanmondi",
            consultation_fee=500,
            follow_up_fee=300,
        ),
    )
    assert chamber.status_code == 201, chamber.text
    payload = dict(
        chamber_id=chamber.json()["data"]["id"],
        schedule_date=str(local_now().date() + timedelta(days=1)),
        start_time="17:00:00",
        end_time="21:00:00",
        maximum_patients=capacity,
    )
    response = await client.post("/api/v1/schedules", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return headers, doctor, response.json()["data"], payload


async def admin(client, db):
    user = User(
        email="admin@example.com",
        role=UserRole.ADMINISTRATOR,
        password_hash=get_password_hash("Password123!"),
    )
    db.add(user)
    await db.commit()
    resp = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "Password123!"}
    )
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


async def test_verification_and_dashboard_contracts(client, db_session):
    doctor_headers, user = await register(client, "doctor", "pending")
    doctor_id = user["doctor_profile"]["id"]
    assert (await client.get(f"/api/v1/doctors/{doctor_id}")).status_code == 404
    assert (
        await client.get("/api/v1/doctors/admin/all", headers=doctor_headers)
    ).status_code == 403
    admin_headers = await admin(client, db_session)
    registry = await client.get("/api/v1/doctors/admin/all", headers=admin_headers)
    assert registry.json()["data"][0]["verification_status"] == "pending"
    approval = await client.post(
        f"/api/v1/doctors/{doctor_id}/verify", headers=admin_headers, json={"status": "approved"}
    )
    assert approval.status_code == 200
    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "doctor.verification_updated")
    )
    assert audit is not None
    assert audit.metadata_json["new_status"] == "approved"
    assert (await client.get("/api/v1/doctors")).json()["data"][0]["full_name"] == "Test pending"
    assert (await client.get("/api/v1/chambers/me", headers=doctor_headers)).json()["data"] == []
    assert (await client.get("/api/v1/schedules/me", headers=doctor_headers)).json()["data"] == []


async def test_booking_cancel_rebook_queue_and_timezone(client, db_session):
    staff, doctor, schedule, _ = await session(client, db_session, capacity=2)
    p1, u1 = await register(client, "patient", "one")
    p2, _ = await register(client, "patient", "two")
    sid = schedule["id"]
    first = (
        await client.post("/api/v1/appointments", headers=p1, json={"schedule_id": sid})
    ).json()["data"]
    second = (
        await client.post("/api/v1/appointments", headers=p2, json={"schedule_id": sid})
    ).json()["data"]
    confirmed = await client.patch(
        f"/api/v1/appointments/{first['id']}/status",
        headers=p1,
        json={"appointment_status": "confirmed"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["appointment_status"] == "confirmed"
    assert (
        await client.patch(
            f"/api/v1/appointments/{first['id']}/status",
            headers=p2,
            json={"appointment_status": "cancelled"},
        )
    ).status_code == 403
    assert first["doctor"]["full_name"] == doctor.full_name
    assert first["chamber"]["name"] == "Test chamber"
    assert first["patient"]["full_name"] == "Test one"
    assert "T11:00:00" in first["estimated_consultation_at"]  # 17:00 Dhaka = 11:00 UTC
    cancelled = await client.patch(
        f"/api/v1/appointments/{second['id']}/status",
        headers=p2,
        json={"appointment_status": "cancelled"},
    )
    assert cancelled.status_code == 200
    rebooked = await client.post("/api/v1/appointments", headers=p2, json={"schedule_id": sid})
    assert rebooked.status_code == 201, rebooked.text
    assert rebooked.json()["data"]["serial_number"] == 3
    invalid_completion = await client.patch(
        f"/api/v1/appointments/{first['id']}/status",
        headers=staff,
        json={"appointment_status": "completed"},
    )
    assert invalid_completion.status_code == 409
    assert "cannot move" in invalid_completion.json()["error"]["message"]
    tracking = (await client.get(f"/api/v1/appointments/track/{sid}", headers=p2)).json()["data"]
    assert tracking["people_ahead"] == 1  # cancelled serial 2 is not counted
    called = await client.post(f"/api/v1/schedules/{sid}/queue/increment", headers=staff)
    assert called.json()["data"]["current_serial"] == 1
    called = await client.post(f"/api/v1/schedules/{sid}/queue/increment", headers=staff)
    assert called.json()["data"]["current_serial"] == 3
    roster = (await client.get(f"/api/v1/appointments/schedule/{sid}", headers=staff)).json()[
        "data"
    ]
    assert roster[0]["appointment_status"] == "completed"
    reopen = await client.patch(
        f"/api/v1/appointments/{first['id']}/status",
        headers=staff,
        json={"appointment_status": "booked"},
    )
    assert reopen.status_code == 409


async def test_staff_permissions_and_assistant_registration(client, db_session):
    staff, doctor, schedule, _ = await session(client, db_session)
    patient, user = await register(client, "patient", "patient")
    other, _ = await register(client, "doctor", "otherdoc")
    payload = dict(
        email="assistant@example.com",
        password="Password123!",
        phone_number="+8801812345678",
        full_name="Assistant",
        doctor_id=str(doctor.id),
    )
    assert (await client.post("/api/v1/auth/register/assistant", json=payload)).status_code == 401
    assert (
        await client.post("/api/v1/auth/register/assistant", headers=other, json=payload)
    ).status_code == 403
    response = await client.post("/api/v1/auth/register/assistant", headers=staff, json=payload)
    assert response.status_code == 201, response.text
    assistant = {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
    assert len((await client.get("/api/v1/schedules/me", headers=assistant)).json()["data"]) == 1
    booking = dict(
        schedule_id=schedule["id"],
        patient_id=user["patient_profile"]["id"],
        booking_source="walk_in",
    )
    assert (
        await client.post("/api/v1/appointments", headers=other, json=booking)
    ).status_code == 403
    assert (
        await client.post("/api/v1/appointments", headers=assistant, json=booking)
    ).status_code == 201
    assignment = await db_session.scalar(
        select(AssistantAssignment).where(AssistantAssignment.doctor_id == doctor.id)
    )
    assignment.can_update_queue = False
    await db_session.commit()
    assert (
        await client.post(f"/api/v1/schedules/{schedule['id']}/queue/increment", headers=assistant)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/appointments/schedule/{schedule['id']}", headers=patient)
    ).status_code == 403


async def test_validation_overlaps_and_session_cancel(client, db_session):
    staff, doctor, schedule, payload = await session(client, db_session)
    bad = await client.post(
        "/api/v1/schedules", headers=staff, json={**payload, "end_time": "16:00:00"}
    )
    assert bad.status_code == 422, bad.text
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"
    assert (await client.post("/api/v1/schedules", headers=staff, json=payload)).status_code == 409
    patient, _ = await register(client, "patient", "patient")
    assert (
        await client.post(
            "/api/v1/appointments", headers=patient, json={"schedule_id": schedule["id"]}
        )
    ).status_code == 201
    cancelled = await client.patch(
        f"/api/v1/schedules/{schedule['id']}",
        headers=staff,
        json={"status": "cancelled", "cancellation_reason": "Doctor unavailable"},
    )
    assert cancelled.status_code == 200, cancelled.text
    mine = (await client.get("/api/v1/appointments/me", headers=patient)).json()["data"][0]
    assert mine["appointment_status"] == "cancelled"
    assert mine["cancellation_reason"] == "Doctor unavailable"


async def test_recurring_schedule_creation_is_atomic_and_audited(client, db_session):
    staff, _, _, payload = await session(client, db_session)
    start = local_now().date() + timedelta(days=2)
    end = start + timedelta(days=6)
    recurring = {
        "chamber_id": payload["chamber_id"],
        "start_date": str(start),
        "end_date": str(end),
        "weekdays": list(range(7)),
        "start_time": "09:00:00",
        "end_time": "11:00:00",
        "maximum_patients": 12,
        "average_consultation_minutes": 10,
    }
    created = await client.post("/api/v1/schedules/recurring", headers=staff, json=recurring)
    assert created.status_code == 201, created.text
    assert len(created.json()["data"]) == 7
    assert {item["schedule_date"] for item in created.json()["data"]} == {
        str(start + timedelta(days=offset)) for offset in range(7)
    }

    duplicate = await client.post("/api/v1/schedules/recurring", headers=staff, json=recurring)
    assert duplicate.status_code == 409
    count = len((await client.get("/api/v1/schedules/me", headers=staff)).json()["data"])
    assert count == 8
    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "schedule.recurring_created")
    )
    assert audit is not None
    assert audit.metadata_json["created_count"] == 7


async def test_public_triage_and_bad_phone(client):
    triage = await client.post(
        "/api/v1/ai/symptom-check", json={"symptoms_text": "Mild sore throat for three days"}
    )
    assert triage.status_code == 201
    assert triage.json()["data"]["patient_id"] is None
    invalid = await client.post(
        "/api/v1/auth/register/patient",
        json=dict(
            email="bad@example.com",
            password="Password123!",
            phone_number="abcdefghijk",
            full_name="Bad number",
        ),
    )
    assert invalid.status_code == 422
    assert "password" not in str(invalid.json()["error"]["details"])


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        '{"recommended_specialization_name":null}',
        '{"recommended_specialization_name":"Cardiology","urgency_level":"oops","reasoning_summary":"x","safety_message":"x"}',
    ],
)
async def test_invalid_ai_output_falls_back(content, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    response = __import__("httpx").Response(
        200, json={"choices": [{"message": {"content": content}}]}
    )
    with patch("app.services.ai.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__.return_value.post = AsyncMock(return_value=response)
        result = await triage_service._call_groq_or_fallback(
            SymptomCheckRequest(symptoms_text="Mild headache"), ["Cardiology"]
        )
    assert result["model_identifier"] == "fallback-general-medicine"


async def test_account_access_and_password_session_revocation(client, db_session):
    patient, user = await register(client, "patient", "account")
    admin_headers = await admin(client, db_session)
    assert (await client.get("/api/v1/users", headers=patient)).status_code == 403
    assert (await client.get("/api/v1/users", headers=admin_headers)).status_code == 200
    assert (await client.get("/api/v1/users/audit-logs", headers=patient)).status_code == 403
    disabled = await client.patch(
        f"/api/v1/users/{user['id']}", headers=admin_headers, json={"is_active": False}
    )
    assert disabled.status_code == 200
    status_audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user.status_updated")
    )
    assert status_audit is not None
    assert status_audit.metadata_json["new_is_active"] is False
    logs = await client.get("/api/v1/users/audit-logs", headers=admin_headers)
    assert logs.status_code == 200
    assert logs.json()["data"][0]["action"] == "user.status_updated"
    assert (await client.get("/api/v1/auth/me", headers=patient)).status_code == 403
    await client.patch(
        f"/api/v1/users/{user['id']}", headers=admin_headers, json={"is_active": True}
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": "Password123!"}
    )
    refresh = login.json()["data"]["refresh_token"]
    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=patient,
        json={"current_password": "Password123!", "new_password": "NewPassword123!"},
    )
    assert changed.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=patient)).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": user["email"], "password": "NewPassword123!"}
        )
    ).status_code == 200


async def test_profile_updates_and_pending_schedule(client, db_session):
    patient, _ = await register(client, "patient", "profile")
    assert (
        await client.patch("/api/v1/patients/me", headers=patient, json={"full_name": None})
    ).status_code == 422
    assert (
        await client.patch(
            "/api/v1/patients/me",
            headers=patient,
            json={"date_of_birth": None, "address": "New address"},
        )
    ).status_code == 200
    doctor, user = await register(client, "doctor", "notverified")
    chamber = await client.post(
        "/api/v1/chambers",
        headers=doctor,
        json={
            "name": "Draft chamber",
            "address": "Dhaka Road 10",
            "district": "Dhaka",
            "area": "Dhanmondi",
            "consultation_fee": 500,
            "follow_up_fee": 300,
        },
    )
    payload = dict(
        chamber_id=chamber.json()["data"]["id"],
        schedule_date=str(local_now().date() + timedelta(days=1)),
        start_time="17:00:00",
        end_time="21:00:00",
        maximum_patients=10,
    )
    assert (await client.post("/api/v1/schedules", headers=doctor, json=payload)).status_code == 403
    assert (
        await client.post("/api/v1/schedules", headers=doctor, json={**payload, "status": "draft"})
    ).status_code == 201
    updated = await client.patch(
        "/api/v1/doctors/me/profile",
        headers=doctor,
        json={
            "qualifications": [
                {"title": "MBBS", "institution": "Test College", "completion_year": 2020}
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["qualifications"][0]["title"] == "MBBS"
