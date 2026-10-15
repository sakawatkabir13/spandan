from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_roles
from app.core.exceptions import create_success_response
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.repositories.user import user_repo
from app.schemas.common import ApiResponse
from app.schemas.user import AuditLogResponse, UserResponse

router = APIRouter(prefix="/users", tags=["User administration"])


class UserStatusUpdate(BaseModel):
    is_active: bool


@router.get("/audit-logs", response_model=ApiResponse[List[AuditLogResponse]])
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    current_user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    logs = list((await db.scalars(stmt)).all())
    return create_success_response(message="Audit log fetched.", data=logs)


@router.get("", response_model=ApiResponse[List[UserResponse]])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(User)
        .options(*user_repo._profile_options())
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return create_success_response(message="Users fetched.", data=list(result.all()))


@router.patch("/{id}", response_model=ApiResponse[UserResponse])
async def update_user(
    id: UUID,
    request: UserStatusUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
    db: AsyncSession = Depends(get_db),
):
    from app.services.appointment_operations import update_user_status
    await update_user_status(db, current_user, id, request.is_active)
    user = await user_repo.get_by_id_with_profiles(db, id)
    return create_success_response(message="Account status updated.", data=user)
