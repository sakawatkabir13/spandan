import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UrgencyLevel(str, enum.Enum):
    ROUTINE = "routine"
    SOON = "soon"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class SpecialistRecommendation(Base):
    __tablename__ = "specialist_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    symptoms_text = Column(Text, nullable=False)
    recommended_specialization_id = Column(UUID(as_uuid=True), ForeignKey("specializations.id", ondelete="SET NULL"), nullable=True)
    recommended_specialization_name = Column(String, nullable=False)
    alternative_specialization_name = Column(String, nullable=True)
    urgency_level = Column(
        Enum(UrgencyLevel, name="urgencylevel", create_constraint=True),
        default=UrgencyLevel.ROUTINE,
        nullable=False,
    )
    reasoning_summary = Column(Text, nullable=True)
    safety_message = Column(Text, nullable=True)
    emergency_warning = Column(Text, nullable=True)
    disclaimer = Column(Text, nullable=True)
    model_identifier = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    patient = relationship("PatientProfile", back_populates="recommendations")
    recommended_specialization = relationship("Specialization")
