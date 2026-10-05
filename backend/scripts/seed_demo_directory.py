"""Create explicitly simulated accounts for reviewed public directory profiles.

Requires DEMO_MODE=true. Passwords are random and written only to a private file.
Re-runs preserve passwords, moderation decisions, fees and existing appointments.
"""

import argparse
import asyncio
import json
import os
import secrets
from datetime import date, time, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.time import local_now
from app.db.session import async_session_maker, engine
from app.models.audit import AuditLog
from app.models.chamber import Chamber
from app.models.directory import DirectoryDoctor
from app.models.doctor import DoctorProfile, DoctorVerificationStatus, Specialization
from app.models.schedule import QueueState, Schedule, ScheduleStatus
from app.models.user import User, UserRole
from app.services.specialty_taxonomy import canonical_specialty
from scripts.import_directory import import_rows, load_dataset


async def ensure_demo_sessions(db, start_date=None, days=7):
    if not settings.DEMO_MODE:
        return 0
    if not 1 <= days <= 30:
        raise ValueError("Demo availability must cover 1–30 days")
    start = start_date or local_now().date()
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(73910623)"))
    chambers = list(
        await db.scalars(
            select(Chamber)
            .join(DoctorProfile)
            .join(User, User.id == DoctorProfile.user_id)
            .join(DirectoryDoctor, DirectoryDoctor.demo_doctor_id == DoctorProfile.id)
            .where(
                DoctorProfile.is_demo.is_(True),
                DoctorProfile.verification_status == DoctorVerificationStatus.APPROVED,
                User.is_active.is_(True),
                DirectoryDoctor.is_active.is_(True),
                Chamber.is_active.is_(True),
            )
        )
    )
    existing = {
        (s.chamber_id, s.schedule_date)
        for s in await db.scalars(
            select(Schedule).where(
                Schedule.chamber_id.in_([c.id for c in chambers]),
                Schedule.schedule_date >= start,
                Schedule.schedule_date < start + timedelta(days=days),
            )
        )
    }
    added = 0
    for chamber in chambers:
        for offset in range(days):
            day = start + timedelta(days=offset)
            if (chamber.id, day) in existing:
                continue
            schedule = Schedule(
                doctor_id=chamber.doctor_id,
                chamber_id=chamber.id,
                schedule_date=day,
                start_time=time(15),
                end_time=time(18),
                maximum_patients=12,
                average_consultation_minutes=15,
                status=ScheduleStatus.OPEN,
            )
            db.add(schedule)
            await db.flush()
            db.add(
                QueueState(
                    schedule_id=schedule.id,
                    status_message="Contact the hospital directly to arrange a consultation.",
                )
            )
            added += 1
    await db.flush()
    return added


async def seed_demo_accounts(db, rows, credentials, start_date=None, days=7):
    if not settings.DEMO_MODE:
        raise ValueError("Explicit DEMO_MODE=true is required")
    await import_rows(db, rows)
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(73910623)"))
    added = 0
    for listing in await db.scalars(select(DirectoryDoctor).order_by(DirectoryDoctor.listing_key)):
        if not listing.is_active or listing.demo_doctor_id:
            continue
        identity = uuid5(NAMESPACE_URL, f"spandan:academic-demo:{listing.listing_key}")
        email = f"{identity.hex}@demo.spandan.example.com"
        password = secrets.token_urlsafe(24)
        # No real email/phone or real registration identifier is used for login.
        user = User(
            id=identity,
            email=email,
            password_hash=get_password_hash(password),
            display_name=listing.full_name,
            role=UserRole.DOCTOR,
            is_active=True,
            is_email_verified=False,
            is_phone_verified=False,
        )
        db.add(user)
        await db.flush()
        name = canonical_specialty(listing.specialty)
        spec = await db.scalar(select(Specialization).where(Specialization.name == name))
        if not spec:
            spec = Specialization(
                name=name, description="Specialist category from public hospital departments."
            )
            db.add(spec)
            await db.flush()
        doctor = DoctorProfile(
            user_id=user.id,
            full_name=listing.full_name,
            medical_registration_number=f"DEMO-{identity.hex[:16].upper()}",
            is_demo=True,
            source_url=listing.source_url,
            current_workplace=listing.institution,
            biography=f"Public hospital qualifications: {listing.qualifications or 'Not provided by source'}.\nHospital department: {listing.specialty}.\nContact the hospital directly to confirm fees and arrange a consultation. Spandan schedules do not reserve a hospital visit.",
            verification_status=DoctorVerificationStatus.APPROVED,
            verification_notes="Automatically approved for academic demonstration only. No BMDC verification or doctor ownership confirmation.",
            specializations=[spec],
            qualifications=[],
            years_of_experience=0,
        )
        db.add(doctor)
        await db.flush()
        listing.demo_doctor_id = doctor.id
        db.add(
            Chamber(
                doctor_id=doctor.id,
                name="Spandan chamber",
                address=f"Hospital reference address: {listing.address or listing.institution}",
                district=listing.district,
                area=listing.district,
                phone_number=None,
                consultation_fee=500,
                follow_up_fee=300,
                average_consultation_minutes=15,
            )
        )
        db.add(
            AuditLog(
                action="doctor.demo_created",
                entity_type="doctor_profile",
                entity_id=str(doctor.id),
                metadata_json={"listing_key": listing.listing_key, "is_demo": True},
            )
        )
        credentials[listing.listing_key] = {
            "name": listing.full_name,
            "email": email,
            "password": password,
            "doctor_id": str(doctor.id),
        }
        added += 1
    await db.flush()
    sessions = await ensure_demo_sessions(db, start_date, days)
    return {"accounts_created": added, "sessions_created": sessions}


def save_credentials(path, credentials):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(credentials, stream, indent=2)
        stream.write("\n")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


async def main(args):
    if not settings.DEMO_MODE:
        raise ValueError("Explicit DEMO_MODE=true is required")
    path = args.credentials_file
    try:
        async with async_session_maker() as db, db.begin():
            if db.bind.dialect.name == "postgresql":
                await db.execute(text("SELECT pg_advisory_xact_lock(73910622)"))
                await db.execute(text("SELECT pg_advisory_xact_lock(73910623)"))
            credentials = json.loads(path.read_text()) if path.exists() else {}
            result = await seed_demo_accounts(
                db, load_dataset(), credentials, args.start_date, args.days
            )
            # Persist before commit: failures cannot create inaccessible accounts.
            save_credentials(path, credentials)
        print(json.dumps(result))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--days", type=int, default=7)
    asyncio.run(main(parser.parse_args()))
