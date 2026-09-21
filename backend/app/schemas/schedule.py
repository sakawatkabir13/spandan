from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.schedule import ScheduleStatus
from app.schemas.chamber import ChamberResponse


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

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time.tzinfo or self.end_time.tzinfo:
            raise ValueError("Session times must be local chamber times without an offset")
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        if self.booking_open_at and self.booking_close_at:
            if not self.booking_open_at.tzinfo or not self.booking_close_at.tzinfo:
                raise ValueError("Booking timestamps must include a timezone")
            if self.booking_close_at <= self.booking_open_at:
                raise ValueError("Booking close must be after booking open")
        return self


class RecurringScheduleCreate(BaseModel):
    chamber_id: UUID
    start_date: date
    end_date: date
    weekdays: List[int] = Field(..., min_length=1, max_length=7)
    start_time: time
    end_time: time
    maximum_patients: int = Field(..., gt=0)
    average_consultation_minutes: int = Field(default=15, gt=0)
    status: ScheduleStatus = ScheduleStatus.OPEN

    @model_validator(mode="after")
    def validate_recurrence(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date")
        if (self.end_date - self.start_date).days > 180:
            raise ValueError("Recurring schedules can cover at most 180 days")
        if self.start_time.tzinfo or self.end_time.tzinfo:
            raise ValueError("Session times must be local chamber times without an offset")
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("Weekdays must use 0 for Monday through 6 for Sunday")
        self.weekdays = sorted(set(self.weekdays))
        return self


class ScheduleUpdate(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, values):
        if isinstance(values, dict) and any(key in values and values[key] is None for key in ['start_time', 'end_time', 'maximum_patients', 'average_consultation_minutes', 'status']):
            raise ValueError("Required fields cannot be null")
        return values

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
    chamber: Optional[ChamberResponse] = None

    model_config = ConfigDict(from_attributes=True)
