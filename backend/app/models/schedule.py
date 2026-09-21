import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScheduleStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    FULL = "full"
    CLOSED = "closed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    chamber_id = Column(UUID(as_uuid=True), ForeignKey("chambers.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    maximum_patients = Column(Integer, nullable=False)
    average_consultation_minutes = Column(Integer, default=15, nullable=False)
    booking_open_at = Column(DateTime(timezone=True), nullable=True)
    booking_close_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        Enum(ScheduleStatus, name="schedulestatus", create_constraint=True),
        default=ScheduleStatus.DRAFT,
        nullable=False,
        index=True,
    )
    cancellation_reason = Column(String, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    doctor = relationship("DoctorProfile", back_populates="schedules")
    chamber = relationship("Chamber", back_populates="schedules")
    appointments = relationship("Appointment", back_populates="schedule", cascade="all, delete-orphan")
    queue_state = relationship("QueueState", back_populates="schedule", uselist=False, cascade="all, delete-orphan")


class QueueState(Base):
    __tablename__ = "queue_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    current_serial = Column(Integer, default=0, nullable=False)
    delay_minutes = Column(Integer, default=0, nullable=False)
    status_message = Column(String, nullable=True, default="Queue not started yet.")
    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    schedule = relationship("Schedule", back_populates="queue_state")
