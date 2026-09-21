from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_appointment_booking_concurrency_and_tracking(client: AsyncClient, db_session):
    # 1. Register a doctor and create chamber + schedule (max 2 patients for test capacity)
    await client.post(
        "/api/v1/auth/register/doctor",
        json={
            "email": "dr.booking@spandan.com.bd",
            "password": "Password123!",
            "phone_number": "+8801710002222",
            "full_name": "Dr. Booking Test",
            "medical_registration_number": "BMDC-B-20202",
        },
    )
    doc_login = await client.post(
        "/api/v1/auth/login", json={"email": "dr.booking@spandan.com.bd", "password": "Password123!"}
    )
    doc_token = doc_login.json()["data"]["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    chamber_resp = await client.post(
        "/api/v1/chambers",
        json={
            "name": "Booking Test Chamber",
            "address": "Banani Road 11",
            "district": "Dhaka",
            "area": "Banani",
            "consultation_fee": 1000.0,
            "follow_up_fee": 600.0,
        },
        headers=doc_headers,
    )
    chamber_id = chamber_resp.json()["data"]["id"]

    from sqlalchemy import update

    from app.models.doctor import DoctorProfile, DoctorVerificationStatus
    await db_session.execute(update(DoctorProfile).values(verification_status=DoctorVerificationStatus.APPROVED))
    await db_session.commit()

    sched_resp = await client.post(
        "/api/v1/schedules",
        json={
            "chamber_id": chamber_id,
            "schedule_date": str(date.today() + timedelta(days=1)),
            "start_time": "18:00:00",
            "end_time": "20:00:00",
            "maximum_patients": 2,  # Set max=2 to test overbooking rejection
        },
        headers=doc_headers,
    )
    schedule_id = sched_resp.json()["data"]["id"]

    # 2. Register Patient 1
    await client.post(
        "/api/v1/auth/register/patient",
        json={
            "email": "pat1@gmail.com",
            "password": "Password123!",
            "phone_number": "+8801710003333",
            "full_name": "Patient One",
        },
    )
    pat1_login = await client.post(
        "/api/v1/auth/login", json={"email": "pat1@gmail.com", "password": "Password123!"}
    )
    pat1_headers = {"Authorization": f"Bearer {pat1_login.json()['data']['access_token']}"}

    # Book for Patient 1 -> Serial #1
    book_resp_1 = await client.post(
        "/api/v1/appointments",
        json={"schedule_id": schedule_id, "patient_note": "Fever and cough"},
        headers=pat1_headers,
    )
    assert book_resp_1.status_code == 201
    app1_data = book_resp_1.json()["data"]
    assert app1_data["serial_number"] == 1
    assert app1_data["appointment_status"] == "booked"

    # Concurrency test: Patient 1 tries to double book same schedule -> 409 Conflict
    book_resp_double = await client.post(
        "/api/v1/appointments",
        json={"schedule_id": schedule_id, "patient_note": "Another booking"},
        headers=pat1_headers,
    )
    assert book_resp_double.status_code == 409
    assert book_resp_double.json()["error"]["code"] == "CONFLICT"

    # 3. Register Patient 2
    await client.post(
        "/api/v1/auth/register/patient",
        json={
            "email": "pat2@gmail.com",
            "password": "Password123!",
            "phone_number": "+8801710004444",
            "full_name": "Patient Two",
        },
    )
    pat2_login = await client.post(
        "/api/v1/auth/login", json={"email": "pat2@gmail.com", "password": "Password123!"}
    )
    pat2_headers = {"Authorization": f"Bearer {pat2_login.json()['data']['access_token']}"}

    # Book for Patient 2 -> Serial #2
    book_resp_2 = await client.post(
        "/api/v1/appointments",
        json={"schedule_id": schedule_id, "patient_note": "Headache"},
        headers=pat2_headers,
    )
    assert book_resp_2.status_code == 201
    app2_data = book_resp_2.json()["data"]
    assert app2_data["serial_number"] == 2

    # 4. Capacity limit reached: Register Patient 3 -> should get rejected due to SCHEDULE_FULL or SCHEDULE_CLOSED
    await client.post(
        "/api/v1/auth/register/patient",
        json={
            "email": "pat3@gmail.com",
            "password": "Password123!",
            "phone_number": "+8801710005555",
            "full_name": "Patient Three",
        },
    )
    pat3_login = await client.post(
        "/api/v1/auth/login", json={"email": "pat3@gmail.com", "password": "Password123!"}
    )
    pat3_headers = {"Authorization": f"Bearer {pat3_login.json()['data']['access_token']}"}

    book_resp_3 = await client.post(
        "/api/v1/appointments",
        json={"schedule_id": schedule_id},
        headers=pat3_headers,
    )
    assert book_resp_3.status_code == 400
    assert book_resp_3.json()["error"]["code"] in ["SCHEDULE_FULL", "SCHEDULE_CLOSED"]

    # 5. Serial tracking test for Patient 2
    track_resp = await client.get(f"/api/v1/appointments/track/{schedule_id}", headers=pat2_headers)
    assert track_resp.status_code == 200
    track_data = track_resp.json()["data"]
    assert track_data["your_serial_number"] == 2
    assert track_data["people_ahead"] == 1  # Since serial 1 is ahead and running is 0

    # 6. Doctor updates appointment 1 status to IN_CONSULTATION -> queue running serial auto updates to 1
    update_status_resp = await client.patch(
        f"/api/v1/appointments/{app1_data['id']}/status",
        json={"appointment_status": "in_consultation"},
        headers=doc_headers,
    )
    assert update_status_resp.status_code == 200
    assert update_status_resp.json()["data"]["appointment_status"] == "in_consultation"

    # Verify queue running serial is now 1
    track_resp_after = await client.get(f"/api/v1/appointments/track/{schedule_id}", headers=pat2_headers)
    assert track_resp_after.json()["data"]["current_serial_running"] == 1
    assert track_resp_after.json()["data"]["people_ahead"] == 1
