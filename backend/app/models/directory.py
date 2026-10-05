"""Public professional listings, independent of authenticated/bookable doctors."""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, utcnow


class DirectoryDoctor(Base):
    __tablename__ = "directory_doctors"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    demo_doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="SET NULL"), unique=True, nullable=True)
    listing_key = Column(String(160), unique=True, nullable=False)
    full_name = Column(String(200), nullable=False, index=True)
    native_name = Column(String(200), nullable=True)
    specialty = Column(String(100), nullable=False, index=True)
    qualifications = Column(String(500), nullable=True)
    institution = Column(String(200), nullable=False)
    division = Column(String(50), nullable=False, index=True)
    district = Column(String(80), nullable=False, index=True)
    address = Column(Text, nullable=True)
    appointment_phone = Column(String(40), nullable=True)
    published_hours = Column(String(300), nullable=True)
    source_url = Column(String(1000), nullable=False)
    contact_source_url = Column(String(1000), nullable=True)
    source_checked_on = Column(Date, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
