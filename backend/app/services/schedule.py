from datetime import date
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SpandanException
from app.models.schedule import Schedule, QueueState
from app.models.user import User, UserRole
from app.repositories.chamber import chamber_repo
from app.repositories.doctor import doctor_repo
from app.repositories.schedule import schedule_repo, queue_repo
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate, QueueStateUpdate


class ScheduleService:
    async def create_schedule(
        self, db: AsyncSession, current_user: User, request: ScheduleCreate
    ) -> Schedule:
        chamber = await chamber_repo.get_by_id(db, request.chamber_id)
        if not chamber:
            raise SpandanException(
                code="NOT_FOUND", message="Specified chamber does not exist.", status_code=404
            )

        doc_profile = await doctor_repo.get_by_user_id_with_details(db, current_user.id)
        if not doc_profile or chamber.doctor_id != doc_profile.id:
            # Check if current user is an assistant assigned to this doctor
            if current_user.role == UserRole.ASSISTANT:
                # verify assignment
                assigned = False
                for assignment in current_user.assistant_assignments:
                    if assignment.doctor_id == chamber.doctor_id and assignment.is_active and assignment.can_manage_schedules:
                        assigned = True
                        break
                if not assigned:
                    raise SpandanException(
                        code="FORBIDDEN",
                        message="You do not have permission to manage schedules for this doctor.",
                        status_code=403,
                    )
            elif current_user.role != UserRole.ADMINISTRATOR:
                raise SpandanException(
                    code="FORBIDDEN",
                    message="You do not have permission to create schedules for this chamber.",
                    status_code=403,
                )

        obj_in = request.model_dump()
        obj_in["doctor_id"] = chamber.doctor_id
        obj_in["created_by_user_id"] = current_user.id
        schedule = Schedule(**obj_in)
        db.add(schedule)
        await db.flush()

        queue_state = QueueState(
            schedule_id=schedule.id,
            current_serial=0,
            delay_minutes=0,
            status_message="Queue not started yet.",
            updated_by_user_id=current_user.id,
        )
        db.add(queue_state)
        await db.commit()
        return await schedule_repo.get_by_id_with_queue(db, schedule.id)

    async def get_schedule(self, db: AsyncSession, schedule_id: UUID) -> Schedule:
        schedule = await schedule_repo.get_by_id_with_queue(db, schedule_id)
        if not schedule:
            raise SpandanException(
                code="NOT_FOUND", message="Schedule not found.", status_code=404
            )
        return schedule

    async def get_doctor_schedules(
        self, db: AsyncSession, doctor_id: UUID, from_date: Optional[date] = None
    ) -> List[Schedule]:
        return await schedule_repo.get_by_doctor_id(db, doctor_id, from_date)

    async def get_chamber_schedules(
        self, db: AsyncSession, chamber_id: UUID, from_date: Optional[date] = None
    ) -> List[Schedule]:
        return await schedule_repo.get_by_chamber_id(db, chamber_id, from_date)

    async def update_schedule(
        self,
        db: AsyncSession,
        current_user: User,
        schedule_id: UUID,
        request: ScheduleUpdate,
    ) -> Schedule:
        schedule = await self.get_schedule(db, schedule_id)
        doc_profile = await doctor_repo.get_by_user_id_with_details(db, current_user.id)
        if not doc_profile or schedule.doctor_id != doc_profile.id:
            if current_user.role != UserRole.ADMINISTRATOR:
                raise SpandanException(
                    code="FORBIDDEN",
                    message="You do not have permission to update this schedule.",
                    status_code=403,
                )
        update_data = request.model_dump(exclude_unset=True)
        await schedule_repo.update(db, schedule, update_data)
        return await schedule_repo.get_by_id_with_queue(db, schedule.id)

    async def update_queue_state(
        self,
        db: AsyncSession,
        current_user: User,
        schedule_id: UUID,
        request: QueueStateUpdate,
    ) -> QueueState:
        schedule = await self.get_schedule(db, schedule_id)
        # Check permissions: doctor, assigned assistant, or admin
        allowed = False
        if current_user.role == UserRole.ADMINISTRATOR:
            allowed = True
        elif current_user.role == UserRole.DOCTOR:
            doc_profile = await doctor_repo.get_by_user_id_with_details(db, current_user.id)
            if doc_profile and schedule.doctor_id == doc_profile.id:
                allowed = True
        elif current_user.role == UserRole.ASSISTANT:
            for assignment in current_user.assistant_assignments:
                if assignment.doctor_id == schedule.doctor_id and assignment.is_active and assignment.can_update_queue:
                    allowed = True
                    break

        if not allowed:
            raise SpandanException(
                code="FORBIDDEN",
                message="You do not have permission to update the queue for this schedule.",
                status_code=403,
            )

        queue_state = await queue_repo.get_by_schedule_id(db, schedule.id)
        if not queue_state:
            queue_state = QueueState(schedule_id=schedule.id, current_serial=0, delay_minutes=0)
            db.add(queue_state)
            await db.flush()

        if request.current_serial is not None:
            queue_state.current_serial = request.current_serial
        if request.delay_minutes is not None:
            queue_state.delay_minutes = request.delay_minutes
        if request.status_message is not None:
            queue_state.status_message = request.status_message
        queue_state.updated_by_user_id = current_user.id

        await db.commit()
        await db.refresh(queue_state)
        return queue_state


schedule_service = ScheduleService()
