import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DoctorVerificationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False, index=True)
    profile_photo_url = Column(String, nullable=True)
    medical_registration_number = Column(String, unique=True, index=True, nullable=False)
    biography = Column(Text, nullable=True)
    current_workplace = Column(String, nullable=True, index=True)
    years_of_experience = Column(Integer, default=0, nullable=False)
    verification_status = Column(
        Enum(DoctorVerificationStatus, name="doctorverificationstatus", create_constraint=True),
        default=DoctorVerificationStatus.PENDING,
        nullable=False,
        index=True,
    )
    verification_notes = Column(Text, nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="doctor_profile", foreign_keys=[user_id])
    qualifications = relationship("Qualification", back_populates="doctor", cascade="all, delete-orphan")
    specializations = relationship("Specialization", secondary="doctor_specializations", back_populates="doctors")
    chambers = relationship("Chamber", back_populates="doctor", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="doctor", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")
    assistant_assignments = relationship("AssistantAssignment", back_populates="doctor", cascade="all, delete-orphan", foreign_keys="AssistantAssignment.doctor_id")


class Qualification(Base):
    __tablename__ = "qualifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    institution = Column(String, nullable=False)
    country = Column(String, nullable=True, default="Bangladesh")
    completion_year = Column(Integer, nullable=True)

    doctor = relationship("DoctorProfile", back_populates="qualifications")


class Specialization(Base):
    __tablename__ = "specializations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    doctors = relationship("DoctorProfile", secondary="doctor_specializations", back_populates="specializations")


class DoctorSpecialization(Base):
    __tablename__ = "doctor_specializations"

    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), primary_key=True)
    specialization_id = Column(UUID(as_uuid=True), ForeignKey("specializations.id", ondelete="CASCADE"), primary_key=True)


class AssistantAssignment(Base):
    __tablename__ = "assistant_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    assistant_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    can_manage_schedules = Column(Boolean, default=True, nullable=False)
    can_manage_appointments = Column(Boolean, default=True, nullable=False)
    can_update_queue = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    doctor = relationship("DoctorProfile", back_populates="assistant_assignments", foreign_keys=[doctor_id])
    assistant = relationship("User", back_populates="assistant_assignments", foreign_keys=[assistant_user_id])
