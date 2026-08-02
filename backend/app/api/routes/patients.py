from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_roles
from app.core.exceptions import create_success_response, SpandanException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user import patient_repo
from app.schemas.common import ApiResponse
from app.schemas.user import PatientProfileResponse, PatientProfileUpdate

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/me", response_model=ApiResponse[PatientProfileResponse])
async def get_patient_profile(
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    profile = await patient_repo.get_by_user_id(db, current_user.id)
    if not profile:
        raise SpandanException(
            code="NOT_FOUND", message="Patient profile not found.", status_code=status.HTTP_404_NOT_FOUND
        )
    return create_success_response(message="Patient profile fetched.", data=profile)


@router.patch("/me", response_model=ApiResponse[PatientProfileResponse])
async def update_patient_profile(
    request: PatientProfileUpdate,
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    profile = await patient_repo.get_by_user_id(db, current_user.id)
    if not profile:
        raise SpandanException(
            code="NOT_FOUND", message="Patient profile not found.", status_code=status.HTTP_404_NOT_FOUND
        )
    update_data = request.model_dump(exclude_unset=True)
    updated_profile = await patient_repo.update(db, profile, update_data)
    return create_success_response(message="Patient profile updated.", data=updated_profile)
