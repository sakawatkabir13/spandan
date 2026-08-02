from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.core.exceptions import create_success_response
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.chamber import ChamberCreate, ChamberResponse, ChamberUpdate
from app.schemas.common import ApiResponse
from app.services.chamber import chamber_service

router = APIRouter(prefix="/chambers", tags=["Chambers"])


@router.post("", response_model=ApiResponse[ChamberResponse], status_code=status.HTTP_201_CREATED)
async def create_chamber(
    request: ChamberCreate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMINISTRATOR)),
    db: AsyncSession = Depends(get_db),
):
    chamber = await chamber_service.create_chamber(db, current_user, request)
    return create_success_response(message="Chamber created successfully.", data=chamber)


@router.get("/doctor/{doctor_id}", response_model=ApiResponse[List[ChamberResponse]])
async def get_doctor_chambers(
    doctor_id: UUID,
    only_active: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    chambers = await chamber_service.get_doctor_chambers(db, doctor_id, only_active=only_active)
    return create_success_response(message="Chambers fetched successfully.", data=chambers)


@router.get("/{id}", response_model=ApiResponse[ChamberResponse])
async def get_chamber(id: UUID, db: AsyncSession = Depends(get_db)):
    chamber = await chamber_service.get_chamber(db, id)
    return create_success_response(message="Chamber fetched successfully.", data=chamber)


@router.patch("/{id}", response_model=ApiResponse[ChamberResponse])
async def update_chamber(
    id: UUID,
    request: ChamberUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    chamber = await chamber_service.update_chamber(db, current_user, id, request)
    return create_success_response(message="Chamber updated successfully.", data=chamber)


@router.delete("/{id}", response_model=ApiResponse[None])
async def delete_chamber(
    id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await chamber_service.delete_chamber(db, current_user, id)
    return create_success_response(message="Chamber deleted successfully.")
