from datetime import date, datetime, time
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.schedule import ScheduleStatus


class QueueStateResponse(BaseModel):
    id: UUID
    schedule_id: UUID
    current_serial: int
    delay_minutes: int
    status_message: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueueStateUpdate(BaseModel):
    current_serial: Optional[int] = Field(None, ge=0)
    delay_minutes: Optional[int] = Field(None, ge=0)
    status_message: Optional[str] = None


class ScheduleBase(BaseModel):
    chamber_id: UUID
    schedule_date: date
    start_time: time
    end_time: time
    maximum_patients: int = Field(..., gt=0)
    average_consultation_minutes: int = Field(default=15, gt=0)
    booking_open_at: Optional[datetime] = None
    booking_close_at: Optional[datetime] = None


class ScheduleCreate(ScheduleBase):
    status: ScheduleStatus = ScheduleStatus.OPEN


class ScheduleUpdate(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    maximum_patients: Optional[int] = Field(None, gt=0)
    average_consultation_minutes: Optional[int] = Field(None, gt=0)
    status: Optional[ScheduleStatus] = None
    cancellation_reason: Optional[str] = None


class ScheduleResponse(ScheduleBase):
    id: UUID
    doctor_id: UUID
    status: ScheduleStatus
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    queue_state: Optional[QueueStateResponse] = None

    model_config = ConfigDict(from_attributes=True)
