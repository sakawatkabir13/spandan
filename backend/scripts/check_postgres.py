"""Exercise real concurrent HTTP bookings against a disposable *_test PostgreSQL database.

Run migrations first. This script inserts uniquely named test records and must never target production.
"""

import asyncio
from datetime import timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.core.time import local_now
from app.db.session import async_session_maker, engine
from app.main import app
from app.models.appointment import Appointment
from app.models.chamber import Chamber
from app.models.doctor import DoctorProfile, DoctorVerificationStatus
from app.models.schedule import QueueState, Schedule, ScheduleStatus
from app.models.user import PatientProfile, User, UserRole


async def main():
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        raise SystemExit("Use a disposable PostgreSQL database with a name ending in _test.")
    run_id = uuid4().hex
    async with async_session_maker() as db:
        doctor_user = User(
            email=f"{run_id}-doctor@example.com",
            role=UserRole.DOCTOR,
            password_hash=get_password_hash("TestPassword123!"),
        )
        db.add(doctor_user)
        await db.flush()
        doctor = DoctorProfile(
            user_id=doctor_user.id,
            full_name="Concurrency Doctor",
            medical_registration_number=run_id,
            verification_status=DoctorVerificationStatus.APPROVED,
        )
        db.add(doctor)
        await db.flush()
        chamber = Chamber(
            doctor_id=doctor.id,
            name="Concurrency Chamber",
            address="Test address",
            district="Dhaka",
            area="Dhaka",
            consultation_fee=500,
            follow_up_fee=300,
        )
        db.add(chamber)
        await db.flush()
        schedule = Schedule(
            doctor_id=doctor.id,
            chamber_id=chamber.id,
            schedule_date=local_now().date() + timedelta(days=1),
            start_time=__import__("datetime").time(17),
            end_time=__import__("datetime").time(21),
            maximum_patients=3,
            status=ScheduleStatus.OPEN,
        )
        db.add(schedule)
        await db.flush()
        db.add(QueueState(schedule_id=schedule.id))
        headers = []
        for index in range(10):
            user = User(
                email=f"{run_id}-{index}@example.com",
                role=UserRole.PATIENT,
                password_hash=doctor_user.password_hash,
            )
            db.add(user)
            await db.flush()
            db.add(PatientProfile(user_id=user.id, full_name=f"Patient {index}"))
            headers.append({"Authorization": f"Bearer {create_access_token(user.id, 'patient')}"})
        await db.commit()
        schedule_id = str(schedule.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(
            *(
                client.post("/api/v1/appointments", headers=h, json={"schedule_id": schedule_id})
                for h in headers
            )
        )
        successes = [(i, r.json()["data"]) for i, r in enumerate(responses) if r.status_code == 201]
        assert len(successes) == 3, [(r.status_code, r.text) for r in responses]
        assert sorted(a["serial_number"] for _, a in successes) == [1, 2, 3]
        assert all(r.status_code in (201, 400) for r in responses)
        owner, last = max(successes, key=lambda pair: pair[1]["serial_number"])
        cancel = await client.patch(
            f"/api/v1/appointments/{last['id']}/status",
            headers=headers[owner],
            json={"appointment_status": "cancelled"},
        )
        assert cancel.status_code == 200, cancel.text
        # Identical simultaneous requests must consume only one freed slot.
        duplicates = await asyncio.gather(
            *(
                client.post(
                    "/api/v1/appointments",
                    headers=headers[owner],
                    json={"schedule_id": schedule_id},
                )
                for _ in range(5)
            )
        )
        assert sum(r.status_code == 201 for r in duplicates) == 1
        created = next(r.json()["data"] for r in duplicates if r.status_code == 201)
        assert created["serial_number"] == 4
        assert all(r.status_code in (201, 400, 409) for r in duplicates)
    async with async_session_maker() as db:
        bookings = list(
            (
                await db.scalars(select(Appointment).where(Appointment.schedule_id == schedule.id))
            ).all()
        )
        assert len(bookings) == 4
        assert len({a.serial_number for a in bookings}) == 4
    await engine.dispose()
    print(
        "PostgreSQL concurrency checks passed: capacity, unique serials, cancellation/rebooking, duplicate requests."
    )


if __name__ == "__main__":
    asyncio.run(main())
