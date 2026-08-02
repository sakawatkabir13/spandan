from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.user import UserRole
from app.schemas.doctor import DoctorProfileResponse


class PatientProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    profile_photo_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    profile_photo_url: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    phone_number: Optional[str] = None
    role: UserRole
    is_active: bool
    is_phone_verified: bool
    is_email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    patient_profile: Optional[PatientProfileResponse] = None
    doctor_profile: Optional[DoctorProfileResponse] = None
    full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
