from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chamber import Chamber
from app.repositories.base import BaseRepository


class ChamberRepository(BaseRepository[Chamber]):
    def __init__(self):
        super().__init__(Chamber)

    async def get_by_doctor_id(self, db: AsyncSession, doctor_id: UUID) -> List[Chamber]:
        result = await db.execute(select(Chamber).where(Chamber.doctor_id == doctor_id))
        return list(result.scalars().all())

    async def get_active_by_doctor_id(self, db: AsyncSession, doctor_id: UUID) -> List[Chamber]:
        result = await db.execute(
            select(Chamber).where(Chamber.doctor_id == doctor_id, Chamber.is_active.is_(True))
        )
        return list(result.scalars().all())


chamber_repo = ChamberRepository()
