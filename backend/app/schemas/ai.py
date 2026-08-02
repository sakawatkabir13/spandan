from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.recommendation import UrgencyLevel


class SymptomCheckRequest(BaseModel):
    symptoms_text: str = Field(..., min_length=5, max_length=1500)
    age: Optional[int] = Field(None, ge=0, le=120)
    gender: Optional[str] = None
    duration_days: Optional[int] = Field(None, ge=0)


class SpecialistRecommendationResponse(BaseModel):
    id: UUID
    patient_id: Optional[UUID] = None
    symptoms_text: str
    recommended_specialization_id: Optional[UUID] = None
    recommended_specialization_name: str
    alternative_specialization_name: Optional[str] = None
    urgency_level: UrgencyLevel
    reasoning_summary: str
    safety_message: Optional[str] = None
    disclaimer: str
    model_identifier: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
