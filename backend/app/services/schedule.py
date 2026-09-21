from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import SpandanException
from app.core.time import local_now, session_time
from app.models.appointment import AppointmentStatus
from app.models.audit import AuditLog
from app.models.doctor import DoctorProfile, DoctorVerificationStatus
from app.models.schedule import QueueState, Schedule, ScheduleStatus
from app.models.user import User, UserRole
from app.repositories.appointment import appointment_repo
from app.repositories.chamber import chamber_repo
from app.repositories.schedule import schedule_repo
from app.schemas.schedule import (
    QueueStateUpdate,
    RecurringScheduleCreate,
    ScheduleCreate,
    ScheduleUpdate,
)
from app.services.permissions import require_doctor_access


class ScheduleService:
    async def validate_session(self, db, schedule, exclude_id=None):
        if schedule.end_time <= schedule.start_time:
            raise SpandanException(
                code="VALIDATION_ERROR", message="Session end time must be after start time."
            )
        if schedule.status in (ScheduleStatus.OPEN, ScheduleStatus.FULL):
            doctor = await db.get(DoctorProfile, schedule.doctor_id)
            if doctor.verification_status != DoctorVerificationStatus.APPROVED:
                raise SpandanException(
                    code="DOCTOR_UNVERIFIED",
                    message="Administrator approval is required before opening a schedule.",
                    status_code=403,
                )
            if session_time(schedule, schedule.end_time) <= local_now():
                raise SpandanException(
                    code="VALIDATION_ERROR", message="Cannot open a session that has already ended."
                )
        if schedule.status not in (ScheduleStatus.CANCELLED, ScheduleStatus.COMPLETED):
            stmt = select(Schedule.id).where(
                Schedule.doctor_id == schedule.doctor_id,
                Schedule.schedule_date == schedule.schedule_date,
                Schedule.start_time < schedule.end_time,
                Schedule.end_time > schedule.start_time,
                Schedule.status.notin_([ScheduleStatus.CANCELLED, ScheduleStatus.COMPLETED]),
            )
            if exclude_id:
                stmt = stmt.where(Schedule.id != exclude_id)
            if await db.scalar(stmt.limit(1)):
                raise SpandanException(
                    code="CONFLICT",
                    message="This doctor already has an overlapping session.",
                    status_code=409,
                )

    async def create_schedule(
        self, db: AsyncSession, current_user: User, request: ScheduleCreate
    ) -> Schedule:
        chamber = await chamber_repo.get_by_id(db, request.chamber_id)
        if not chamber or not chamber.is_active:
            raise SpandanException(
                code="NOT_FOUND", message="Active chamber not found.", status_code=404
            )
        require_doctor_access(current_user, chamber.doctor_id, "can_manage_schedules")
        # Serialize session creation per doctor, including sessions at different chambers.
        await db.execute(
            select(DoctorProfile.id).where(DoctorProfile.id == chamber.doctor_id).with_for_update()
        )
        schedule = Schedule(
            **request.model_dump(), doctor_id=chamber.doctor_id, created_by_user_id=current_user.id
        )
        await self.validate_session(db, schedule)
        db.add(schedule)
        await db.flush()
        db.add(
            QueueState(
                schedule_id=schedule.id,
                current_serial=0,
                delay_minutes=0,
                status_message="Queue not started yet.",
                updated_by_user_id=current_user.id,
            )
        )
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                action="schedule.created",
                entity_type="schedule",
                entity_id=str(schedule.id),
                metadata_json={
                    "doctor_id": str(schedule.doctor_id),
                    "chamber_id": str(schedule.chamber_id),
                    "schedule_date": schedule.schedule_date.isoformat(),
                    "status": schedule.status.value,
                },
            )
        )
        await db.commit()
        return await schedule_repo.get_by_id_with_queue(db, schedule.id)

    async def create_recurring_schedules(
        self, db: AsyncSession, current_user: User, request: RecurringScheduleCreate
    ) -> List[Schedule]:
        chamber = await chamber_repo.get_by_id(db, request.chamber_id)
        if not chamber or not chamber.is_active:
            raise SpandanException(
                code="NOT_FOUND", message="Active chamber not found.", status_code=404
            )
        require_doctor_access(current_user, chamber.doctor_id, "can_manage_schedules")
        await db.execute(
            select(DoctorProfile.id)
            .where(DoctorProfile.id == chamber.doctor_id)
            .with_for_update()
        )
        dates = []
        current = request.start_date
        weekdays = set(request.weekdays)
        while current <= request.end_date:
            if current.weekday() in weekdays:
                dates.append(current)
            current += timedelta(days=1)
        if not dates:
            raise SpandanException(
                code="VALIDATION_ERROR",
                message="The selected date range contains none of the chosen weekdays.",
            )
        if len(dates) > 100:
            raise SpandanException(
                code="VALIDATION_ERROR",
                message="A maximum of 100 sessions can be created at once.",
            )

        created: List[Schedule] = []
        for schedule_date in dates:
            schedule = Schedule(
                chamber_id=request.chamber_id,
                doctor_id=chamber.doctor_id,
                schedule_date=schedule_date,
                start_time=request.start_time,
                end_time=request.end_time,
                maximum_patients=request.maximum_patients,
                average_consultation_minutes=request.average_consultation_minutes,
                status=request.status,
                created_by_user_id=current_user.id,
            )
            await self.validate_session(db, schedule)
            db.add(schedule)
            await db.flush()
            db.add(
                QueueState(
                    schedule_id=schedule.id,
                    current_serial=0,
                    delay_minutes=0,
                    status_message="Queue not started yet.",
                    updated_by_user_id=current_user.id,
                )
            )
            created.append(schedule)

        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                action="schedule.recurring_created",
                entity_type="schedule_series",
                metadata_json={
                    "doctor_id": str(chamber.doctor_id),
                    "chamber_id": str(chamber.id),
                    "start_date": request.start_date.isoformat(),
                    "end_date": request.end_date.isoformat(),
                    "weekdays": request.weekdays,
                    "created_count": len(created),
                },
            )
        )
        await db.commit()
        return [
            await schedule_repo.get_by_id_with_queue(db, schedule.id) for schedule in created
        ]

    async def get_schedule(self, db: AsyncSession, schedule_id: UUID) -> Schedule:
        schedule = await schedule_repo.get_by_id_with_queue(db, schedule_id)
        if not schedule:
            raise SpandanException(code="NOT_FOUND", message="Schedule not found.", status_code=404)
        return schedule

    async def get_my_schedules(self, db: AsyncSession, user: User) -> List[Schedule]:
        stmt = select(Schedule).options(
            selectinload(Schedule.queue_state), selectinload(Schedule.chamber)
        )
        if user.role == UserRole.DOCTOR:
            stmt = stmt.where(Schedule.doctor_id == user.doctor_profile.id)
        elif user.role == UserRole.ASSISTANT:
            ids = [a.doctor_id for a in user.assistant_assignments if a.is_active]
            stmt = stmt.where(Schedule.doctor_id.in_(ids))
        elif user.role != UserRole.ADMINISTRATOR:
            raise SpandanException(
                code="FORBIDDEN", message="Staff access required.", status_code=403
            )
        stmt = stmt.where(Schedule.schedule_date >= local_now().date()).order_by(
            Schedule.schedule_date, Schedule.start_time
        )
        return list((await db.scalars(stmt)).all())

    async def get_doctor_schedules(
        self, db: AsyncSession, doctor_id: UUID, from_date: Optional[date] = None
    ) -> List[Schedule]:
        return await schedule_repo.get_by_doctor_id(db, doctor_id, from_date or local_now().date())

    async def get_chamber_schedules(
        self, db: AsyncSession, chamber_id: UUID, from_date: Optional[date] = None
    ) -> List[Schedule]:
        return await schedule_repo.get_by_chamber_id(
            db, chamber_id, from_date or local_now().date()
        )

    async def update_schedule(
        self, db: AsyncSession, current_user: User, schedule_id: UUID, request: ScheduleUpdate
    ) -> Schedule:
        existing = await self.get_schedule(db, schedule_id)
        require_doctor_access(current_user, existing.doctor_id, "can_manage_schedules")
        await db.execute(
            select(DoctorProfile.id).where(DoctorProfile.id == existing.doctor_id).with_for_update()
        )
        schedule = await schedule_repo.get_by_id_with_queue(db, schedule_id, lock=True)
        changes = request.model_dump(exclude_unset=True)
        if any(v is None for k, v in changes.items() if k != "cancellation_reason"):
            raise SpandanException(
                code="VALIDATION_ERROR", message="Session fields cannot be null."
            )
        count = await appointment_repo.count_active_by_schedule(db, schedule_id)
        if count and any(
            k in changes for k in ("start_time", "end_time", "average_consultation_minutes")
        ):
            raise SpandanException(
                code="CONFLICT",
                message="Cancel existing bookings before changing session times.",
                status_code=409,
            )
        for key, value in changes.items():
            setattr(schedule, key, value)
        if schedule.maximum_patients < count:
            raise SpandanException(
                code="CONFLICT",
                message="Capacity cannot be lower than existing bookings.",
                status_code=409,
            )
        await self.validate_session(db, schedule, schedule.id)
        if schedule.status == ScheduleStatus.CANCELLED:
            for appointment in await appointment_repo.get_by_schedule_id(db, schedule_id):
                if appointment.appointment_status not in (
                    AppointmentStatus.COMPLETED,
                    AppointmentStatus.CANCELLED,
                ):
                    appointment.appointment_status = AppointmentStatus.CANCELLED
                    appointment.cancellation_reason = (
                        request.cancellation_reason or "Session cancelled by chamber."
                    )
                    appointment.cancelled_at = local_now()
        elif schedule.status in (ScheduleStatus.OPEN, ScheduleStatus.FULL):
            schedule.status = (
                ScheduleStatus.FULL if count >= schedule.maximum_patients else ScheduleStatus.OPEN
            )
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                action="schedule.updated",
                entity_type="schedule",
                entity_id=str(schedule.id),
                metadata_json={
                    "changed_fields": sorted(changes.keys()),
                    "status": schedule.status.value,
                },
            )
        )
        await db.commit()
        return await schedule_repo.get_by_id_with_queue(db, schedule.id)

    async def queue_for_update(self, db, user, schedule_id):
        schedule = await schedule_repo.get_by_id_with_queue(db, schedule_id, lock=True)
        if not schedule:
            raise SpandanException(code="NOT_FOUND", message="Schedule not found.", status_code=404)
        require_doctor_access(user, schedule.doctor_id, "can_update_queue")
        if schedule.status in (
            ScheduleStatus.DRAFT,
            ScheduleStatus.CANCELLED,
            ScheduleStatus.COMPLETED,
        ):
            raise SpandanException(
                code="SCHEDULE_CLOSED", message="This session's queue is not active."
            )
        return schedule

    async def update_queue_state(
        self, db: AsyncSession, current_user: User, schedule_id: UUID, request: QueueStateUpdate
    ) -> QueueState:
        schedule = await self.queue_for_update(db, current_user, schedule_id)
        queue = schedule.queue_state
        if request.current_serial is not None and request.current_serial != queue.current_serial:
            raise SpandanException(
                code="VALIDATION_ERROR",
                message="Use Call Next or update a patient's consultation status to advance the queue.",
            )
        for key, value in request.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(queue, key, value)
        queue.updated_by_user_id = current_user.id
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                action="queue.updated",
                entity_type="schedule",
                entity_id=str(schedule.id),
                metadata_json={
                    "current_serial": queue.current_serial,
                    "delay_minutes": queue.delay_minutes,
                },
            )
        )
        await db.commit()
        await db.refresh(queue)
        return queue

    async def increment_queue(
        self, db: AsyncSession, current_user: User, schedule_id: UUID
    ) -> QueueState:
        schedule = await self.queue_for_update(db, current_user, schedule_id)
        queue = schedule.queue_state
        appointments = await appointment_repo.get_by_schedule_id(db, schedule_id)
        waiting = {
            AppointmentStatus.BOOKED,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.WAITING,
        }
        next_patient = next((a for a in appointments if a.appointment_status in waiting), None)
        for appointment in appointments:
            if appointment.appointment_status == AppointmentStatus.IN_CONSULTATION:
                appointment.appointment_status = AppointmentStatus.COMPLETED
                appointment.actual_consultation_completed_at = local_now()
        if next_patient:
            next_patient.appointment_status = AppointmentStatus.IN_CONSULTATION
            next_patient.actual_consultation_started_at = local_now()
            queue.current_serial = next_patient.serial_number
            queue.status_message = (
                f"Consultation in progress for Serial #{next_patient.serial_number}."
            )
        else:
            queue.current_serial = 0
            queue.status_message = "No patients waiting."
        queue.updated_by_user_id = current_user.id
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                action="queue.advanced",
                entity_type="schedule",
                entity_id=str(schedule.id),
                metadata_json={"current_serial": queue.current_serial},
            )
        )
        await db.commit()
        await db.refresh(queue)
        return queue


schedule_service = ScheduleService()
