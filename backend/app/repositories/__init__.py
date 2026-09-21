from app.repositories.ai import RecommendationRepository, recommendation_repo
from app.repositories.appointment import AppointmentRepository, appointment_repo
from app.repositories.base import BaseRepository
from app.repositories.chamber import ChamberRepository, chamber_repo
from app.repositories.doctor import (
    DoctorRepository,
    QualificationRepository,
    SpecializationRepository,
    doctor_repo,
    qualification_repo,
    specialization_repo,
)
from app.repositories.schedule import (
    QueueStateRepository,
    ScheduleRepository,
    queue_repo,
    schedule_repo,
)
from app.repositories.user import PatientProfileRepository, UserRepository, patient_repo, user_repo

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
