from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies.auth import require_roles
from app.core.exceptions import SpandanException, create_success_response
from app.db.session import get_db
from app.models.doctor import AssistantAssignment
from app.models.user import User, UserRole
from app.schemas.common import ApiResponse
from app.services.permissions import require_doctor_access

router = APIRouter(prefix="/assistants", tags=["Assistant assignments"])


class AssignmentUpdate(BaseModel):
    is_active: bool
    can_manage_schedules: bool
    can_manage_appointments: bool
    can_update_queue: bool


class AssistantSummary(BaseModel):
    email: str
    phone_number: str | None = None
    model_config = ConfigDict(from_attributes=True)


class AssignmentResponse(AssignmentUpdate):
    id: UUID
    doctor_id: UUID
    assistant_user_id: UUID
    assistant: AssistantSummary
    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=ApiResponse[List[AssignmentResponse]])
async def list_assignments(
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMINISTRATOR)),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AssistantAssignment)
        .options(selectinload(AssistantAssignment.assistant))
        .order_by(AssistantAssignment.assigned_at.desc())
    )
    if current_user.role == UserRole.DOCTOR:
        stmt = stmt.where(AssistantAssignment.doctor_id == current_user.doctor_profile.id)
    return create_success_response(
        message="Assistant assignments fetched.", data=list((await db.scalars(stmt)).all())
    )


@router.patch("/{id}", response_model=ApiResponse[AssignmentResponse])
async def update_assignment(
    id: UUID,
    request: AssignmentUpdate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMINISTRATOR)),
    db: AsyncSession = Depends(get_db),
):
    assignment = await db.scalar(
        select(AssistantAssignment)
        .options(selectinload(AssistantAssignment.assistant))
        .where(AssistantAssignment.id == id)
    )
    if not assignment:
        raise SpandanException(code="NOT_FOUND", message="Assignment not found.", status_code=404)
    require_doctor_access(current_user, assignment.doctor_id, "can_manage_appointments")
    for key, value in request.model_dump().items():
        setattr(assignment, key, value)
    await db.commit()
    return create_success_response(message="Assistant permissions updated.", data=assignment)
