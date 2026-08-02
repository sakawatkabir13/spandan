from app.services.auth import auth_service, AuthService
from app.services.doctor import doctor_service, DoctorService
from app.services.chamber import chamber_service, ChamberService
from app.services.schedule import schedule_service, ScheduleService
from app.services.appointment import appointment_service, AppointmentService
from app.services.ai import triage_service, SymptomTriageService

__all__ = [
    "auth_service",
    "AuthService",
    "doctor_service",
    "DoctorService",
    "chamber_service",
    "ChamberService",
    "schedule_service",
    "ScheduleService",
    "appointment_service",
    "AppointmentService",
    "triage_service",
    "SymptomTriageService",
]
