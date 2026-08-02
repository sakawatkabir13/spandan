from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.appointment import AppointmentStatus, BookingSource


class AppointmentCreate(BaseModel):
    schedule_id: UUID
    patient_note: Optional[str] = None
    booking_source: BookingSource = BookingSource.ONLINE
    # For walk-in / assistant bookings where patient is not yet a registered online user, or booking for someone else
    patient_id: Optional[UUID] = None


class AppointmentStatusUpdate(BaseModel):
    appointment_status: AppointmentStatus
    cancellation_reason: Optional[str] = None
    actual_consultation_started_at: Optional[datetime] = None
    actual_consultation_completed_at: Optional[datetime] = None


class AppointmentResponse(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    chamber_id: UUID
    schedule_id: UUID
    serial_number: int
    booking_source: BookingSource
    appointment_status: AppointmentStatus
    estimated_consultation_at: Optional[datetime] = None
    actual_consultation_started_at: Optional[datetime] = None
    actual_consultation_completed_at: Optional[datetime] = None
    patient_note: Optional[str] = None
    cancellation_reason: Optional[str] = None
    booked_by_user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    cancelled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SerialTrackingResponse(BaseModel):
    schedule_id: UUID
    current_serial_running: int
    delay_minutes: int
    status_message: Optional[str] = None
    your_serial_number: Optional[int] = None
    people_ahead: Optional[int] = None
    estimated_waiting_minutes: Optional[int] = None
    estimated_consultation_time: Optional[datetime] = None
