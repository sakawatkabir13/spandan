from datetime import date
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.schedule import Schedule, QueueState
from app.repositories.base import BaseRepository


class ScheduleRepository(BaseRepository[Schedule]):
    def __init__(self):
        super().__init__(Schedule)

    async def get_by_id_with_queue(self, db: AsyncSession, schedule_id: UUID) -> Optional[Schedule]:
        result = await db.execute(
            select(Schedule).options(selectinload(Schedule.queue_state)).where(Schedule.id == schedule_id)
        )
        return result.scalar_one_or_none()

    async def get_by_doctor_id(
        self, db: AsyncSession, doctor_id: UUID, from_date: Optional[date] = None
    ) -> List[Schedule]:
        stmt = select(Schedule).options(selectinload(Schedule.queue_state)).where(Schedule.doctor_id == doctor_id)
        if from_date:
            stmt = stmt.where(Schedule.schedule_date >= from_date)
        stmt = stmt.order_by(Schedule.schedule_date, Schedule.start_time)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_chamber_id(
        self, db: AsyncSession, chamber_id: UUID, from_date: Optional[date] = None
    ) -> List[Schedule]:
        stmt = select(Schedule).options(selectinload(Schedule.queue_state)).where(Schedule.chamber_id == chamber_id)
        if from_date:
            stmt = stmt.where(Schedule.schedule_date >= from_date)
        stmt = stmt.order_by(Schedule.schedule_date, Schedule.start_time)
        result = await db.execute(stmt)
        return list(result.scalars().all())


class QueueStateRepository(BaseRepository[QueueState]):
    def __init__(self):
        super().__init__(QueueState)

    async def get_by_schedule_id(self, db: AsyncSession, schedule_id: UUID) -> Optional[QueueState]:
        result = await db.execute(select(QueueState).where(QueueState.schedule_id == schedule_id))
        return result.scalar_one_or_none()


schedule_repo = ScheduleRepository()
queue_repo = QueueStateRepository()
