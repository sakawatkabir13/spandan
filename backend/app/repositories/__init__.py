from app.repositories.base import BaseRepository
from app.repositories.user import user_repo, patient_repo, UserRepository, PatientProfileRepository
from app.repositories.doctor import doctor_repo, specialization_repo, qualification_repo, DoctorRepository, SpecializationRepository, QualificationRepository
from app.repositories.chamber import chamber_repo, ChamberRepository
from app.repositories.schedule import schedule_repo, queue_repo, ScheduleRepository, QueueStateRepository
from app.repositories.appointment import appointment_repo, AppointmentRepository
from app.repositories.ai import recommendation_repo, RecommendationRepository

__all__ = [
    "BaseRepository",
    "user_repo",
    "patient_repo",
    "UserRepository",
    "PatientProfileRepository",
    "doctor_repo",
    "specialization_repo",
    "qualification_repo",
    "DoctorRepository",
    "SpecializationRepository",
    "QualificationRepository",
    "chamber_repo",
    "ChamberRepository",
    "schedule_repo",
    "queue_repo",
    "ScheduleRepository",
    "QueueStateRepository",
    "appointment_repo",
    "AppointmentRepository",
    "recommendation_repo",
    "RecommendationRepository",
]
