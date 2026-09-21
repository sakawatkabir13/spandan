from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.core.exceptions import create_success_response
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import ApiResponse
from app.schemas.schedule import (
    QueueStateResponse,
    QueueStateUpdate,
    RecurringScheduleCreate,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.services.schedule import schedule_service

router = APIRouter(prefix="/schedules", tags=["Schedules & Queue"])


@router.post("", response_model=ApiResponse[ScheduleResponse], status_code=status.HTTP_201_CREATED)
async def create_schedule(
    request: ScheduleCreate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR)),
    db: AsyncSession = Depends(get_db),
):
    schedule = await schedule_service.create_schedule(db, current_user, request)
    return create_success_response(message="Schedule created successfully.", data=schedule)


@router.post(
    "/recurring",
    response_model=ApiResponse[List[ScheduleResponse]],
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring_schedules(
    request: RecurringScheduleCreate,
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR)
    ),
    db: AsyncSession = Depends(get_db),
):
    schedules = await schedule_service.create_recurring_schedules(db, current_user, request)
    return create_success_response(
        message=f"{len(schedules)} recurring schedules created successfully.", data=schedules
    )


@router.get("/doctor/{doctor_id}", response_model=ApiResponse[List[ScheduleResponse]])
async def get_doctor_schedules(
    doctor_id: UUID,
    from_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    schedules = await schedule_service.get_doctor_schedules(db, doctor_id, from_date=from_date)
    return create_success_response(message="Schedules fetched successfully.", data=schedules)


@router.get("/chamber/{chamber_id}", response_model=ApiResponse[List[ScheduleResponse]])
async def get_chamber_schedules(
    chamber_id: UUID,
    from_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    schedules = await schedule_service.get_chamber_schedules(db, chamber_id, from_date=from_date)
    return create_success_response(message="Schedules fetched successfully.", data=schedules)


@router.get("/me", response_model=ApiResponse[List[ScheduleResponse]])
async def get_my_schedules(
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ASSISTANT, UserRole.ADMINISTRATOR)),
    db: AsyncSession = Depends(get_db),
):
    return create_success_response(message="Assigned schedules fetched.", data=await schedule_service.get_my_schedules(db, current_user))


@router.post("/{id}/queue/increment", response_model=ApiResponse[QueueStateResponse])
async def increment_queue(id: UUID, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    return create_success_response(message="Queue advanced.", data=await schedule_service.increment_queue(db, current_user, id))


@router.get("/{id}", response_model=ApiResponse[ScheduleResponse])
async def get_schedule(id: UUID, db: AsyncSession = Depends(get_db)):
    schedule = await schedule_service.get_schedule(db, id)
    return create_success_response(message="Schedule fetched successfully.", data=schedule)


@router.patch("/{id}", response_model=ApiResponse[ScheduleResponse])
async def update_schedule(
    id: UUID,
    request: ScheduleUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await schedule_service.update_schedule(db, current_user, id, request)
    return create_success_response(message="Schedule updated successfully.", data=schedule)


@router.patch("/{id}/queue", response_model=ApiResponse[QueueStateResponse])
async def update_queue_state(
    id: UUID,
    request: QueueStateUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await schedule_service.update_queue_state(db, current_user, id, request)
    return create_success_response(message="Queue status updated successfully.", data=queue)
