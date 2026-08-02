from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


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
