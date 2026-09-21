from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.doctor import DoctorProfile
from app.models.user import PatientProfile, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def _profile_options(self):
        return [
            selectinload(User.patient_profile),
            selectinload(User.assistant_assignments),
            selectinload(User.doctor_profile).selectinload(DoctorProfile.qualifications),
            selectinload(User.doctor_profile).selectinload(DoctorProfile.specializations),
        ]

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(*self._profile_options())
            .where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, db: AsyncSession, phone: str) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(*self._profile_options())
            .where(User.phone_number == phone)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_profiles(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(*self._profile_options())
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()


class PatientProfileRepository(BaseRepository[PatientProfile]):
    def __init__(self):
        super().__init__(PatientProfile)

    async def get_by_user_id(self, db: AsyncSession, user_id: UUID) -> Optional[PatientProfile]:
        result = await db.execute(
            select(PatientProfile).where(PatientProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()


user_repo = UserRepository()
patient_repo = PatientProfileRepository()
