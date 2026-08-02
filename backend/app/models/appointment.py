import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BookingSource(str, enum.Enum):
    ONLINE = "online"
    ASSISTANT = "assistant"
    PHONE = "phone"
    WALK_IN = "walk_in"
    DOCTOR = "doctor"


class AppointmentStatus(str, enum.Enum):
    BOOKED = "booked"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    WAITING = "waiting"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    ABSENT = "absent"
    CANCELLED = "cancelled"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    chamber_id = Column(UUID(as_uuid=True), ForeignKey("chambers.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    serial_number = Column(Integer, nullable=False)
    booking_source = Column(
        Enum(BookingSource, name="bookingsource", create_constraint=True),
        default=BookingSource.ONLINE,
        nullable=False,
    )
    appointment_status = Column(
        Enum(AppointmentStatus, name="appointmentstatus", create_constraint=True),
        default=AppointmentStatus.BOOKED,
        nullable=False,
        index=True,
    )
    estimated_consultation_at = Column(DateTime(timezone=True), nullable=True)
    actual_consultation_started_at = Column(DateTime(timezone=True), nullable=True)
    actual_consultation_completed_at = Column(DateTime(timezone=True), nullable=True)
    patient_note = Column(Text, nullable=True)
    cancellation_reason = Column(String, nullable=True)
    booked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    patient = relationship("PatientProfile", back_populates="appointments")
    doctor = relationship("DoctorProfile", back_populates="appointments")
    chamber = relationship("Chamber", back_populates="appointments")
    schedule = relationship("Schedule", back_populates="appointments")
