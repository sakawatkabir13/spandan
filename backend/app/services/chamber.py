from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SpandanException
from app.models.chamber import Chamber
from app.models.user import User, UserRole
from app.repositories.chamber import chamber_repo
from app.repositories.doctor import doctor_repo
from app.schemas.chamber import ChamberCreate, ChamberUpdate


class ChamberService:
    async def create_chamber(
        self, db: AsyncSession, current_user: User, request: ChamberCreate
    ) -> Chamber:
        doc_profile = await doctor_repo.get_by_user_id_with_details(db, current_user.id)
        if not doc_profile:
            raise SpandanException(
                code="FORBIDDEN",
                message="Only registered doctors can create chambers.",
                status_code=403,
            )
        obj_in = request.model_dump()
        obj_in["doctor_id"] = doc_profile.id
        return await chamber_repo.create(db, obj_in)

    async def get_doctor_chambers(
        self, db: AsyncSession, doctor_id: UUID, only_active: bool = True
    ) -> List[Chamber]:
        if only_active:
            return await chamber_repo.get_active_by_doctor_id(db, doctor_id)
        return await chamber_repo.get_by_doctor_id(db, doctor_id)

    async def get_chamber(self, db: AsyncSession, chamber_id: UUID) -> Chamber:
        chamber = await chamber_repo.get_by_id(db, chamber_id)
        if not chamber:
            raise SpandanException(
                code="NOT_FOUND", message="Chamber not found.", status_code=404
            )
        return chamber

    async def update_chamber(
        self,
        db: AsyncSession,
        current_user: User,
        chamber_id: UUID,
        request: ChamberUpdate,
    ) -> Chamber:
        chamber = await self.get_chamber(db, chamber_id)
        doc_profile = await doctor_repo.get_by_user_id_with_details(db, current_user.id)
        if not doc_profile or chamber.doctor_id != doc_profile.id:
            if current_user.role != UserRole.ADMINISTRATOR:
                raise SpandanException(
                    code="FORBIDDEN",
                    message="You do not have permission to modify this chamber.",
                    status_code=403,
                )
        update_data = request.model_dump(exclude_unset=True)
        return await chamber_repo.update(db, chamber, update_data)

    async def delete_chamber(
        self, db: AsyncSession, current_user: User, chamber_id: UUID
    ) -> bool:
        chamber = await self.get_chamber(db, chamber_id)
        doc_profile = await doctor_repo.get_by_user_id_with_details(db, current_user.id)
        if not doc_profile or chamber.doctor_id != doc_profile.id:
            if current_user.role != UserRole.ADMINISTRATOR:
                raise SpandanException(
                    code="FORBIDDEN",
                    message="You do not have permission to delete this chamber.",
                    status_code=403,
                )
        from sqlalchemy import select

        from app.models.schedule import Schedule, ScheduleStatus
        active = await db.scalar(select(Schedule.id).where(Schedule.chamber_id == chamber_id, Schedule.status.in_([ScheduleStatus.OPEN, ScheduleStatus.FULL])).limit(1))
        if active:
            raise SpandanException(code="CONFLICT", message="Close or cancel active sessions before removing this chamber.", status_code=409)
        await chamber_repo.update(db, chamber, {"is_active": False})
        return True


chamber_service = ChamberService()
