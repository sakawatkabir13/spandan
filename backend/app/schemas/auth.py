import re
from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole
from app.schemas.user import UserResponse


def clean_and_validate_phone(v: str) -> str:
    v_clean = v.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if len(v_clean) < 10:
        raise ValueError("Please enter a valid phone number with at least 10 digits")
    if v_clean.startswith("01") and len(v_clean) == 11:
        v_clean = "+88" + v_clean
    elif not v_clean.startswith("+"):
        if v_clean.startswith("8801"):
            v_clean = "+" + v_clean
        elif v_clean.startswith("1") and len(v_clean) == 10:
            v_clean = "+880" + v_clean
        else:
            v_clean = "+" + v_clean
    if not re.fullmatch(r"\+[1-9]\d{9,14}", v_clean):
        raise ValueError("Please enter a valid phone number")
    return v_clean


class RegisterPatientRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Must be at least 8 characters")
    phone_number: str = Field(..., description="Bangladeshi +880 format e.g. +8801712345678")
    full_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return clean_and_validate_phone(v)


class RegisterDoctorRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    phone_number: str
    full_name: str = Field(..., min_length=2)
    medical_registration_number: str = Field(..., min_length=3)
    current_workplace: Optional[str] = None
    years_of_experience: int = Field(default=0, ge=0)
    biography: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return clean_and_validate_phone(v)


class RegisterAssistantRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    phone_number: str
    full_name: str
    doctor_id: UUID

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return clean_and_validate_phone(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: UserRole
    user: Optional[UserResponse] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
