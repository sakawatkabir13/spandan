"""Clinical information is kept separate from public and authentication profiles."""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, utcnow


class MedicalHistory(Base):
    __tablename__ = "medical_histories"

    patient_id = Column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), primary_key=True)
    blood_group = Column(String(10), nullable=True)
    allergies = Column(Text, nullable=False, default="", server_default="")
    medications = Column(Text, nullable=False, default="", server_default="")
    conditions = Column(Text, nullable=False, default="", server_default="")
    surgeries = Column(Text, nullable=False, default="", server_default="")
    family_history = Column(Text, nullable=False, default="", server_default="")
    history_reviewed = Column(Boolean, nullable=False, default=False, server_default="false")
    share_with_doctors = Column(Boolean, nullable=False, default=False, server_default="false")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class MedicalReport(Base):
    __tablename__ = "medical_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    dependent_id = Column(UUID(as_uuid=True), ForeignKey("dependents.id", ondelete="CASCADE"), nullable=True, index=True)
    share_with_doctors = Column(Boolean, nullable=False, default=True, server_default="true")
    title = Column(String(120), nullable=False)
    report_type = Column(String(30), nullable=False)
    report_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=False, default="", server_default="")
    original_filename = Column(String(180), nullable=False)
    content_type = Column(String(50), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_key = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
