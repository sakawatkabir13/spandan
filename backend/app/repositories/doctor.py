from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.doctor import (
    DoctorProfile,
    DoctorVerificationStatus,
    Qualification,
    Specialization,
)
from app.repositories.base import BaseRepository


class DoctorRepository(BaseRepository[DoctorProfile]):
    def __init__(self):
        super().__init__(DoctorProfile)

    async def get_by_id_with_details(self, db: AsyncSession, doctor_id: UUID) -> Optional[DoctorProfile]:
        result = await db.execute(
            select(DoctorProfile)
            .options(selectinload(DoctorProfile.qualifications), selectinload(DoctorProfile.specializations))
            .where(DoctorProfile.id == doctor_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id_with_details(self, db: AsyncSession, user_id: UUID) -> Optional[DoctorProfile]:
        result = await db.execute(
            select(DoctorProfile)
            .options(selectinload(DoctorProfile.qualifications), selectinload(DoctorProfile.specializations))
            .where(DoctorProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def search_doctors(
        self,
        db: AsyncSession,
        specialization_id: Optional[UUID] = None,
        district: Optional[UUID | str] = None,
        query: Optional[str] = None,
        status: DoctorVerificationStatus = DoctorVerificationStatus.APPROVED,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DoctorProfile]:
        stmt = (
            select(DoctorProfile)
            .options(selectinload(DoctorProfile.qualifications), selectinload(DoctorProfile.specializations))
            .where(DoctorProfile.verification_status == status)
        )

        if specialization_id:
            stmt = stmt.join(DoctorProfile.specializations).where(Specialization.id == specialization_id)

        if query:
            q_str = f"%{query.lower()}%"
            stmt = stmt.where(DoctorProfile.full_name.ilike(q_str))

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())


class SpecializationRepository(BaseRepository[Specialization]):
    def __init__(self):
        super().__init__(Specialization)

    async def get_active_all(self, db: AsyncSession) -> List[Specialization]:
        result = await db.execute(select(Specialization).where(Specialization.is_active == True))
        return list(result.scalars().all())


class QualificationRepository(BaseRepository[Qualification]):
    def __init__(self):
        super().__init__(Qualification)


doctor_repo = DoctorRepository()
specialization_repo = SpecializationRepository()
qualification_repo = QualificationRepository()
