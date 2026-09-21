from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.doctor import DoctorVerificationStatus


class QualificationResponse(BaseModel):
    id: UUID
    title: str
    institution: str
    completion_year: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class QualificationCreate(BaseModel):
    title: str
    institution: str
    completion_year: Optional[int] = None


class SpecializationResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SpecializationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None


class DoctorProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    profile_photo_url: Optional[str] = None
    medical_registration_number: str
    biography: Optional[str] = None
    current_workplace: Optional[str] = None
    years_of_experience: int
    verification_status: DoctorVerificationStatus
    verification_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    qualifications: List[QualificationResponse] = []
    specializations: List[SpecializationResponse] = []

    model_config = ConfigDict(from_attributes=True)


class DoctorProfileUpdate(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, values):
        if isinstance(values, dict) and any(key in values and values[key] is None for key in ['full_name', 'years_of_experience']):
            raise ValueError("Required fields cannot be null")
        return values

    full_name: Optional[str] = None
    biography: Optional[str] = None
    current_workplace: Optional[str] = None
    years_of_experience: Optional[int] = Field(None, ge=0)
    specialization_ids: Optional[List[UUID]] = None
    qualifications: Optional[List[QualificationCreate]] = None


class DoctorVerificationRequest(BaseModel):
    status: DoctorVerificationStatus
    verification_notes: Optional[str] = None
