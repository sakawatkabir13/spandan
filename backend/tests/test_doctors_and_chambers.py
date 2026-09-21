from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_specialization_and_doctor_discovery(client: AsyncClient, db_session):
    # Register and verify a doctor
    reg_payload = {
        "email": "dr.cardio@spandan.com.bd",
        "password": "Password123!",
        "phone_number": "+8801710001111",
        "full_name": "Dr. Cardio Specialist",
        "medical_registration_number": "BMDC-C-10101",
        "current_workplace": "NICVD",
        "years_of_experience": 15,
    }
    await client.post("/api/v1/auth/register/doctor", json=reg_payload)

    # Login as doctor
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "dr.cardio@spandan.com.bd", "password": "Password123!"}
    )
    access_token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Get my doctor profile
    profile_resp = await client.get("/api/v1/doctors/me/profile", headers=headers)
    assert profile_resp.status_code == 200
    doc_id = profile_resp.json()["data"]["id"]

    # Create chamber
    chamber_payload = {
        "name": "Cardio Care Dhanmondi",
        "address": "House #12, Road #4, Dhanmondi",
        "district": "Dhaka",
        "area": "Dhanmondi",
        "consultation_fee": 1500.0,
        "follow_up_fee": 1000.0,
        "average_consultation_minutes": 15,
    }
    chamber_resp = await client.post("/api/v1/chambers", json=chamber_payload, headers=headers)
    assert chamber_resp.status_code == 201
    chamber_id = chamber_resp.json()["data"]["id"]

    from sqlalchemy import update

    from app.models.doctor import DoctorProfile, DoctorVerificationStatus
    await db_session.execute(update(DoctorProfile).values(verification_status=DoctorVerificationStatus.APPROVED))
    await db_session.commit()

    # Create schedule
    schedule_payload = {
        "chamber_id": chamber_id,
        "schedule_date": str(date.today() + timedelta(days=1)),
        "start_time": "17:00:00",
        "end_time": "21:00:00",
        "maximum_patients": 20,
    }
    sched_resp = await client.post("/api/v1/schedules", json=schedule_payload, headers=headers)
    assert sched_resp.status_code == 201
    sched_data = sched_resp.json()["data"]
    schedule_id = sched_data["id"]
    assert sched_data["queue_state"] is not None
    assert sched_data["queue_state"]["current_serial"] == 0

    # Update queue state
    queue_update = {"current_serial": 0, "delay_minutes": 15, "status_message": "Patient #1 inside"}
    q_resp = await client.patch(f"/api/v1/schedules/{schedule_id}/queue", json=queue_update, headers=headers)
    assert q_resp.status_code == 200
    q_data = q_resp.json()["data"]
    assert q_data["current_serial"] == 0
    assert q_data["delay_minutes"] == 15

    # Public discovery: Get chambers by doctor_id
    chambers_get = await client.get(f"/api/v1/chambers/doctor/{doc_id}")
    assert chambers_get.status_code == 200
    assert len(chambers_get.json()["data"]) == 1

    # Public discovery: Get schedules by doctor_id
    schedules_get = await client.get(f"/api/v1/schedules/doctor/{doc_id}")
    assert schedules_get.status_code == 200
    assert len(schedules_get.json()["data"]) == 1
