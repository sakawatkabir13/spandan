import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Chamber(Base):
    __tablename__ = "chambers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    district = Column(String, nullable=False, index=True)
    area = Column(String, nullable=False, index=True)
    phone_number = Column(String, nullable=True)
    consultation_fee = Column(Numeric(10, 2), nullable=False)
    follow_up_fee = Column(Numeric(10, 2), nullable=True)
    average_consultation_minutes = Column(Integer, default=15, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    doctor = relationship("DoctorProfile", back_populates="chambers")
    schedules = relationship("Schedule", back_populates="chamber", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="chamber", cascade="all, delete-orphan")
