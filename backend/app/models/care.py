"""Patient-owned charts and doctor-reviewed visit records, excluded from AI tools."""
import uuid

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, utcnow


class DependentMedicalHistory(Base):
    __tablename__ = "dependent_medical_histories"
    dependent_id = Column(UUID(as_uuid=True), ForeignKey("dependents.id", ondelete="CASCADE"), primary_key=True)
    blood_group = Column(String(10))
    allergies = Column(Text, nullable=False, default="", server_default="")
    medications = Column(Text, nullable=False, default="", server_default="")
    conditions = Column(Text, nullable=False, default="", server_default="")
    surgeries = Column(Text, nullable=False, default="", server_default="")
    family_history = Column(Text, nullable=False, default="", server_default="")
    history_reviewed = Column(Boolean, nullable=False, default=False, server_default="false")
    share_with_doctors = Column(Boolean, nullable=False, default=False, server_default="false")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AppointmentSharing(Base):
    __tablename__ = "appointment_sharing"
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), primary_key=True)
    share_history = Column(Boolean, nullable=False, default=False)
    report_ids = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class VisitSummary(Base):
    __tablename__ = "visit_summaries"
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), primary_key=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False)
    summary = Column(Text, nullable=False, default="")
    prescription = Column(Text, nullable=False, default="")
    follow_up_instructions = Column(Text, nullable=False, default="")
    follow_up_date = Column(Date)
    revision = Column(Integer, nullable=False, default=0)
    published_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class FavoriteDoctor(Base):
    __tablename__ = "favorite_doctors"
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), primary_key=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class BookingEvent(Base):
    __tablename__ = "booking_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    event = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
