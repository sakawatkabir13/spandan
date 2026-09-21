from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import DoctorProfile
from app.models.schedule import Schedule
from app.repositories.base import BaseRepository


class AppointmentRepository(BaseRepository[Appointment]):
    def __init__(self):
        super().__init__(Appointment)

    async def get_by_id_with_details(self, db: AsyncSession, appointment_id: UUID) -> Optional[Appointment]:
        result = await db.execute(
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.patient),
                selectinload(Appointment.doctor).selectinload(DoctorProfile.specializations),
                selectinload(Appointment.doctor).selectinload(DoctorProfile.qualifications),
                selectinload(Appointment.chamber),
                selectinload(Appointment.schedule).selectinload(Schedule.queue_state),
                selectinload(Appointment.schedule).selectinload(Schedule.chamber),
            )
            .where(Appointment.id == appointment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_schedule_id(
        self, db: AsyncSession, schedule_id: UUID, active_only: bool = False
    ) -> List[Appointment]:
        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.patient),
                selectinload(Appointment.doctor).selectinload(DoctorProfile.specializations),
                selectinload(Appointment.doctor).selectinload(DoctorProfile.qualifications),
                selectinload(Appointment.chamber),
                selectinload(Appointment.schedule).selectinload(Schedule.queue_state),
                selectinload(Appointment.schedule).selectinload(Schedule.chamber),
            )
            .where(Appointment.schedule_id == schedule_id)
        )
        if active_only:
            stmt = stmt.where(Appointment.appointment_status != AppointmentStatus.CANCELLED)
        stmt = stmt.order_by(Appointment.serial_number)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_patient_id(self, db: AsyncSession, patient_id: UUID) -> List[Appointment]:
        result = await db.execute(
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.doctor).selectinload(DoctorProfile.specializations),
                selectinload(Appointment.doctor).selectinload(DoctorProfile.qualifications),
                selectinload(Appointment.chamber),
                selectinload(Appointment.schedule).selectinload(Schedule.queue_state),
                selectinload(Appointment.schedule).selectinload(Schedule.chamber),
            )
            .where(Appointment.patient_id == patient_id)
            .order_by(Appointment.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_max_serial(self, db: AsyncSession, schedule_id: UUID) -> int:
        result = await db.execute(
            select(func.max(Appointment.serial_number)).where(
                Appointment.schedule_id == schedule_id,
            )
        )
        val = result.scalar()
        return val if val is not None else 0

    async def count_active_by_schedule(self, db: AsyncSession, schedule_id: UUID) -> int:
        result = await db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.schedule_id == schedule_id,
                Appointment.appointment_status != AppointmentStatus.CANCELLED,
            )
        )
        return result.scalar() or 0

    async def check_patient_already_booked(
        self, db: AsyncSession, schedule_id: UUID, patient_id: UUID
    ) -> bool:
        result = await db.execute(
            select(Appointment).where(
                Appointment.schedule_id == schedule_id,
                Appointment.patient_id == patient_id,
                Appointment.appointment_status != AppointmentStatus.CANCELLED,
            )
        )
        return result.scalar_one_or_none() is not None


appointment_repo = AppointmentRepository()
