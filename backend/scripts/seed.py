import asyncio
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.db.session import async_session_maker
from app.models.user import User, UserRole, PatientProfile
from app.models.doctor import (
    DoctorProfile,
    DoctorVerificationStatus,
    Qualification,
    Specialization,
    AssistantAssignment,
)
from app.models.chamber import Chamber
from app.models.schedule import Schedule, ScheduleStatus, QueueState
from app.models.appointment import Appointment, BookingSource, AppointmentStatus
from app.models.recommendation import SpecialistRecommendation, UrgencyLevel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def seed_data(db: AsyncSession) -> None:
    # Check if admin already exists
    existing_admin = await db.execute(select(User).where(User.email == "admin@spandan.com.bd"))
    if existing_admin.scalar_one_or_none():
        print("Seed data already present. Skipping seeding.")
        return

    print("Seeding Spandan initial data...")
    password_hash = get_password_hash("Password123!")

    # 1. Specializations
    specs = [
        ("General Medicine", "Primary healthcare, diagnostics, and general medical checkups."),
        ("Cardiology", "Heart diseases, blood pressure, and cardiovascular conditions."),
        ("Pediatrics", "Medical care for infants, children, and adolescents."),
        ("Dermatology", "Skin, hair, and nail disorders."),
        ("Neurology", "Brain, spinal cord, and nervous system disorders."),
        ("Gynecology and Obstetrics", "Women's reproductive health and pregnancy care."),
        ("Orthopedics", "Bone, joint, muscle, and ligament disorders."),
        ("Psychiatry", "Mental health disorders, anxiety, depression, and counseling."),
        ("ENT", "Ear, Nose, and Throat surgery and treatment."),
    ]
    spec_map = {}
    for name, desc in specs:
        s = Specialization(name=name, description=desc, is_active=True)
        db.add(s)
        await db.flush()
        spec_map[name] = s

    # 2. Administrator Account
    admin = User(
        email="admin@spandan.com.bd",
        phone_number="+8801711000001",
        password_hash=password_hash,
        role=UserRole.ADMINISTRATOR,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=True,
    )
    db.add(admin)
    await db.flush()

    # 3. Approved Doctor 1 (Dr. Anisur Rahman - Cardiologist & General Medicine)
    doc_user_1 = User(
        email="dr.rahman@spandan.com.bd",
        phone_number="+8801711000002",
        password_hash=password_hash,
        role=UserRole.DOCTOR,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=True,
    )
    db.add(doc_user_1)
    await db.flush()

    doc_profile_1 = DoctorProfile(
        user_id=doc_user_1.id,
        full_name="Prof. Dr. Anisur Rahman",
        medical_registration_number="BMDC-A-12345",
        biography="Senior Consultant in Cardiology with over 22 years of clinical experience in interventional cardiology and preventive heart care.",
        current_workplace="National Institute of Cardiovascular Diseases (NICVD), Dhaka",
        years_of_experience=22,
        verification_status=DoctorVerificationStatus.APPROVED,
        verification_notes="Verified BMDC registration and academic credentials.",
        verified_by=admin.id,
        verified_at=utcnow(),
    )
    doc_profile_1.specializations.append(spec_map["Cardiology"])
    doc_profile_1.specializations.append(spec_map["General Medicine"])
    db.add(doc_profile_1)
    await db.flush()

    db.add(Qualification(doctor_id=doc_profile_1.id, title="MBBS", institution="Dhaka Medical College", completion_year=2000))
    db.add(Qualification(doctor_id=doc_profile_1.id, title="FCPS (Cardiology)", institution="BCPS Bangladesh", completion_year=2006))

    # Chamber for Doctor 1
    chamber_1 = Chamber(
        doctor_id=doc_profile_1.id,
        name="Popular Diagnostic Centre - Dhanmondi Chamber",
        address="House #16, Road #2, Dhanmondi R/A",
        district="Dhaka",
        area="Dhanmondi",
        phone_number="+8801711000010",
        consultation_fee=1500.00,
        follow_up_fee=1000.00,
        average_consultation_minutes=15,
        is_active=True,
    )
    db.add(chamber_1)
    await db.flush()

    # 4. Approved Doctor 2 (Dr. Farhana Akter - Pediatrician)
    doc_user_2 = User(
        email="dr.farhana@spandan.com.bd",
        phone_number="+8801711000003",
        password_hash=password_hash,
        role=UserRole.DOCTOR,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=True,
    )
    db.add(doc_user_2)
    await db.flush()

    doc_profile_2 = DoctorProfile(
        user_id=doc_user_2.id,
        full_name="Dr. Farhana Akter",
        medical_registration_number="BMDC-A-67890",
        biography="Experienced Pediatrician dedicated to child health, vaccination counseling, and neonatal intensive care.",
        current_workplace="Bangladesh Shishu Hospital and Institute, Dhaka",
        years_of_experience=14,
        verification_status=DoctorVerificationStatus.APPROVED,
        verification_notes="All documents verified.",
        verified_by=admin.id,
        verified_at=utcnow(),
    )
    doc_profile_2.specializations.append(spec_map["Pediatrics"])
    db.add(doc_profile_2)
    await db.flush()

    db.add(Qualification(doctor_id=doc_profile_2.id, title="MBBS", institution="Sir Salimullah Medical College", completion_year=2008))
    db.add(Qualification(doctor_id=doc_profile_2.id, title="MD (Pediatrics)", institution="BSMMU", completion_year=2014))

    chamber_2 = Chamber(
        doctor_id=doc_profile_2.id,
        name="Labaid Diagnostic - Uttara Branch",
        address="House #15, Sector #6, Uttara",
        district="Dhaka",
        area="Uttara",
        phone_number="+8801711000020",
        consultation_fee=1200.00,
        follow_up_fee=800.00,
        average_consultation_minutes=12,
        is_active=True,
    )
    db.add(chamber_2)
    await db.flush()

    # 5. Pending Doctor (Dr. Tariqul Islam)
    doc_user_3 = User(
        email="dr.tariq@spandan.com.bd",
        phone_number="+8801711000004",
        password_hash=password_hash,
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db.add(doc_user_3)
    await db.flush()

    doc_profile_3 = DoctorProfile(
        user_id=doc_user_3.id,
        full_name="Dr. Tariqul Islam",
        medical_registration_number="BMDC-A-99887",
        biography="Consultant Dermatologist specializing in laser therapy and clinical dermatology.",
        current_workplace="Dhaka Medical College Hospital",
        years_of_experience=8,
        verification_status=DoctorVerificationStatus.PENDING,
    )
    doc_profile_3.specializations.append(spec_map["Dermatology"])
    db.add(doc_profile_3)
    await db.flush()

    # 6. Assistants
    asst_user_1 = User(
        email="assistant.karim@spandan.com.bd",
        phone_number="+8801711000005",
        password_hash=password_hash,
        role=UserRole.ASSISTANT,
        is_active=True,
    )
    db.add(asst_user_1)
    await db.flush()
    db.add(AssistantAssignment(doctor_id=doc_profile_1.id, assistant_user_id=asst_user_1.id, is_active=True))

    asst_user_2 = User(
        email="assistant.nasrin@spandan.com.bd",
        phone_number="+8801711000006",
        password_hash=password_hash,
        role=UserRole.ASSISTANT,
        is_active=True,
    )
    db.add(asst_user_2)
    await db.flush()
    db.add(AssistantAssignment(doctor_id=doc_profile_2.id, assistant_user_id=asst_user_2.id, is_active=True))

    # 7. Patients
    pat_user_1 = User(
        email="patient.jamal@gmail.com",
        phone_number="+8801711000007",
        password_hash=password_hash,
        role=UserRole.PATIENT,
        is_active=True,
    )
    db.add(pat_user_1)
    await db.flush()
    pat_profile_1 = PatientProfile(
        user_id=pat_user_1.id,
        full_name="Jamal Uddin Ahmed",
        date_of_birth=date(1985, 5, 12),
        gender="Male",
        address="House 45, Road 10, Banani, Dhaka",
        emergency_contact="+8801711999999",
    )
    db.add(pat_profile_1)
    await db.flush()

    pat_user_2 = User(
        email="patient.sadia@gmail.com",
        phone_number="+8801711000008",
        password_hash=password_hash,
        role=UserRole.PATIENT,
        is_active=True,
    )
    db.add(pat_user_2)
    await db.flush()
    pat_profile_2 = PatientProfile(
        user_id=pat_user_2.id,
        full_name="Sadia Jahan",
        date_of_birth=date(1992, 9, 20),
        gender="Female",
        address="Mirpur 10, Dhaka",
        emergency_contact="+8801711888888",
    )
    db.add(pat_profile_2)
    await db.flush()

    # 8. Schedules & Appointments (For Dr. Rahman today and tomorrow)
    today = date.today()
    schedule_1 = Schedule(
        doctor_id=doc_profile_1.id,
        chamber_id=chamber_1.id,
        schedule_date=today,
        start_time=time(17, 0),
        end_time=time(21, 0),
        maximum_patients=20,
        average_consultation_minutes=15,
        status=ScheduleStatus.OPEN,
        created_by_user_id=doc_user_1.id,
    )
    db.add(schedule_1)
    await db.flush()

    queue_1 = QueueState(
        schedule_id=schedule_1.id,
        current_serial=2,
        delay_minutes=10,
        status_message="Consultation in progress. Serial #2 inside chamber.",
        updated_by_user_id=asst_user_1.id,
    )
    db.add(queue_1)
    await db.flush()

    # Sample Appointments
    app_1 = Appointment(
        patient_id=pat_profile_1.id,
        doctor_id=doc_profile_1.id,
        chamber_id=chamber_1.id,
        schedule_id=schedule_1.id,
        serial_number=1,
        booking_source=BookingSource.ONLINE,
        appointment_status=AppointmentStatus.COMPLETED,
        patient_note="Routine blood pressure checkup.",
        booked_by_user_id=pat_user_1.id,
    )
    app_2 = Appointment(
        patient_id=pat_profile_2.id,
        doctor_id=doc_profile_1.id,
        chamber_id=chamber_1.id,
        schedule_id=schedule_1.id,
        serial_number=2,
        booking_source=BookingSource.ASSISTANT,
        appointment_status=AppointmentStatus.IN_CONSULTATION,
        patient_note="Chest discomfort and palpitations.",
        booked_by_user_id=asst_user_1.id,
    )
    db.add(app_1)
    db.add(app_2)

    # 9. Sample AI Recommendation
    rec_1 = SpecialistRecommendation(
        patient_id=pat_profile_2.id,
        symptoms_text="I have been having mild palpitations and dizziness after climbing stairs for the last 3 days.",
        recommended_specialization_id=spec_map["Cardiology"].id,
        recommended_specialization_name="Cardiology",
        alternative_specialization_name="General Medicine",
        urgency_level=UrgencyLevel.SOON,
        reasoning_summary="Symptoms of chest palpitations and dizziness on exertion warrant a cardiovascular evaluation to check heart rhythm and blood pressure.",
        safety_message="Please avoid strenuous physical exertion until evaluated by a doctor.",
        disclaimer="This recommendation is generated by AI for general guidance only and is not a medical diagnosis.",
        model_identifier="llama-3.3-70b-versatile",
    )
    db.add(rec_1)

    await db.commit()
    print("Seeding completed successfully!")


async def main():
    async with async_session_maker() as session:
        await seed_data(session)


if __name__ == "__main__":
    asyncio.run(main())
