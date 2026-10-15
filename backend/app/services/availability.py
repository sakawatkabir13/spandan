"""Tell affected patients when a doctor becomes unavailable, without changing their payments."""
from sqlalchemy import select

from app.core.config import settings
from app.core.time import local_now
from app.models.appointment import Appointment, AppointmentStatus
from app.models.schedule import Schedule
from app.models.user import PatientProfile, User
from app.services.notifications import notify


async def notify_unavailability(db, doctor_id, change_id):
    rows = await db.execute(select(Appointment.id, User).join(PatientProfile, PatientProfile.id == Appointment.patient_id).join(User, User.id == PatientProfile.user_id).join(Schedule, Schedule.id == Appointment.schedule_id).where(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.ABSENT]),
        Schedule.schedule_date >= local_now().date(), User.is_active.is_(True),
    ))
    for id, user in rows:
        await notify(db, user, "Chamber availability changed", f"Your booked doctor is currently unavailable on Spandan. Contact the chamber before travelling and review your booking, cancellation, and payment options at {settings.FRONTEND_URL}/dashboard/patient/appointments/{id}. Your appointment and payment have not been changed automatically.", f"availability:{id}:{change_id}")
