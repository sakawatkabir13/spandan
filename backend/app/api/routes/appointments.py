from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_current_active_user,
    get_optional_user,
    require_roles,
)
from app.core.exceptions import create_success_response
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusUpdate,
    SerialTrackingResponse,
)
from app.schemas.common import ApiResponse
from app.services.appointment import appointment_service

router = APIRouter(prefix="/appointments", tags=["Appointments & Serial Tracking"])


@router.post("", response_model=ApiResponse[AppointmentResponse], status_code=status.HTTP_201_CREATED)
async def book_appointment(
    request: AppointmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    appointment = await appointment_service.book_appointment(db, current_user, request)
    return create_success_response(message="Appointment booked successfully.", data=appointment)


@router.get("/me", response_model=ApiResponse[List[AppointmentResponse]])
async def get_my_appointments(
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    appointments = await appointment_service.get_patient_appointments(db, current_user)
    return create_success_response(message="Patient appointments fetched.", data=appointments)


@router.get("/schedule/{schedule_id}", response_model=ApiResponse[List[AppointmentResponse]])
async def get_schedule_appointments(
    schedule_id: UUID,
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    appointments = await appointment_service.get_schedule_appointments(
        db, current_user, schedule_id, active_only=active_only
    )
    return create_success_response(message="Schedule appointments fetched.", data=appointments)


@router.patch("/{id}/status", response_model=ApiResponse[AppointmentResponse])
async def update_appointment_status(
    id: UUID,
    request: AppointmentStatusUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    appointment = await appointment_service.update_status(db, current_user, id, request)
    return create_success_response(message="Appointment status updated.", data=appointment)


@router.get("/track/{schedule_id}", response_model=ApiResponse[SerialTrackingResponse])
async def track_serial(
    schedule_id: UUID,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    tracking = await appointment_service.get_serial_tracking(db, schedule_id, current_user=current_user)
    return create_success_response(message="Serial tracking info fetched.", data=tracking)
