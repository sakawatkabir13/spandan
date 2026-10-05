from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.doctor import (
    DoctorProfile,
    DoctorVerificationStatus,
    Qualification,
    Specialization,
)
from app.models.user import User
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
        max_fee: Optional[float] = None,
        available_on: Optional[date] = None,
    ) -> List[DoctorProfile]:
        stmt = (
            select(DoctorProfile)
            .options(selectinload(DoctorProfile.qualifications), selectinload(DoctorProfile.specializations))
            .where(DoctorProfile.verification_status == status, DoctorProfile.user.has(User.is_active.is_(True)))
        )

        if not settings.DEMO_MODE:
            stmt = stmt.where(DoctorProfile.is_demo.is_(False))

        if specialization_id:
            stmt = stmt.join(DoctorProfile.specializations).where(Specialization.id == specialization_id)

        if query:
            q_str = f"%{query.lower()}%"
            stmt = stmt.where(or_(
                DoctorProfile.full_name.ilike(q_str),
                DoctorProfile.current_workplace.ilike(q_str),
                DoctorProfile.specializations.any(Specialization.name.ilike(q_str)),
                DoctorProfile.qualifications.any(Qualification.title.ilike(q_str)),
            ))

        from app.models.chamber import Chamber
        from app.models.schedule import Schedule, ScheduleStatus
        chamber_filters = [Chamber.is_active.is_(True)]
        if district:
            chamber_filters.append(Chamber.district.ilike(f"%{district}%"))
        if max_fee is not None:
            chamber_filters.append(Chamber.consultation_fee <= max_fee)
        if available_on:
            chamber_filters.append(Chamber.schedules.any(and_(Schedule.schedule_date == available_on, Schedule.status == ScheduleStatus.OPEN)))
        if district or max_fee is not None or available_on:
            stmt = stmt.where(DoctorProfile.chambers.any(and_(*chamber_filters)))

        stmt = stmt.order_by(DoctorProfile.full_name, DoctorProfile.id).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())


class SpecializationRepository(BaseRepository[Specialization]):
    def __init__(self):
        super().__init__(Specialization)

    async def get_active_all(self, db: AsyncSession) -> List[Specialization]:
        result = await db.execute(select(Specialization).where(Specialization.is_active.is_(True)))
        return list(result.scalars().all())


class QualificationRepository(BaseRepository[Qualification]):
    def __init__(self):
        super().__init__(Qualification)


doctor_repo = DoctorRepository()
specialization_repo = SpecializationRepository()
qualification_repo = QualificationRepository()
