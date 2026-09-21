from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_optional_user, require_roles
from app.core.exceptions import create_success_response
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.ai import SpecialistRecommendationResponse, SymptomCheckRequest
from app.schemas.common import ApiResponse
from app.services.ai import triage_service

router = APIRouter(prefix="/ai", tags=["AI Symptom Checker & Triage"])


@router.post("/symptom-check", response_model=ApiResponse[SpecialistRecommendationResponse], status_code=status.HTTP_201_CREATED)
async def check_symptoms(
    request: SymptomCheckRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    recommendation = await triage_service.check_symptoms(db, current_user, request)
    return create_success_response(message="Symptom analysis complete.", data=recommendation)


@router.get("/recommendations/me", response_model=ApiResponse[List[SpecialistRecommendationResponse]])
async def get_my_recommendations(
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    recs = await triage_service.get_patient_recommendations(db, current_user)
    return create_success_response(message="Patient triage history fetched.", data=recs)
