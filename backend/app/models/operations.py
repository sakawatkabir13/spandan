"""Durable operational records; external deliveries are processed from an outbox."""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, utcnow


class Dependent(Base):
    __tablename__ = "dependents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id"), nullable=False, index=True
    )
    full_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    relationship_name = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (UniqueConstraint("schedule_id", "patient_id", name="uq_waitlist_patient"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id"), nullable=False, index=True)
    patient_id = Column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="waiting")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("deduplication_key", name="uq_notification_deduplication"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(String(10), nullable=False, default="in_app")
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    deduplication_key = Column(String(200), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AccountAction(Base):
    __tablename__ = "account_actions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    purpose = Column(String(20), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PrivacyRequest(Base):
    __tablename__ = "privacy_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), unique=True, nullable=False
    )
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="bdt")
    status = Column(String(20), nullable=False, default="pending")
    provider = Column(String(20), nullable=False, default="cash", server_default="cash")
    is_test = Column(Boolean, nullable=False, default=False, server_default="false")
    checkout_attempt = Column(Integer, nullable=False, default=0, server_default="0")
    provider_reference = Column(String(200), unique=True, nullable=True)
    refund_reference = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    paid_at = Column(DateTime(timezone=True), nullable=True)


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"
    __table_args__ = (
        UniqueConstraint("doctor_id", "exception_date", name="uq_doctor_exception_date"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = Column(
        UUID(as_uuid=True), ForeignKey("doctor_profiles.id"), nullable=False, index=True
    )
    exception_date = Column(Date, nullable=False)
    reason = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
