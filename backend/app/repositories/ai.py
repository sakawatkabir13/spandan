from typing import List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation import SpecialistRecommendation
from app.repositories.base import BaseRepository


class RecommendationRepository(BaseRepository[SpecialistRecommendation]):
    def __init__(self):
        super().__init__(SpecialistRecommendation)

    async def get_by_patient_id(
        self, db: AsyncSession, patient_id: UUID
    ) -> List[SpecialistRecommendation]:
        result = await db.execute(
            select(SpecialistRecommendation)
            .where(SpecialistRecommendation.patient_id == patient_id)
            .order_by(SpecialistRecommendation.created_at.desc())
        )
        return list(result.scalars().all())


recommendation_repo = RecommendationRepository()
