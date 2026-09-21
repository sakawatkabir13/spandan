from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChamberBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    address: str = Field(..., min_length=5)
    district: str
    area: str
    phone_number: Optional[str] = None
    consultation_fee: float = Field(..., ge=0)
    follow_up_fee: float = Field(..., ge=0)
    average_consultation_minutes: int = Field(default=15, gt=0)
    is_active: bool = True


class ChamberCreate(ChamberBase):
    pass


class ChamberUpdate(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, values):
        if isinstance(values, dict) and any(key in values and values[key] is None for key in ['name', 'address', 'district', 'area', 'consultation_fee', 'follow_up_fee', 'average_consultation_minutes', 'is_active']):
            raise ValueError("Required fields cannot be null")
        return values

    name: Optional[str] = Field(None, min_length=2, max_length=150)
    address: Optional[str] = Field(None, min_length=5)
    district: Optional[str] = None
    area: Optional[str] = None
    phone_number: Optional[str] = None
    consultation_fee: Optional[float] = Field(None, ge=0)
    follow_up_fee: Optional[float] = Field(None, ge=0)
    average_consultation_minutes: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None


class ChamberResponse(ChamberBase):
    id: UUID
    doctor_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
