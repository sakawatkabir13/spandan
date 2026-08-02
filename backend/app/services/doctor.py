from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import SpandanException
from app.models.doctor import (
    DoctorProfile,
    DoctorVerificationStatus,
    Qualification,
    Specialization,
)
from app.models.user import User, UserRole
from app.repositories.doctor import doctor_repo, specialization_repo
from app.schemas.doctor import DoctorProfileUpdate, DoctorVerificationRequest


class DoctorService:
    async def get_doctor_profile(self, db: AsyncSession, doctor_id: UUID) -> DoctorProfile:
        profile = await doctor_repo.get_by_id_with_details(db, doctor_id)
        if not profile:
            raise SpandanException(
                code="NOT_FOUND", message="Doctor profile not found.", status_code=404
            )
        return profile

    async def get_doctor_profile_by_user(self, db: AsyncSession, user_id: UUID) -> DoctorProfile:
        profile = await doctor_repo.get_by_user_id_with_details(db, user_id)
        if not profile:
            raise SpandanException(
                code="NOT_FOUND", message="Doctor profile not found for this user.", status_code=404
            )
        return profile

    async def search_doctors(
        self,
        db: AsyncSession,
        specialization_id: Optional[UUID] = None,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DoctorProfile]:
        return await doctor_repo.search_doctors(
            db,
            specialization_id=specialization_id,
            query=query,
            status=DoctorVerificationStatus.APPROVED,
            skip=skip,
            limit=limit,
        )

    async def update_profile(
        self, db: AsyncSession, doctor_user: User, update_data: DoctorProfileUpdate
    ) -> DoctorProfile:
        profile = await self.get_doctor_profile_by_user(db, doctor_user.id)

        if update_data.full_name is not None:
            profile.full_name = update_data.full_name
        if update_data.biography is not None:
            profile.biography = update_data.biography
        if update_data.current_workplace is not None:
            profile.current_workplace = update_data.current_workplace
        if update_data.years_of_experience is not None:
            profile.years_of_experience = update_data.years_of_experience

        if update_data.specialization_ids is not None:
            result = await db.execute(
                select(Specialization).where(Specialization.id.in_(update_data.specialization_ids))
            )
            specs = list(result.scalars().all())
            profile.specializations.clear()
            for s in specs:
                profile.specializations.append(s)

        if update_data.qualifications is not None:
            profile.qualifications.clear()
            for q in update_data.qualifications:
                qual = Qualification(
                    doctor_id=profile.id,
                    title=q.title,
                    institution=q.institution,
                    completion_year=q.completion_year,
                )
                db.add(qual)

        await db.commit()
        return await doctor_repo.get_by_id_with_details(db, profile.id)

    async def get_all_specializations(self, db: AsyncSession) -> List[Specialization]:
        return await specialization_repo.get_active_all(db)

    async def verify_doctor(
        self, db: AsyncSession, admin_user: User, doctor_id: UUID, req: DoctorVerificationRequest
    ) -> DoctorProfile:
        profile = await self.get_doctor_profile(db, doctor_id)
        profile.verification_status = req.status
        profile.verification_notes = req.verification_notes
        profile.verified_by = admin_user.id
        from datetime import datetime, timezone

        profile.verified_at = datetime.now(timezone.utc)
        await db.commit()
        return await doctor_repo.get_by_id_with_details(db, profile.id)


doctor_service = DoctorService()
