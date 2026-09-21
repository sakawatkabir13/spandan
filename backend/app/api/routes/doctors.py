from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_roles
from app.core.exceptions import SpandanException, create_success_response
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import ApiResponse
from app.schemas.doctor import (
    DoctorProfileResponse,
    DoctorProfileUpdate,
    DoctorVerificationRequest,
    SpecializationResponse,
)
from app.services.doctor import doctor_service
from app.services.profile_photo import store_profile_photo

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("/specializations", response_model=ApiResponse[List[SpecializationResponse]])
async def get_specializations(db: AsyncSession = Depends(get_db)):
    specs = await doctor_service.get_all_specializations(db)
    return create_success_response(message="Specializations fetched.", data=specs)


@router.get("", response_model=ApiResponse[List[DoctorProfileResponse]])
async def search_doctors(
    specialization_id: Optional[UUID] = Query(None, description="Filter by specialization ID"),
    query: Optional[str] = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    doctors = await doctor_service.search_doctors(
        db, specialization_id=specialization_id, query=query, skip=skip, limit=limit
    )
    return create_success_response(message="Doctors fetched.", data=doctors)


@router.get("/me/profile", response_model=ApiResponse[DoctorProfileResponse])
async def get_my_doctor_profile(
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    profile = await doctor_service.get_doctor_profile_by_user(db, current_user.id)
    return create_success_response(message="Doctor profile fetched.", data=profile)


@router.patch("/me/profile", response_model=ApiResponse[DoctorProfileResponse])
async def update_my_doctor_profile(
    request: DoctorProfileUpdate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    profile = await doctor_service.update_profile(db, current_user, request)
    return create_success_response(message="Doctor profile updated.", data=profile)


@router.post("/me/profile/photo", response_model=ApiResponse[DoctorProfileResponse])
async def upload_doctor_photo(
    photo: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    profile = await doctor_service.get_doctor_profile_by_user(db, current_user.id)
    profile.profile_photo_url = await store_profile_photo(photo, profile.profile_photo_url)
    await db.commit()
    return create_success_response(
        message="Profile photo updated.",
        data=await doctor_service.get_doctor_profile(db, profile.id),
    )


@router.get("/admin/all", response_model=ApiResponse[List[DoctorProfileResponse]])
async def list_doctors_for_review(current_user: User = Depends(require_roles(UserRole.ADMINISTRATOR)), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.doctor import DoctorProfile
    doctors = await db.scalars(select(DoctorProfile).options(selectinload(DoctorProfile.specializations), selectinload(DoctorProfile.qualifications)).order_by(DoctorProfile.created_at.desc()))
    return create_success_response(message="Doctor registry fetched.", data=list(doctors.all()))


@router.post("/{id}/verify", response_model=ApiResponse[DoctorProfileResponse])
async def verify_doctor(id: UUID, request: DoctorVerificationRequest, current_user: User = Depends(require_roles(UserRole.ADMINISTRATOR)), db: AsyncSession = Depends(get_db)):
    profile = await doctor_service.verify_doctor(db, current_user, id, request)
    return create_success_response(message="Doctor verification updated.", data=profile)


@router.get("/{id}", response_model=ApiResponse[DoctorProfileResponse])
async def get_doctor_by_id(id: UUID, db: AsyncSession = Depends(get_db)):
    profile = await doctor_service.get_doctor_profile(db, id)
    if profile.verification_status.value != "approved":
        raise SpandanException(code="NOT_FOUND", message="Doctor profile not found.", status_code=404)
    return create_success_response(message="Doctor profile fetched.", data=profile)
