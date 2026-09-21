from datetime import datetime, timedelta, timezone
from math import ceil
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SpandanException
from app.core.time import aware, session_time
from app.models.appointment import Appointment, AppointmentStatus, BookingSource
from app.models.audit import AuditLog
from app.models.doctor import DoctorProfile, DoctorVerificationStatus
from app.models.schedule import ScheduleStatus
from app.models.user import User, UserRole
from app.repositories.appointment import appointment_repo
from app.repositories.schedule import schedule_repo
from app.repositories.user import patient_repo, user_repo
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentStatusUpdate,
    SerialTrackingResponse,
)
from app.services.permissions import require_doctor_access

WAITING = {
    AppointmentStatus.BOOKED,
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.WAITING,
}
TERMINAL = {AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED, AppointmentStatus.ABSENT}
ALLOWED_TRANSITIONS = {
    AppointmentStatus.BOOKED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.WAITING,
        AppointmentStatus.IN_CONSULTATION,
        AppointmentStatus.SKIPPED,
        AppointmentStatus.ABSENT,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.WAITING,
        AppointmentStatus.IN_CONSULTATION,
        AppointmentStatus.SKIPPED,
        AppointmentStatus.ABSENT,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.CHECKED_IN: {
        AppointmentStatus.WAITING,
        AppointmentStatus.IN_CONSULTATION,
        AppointmentStatus.SKIPPED,
        AppointmentStatus.ABSENT,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.WAITING: {
        AppointmentStatus.IN_CONSULTATION,
        AppointmentStatus.SKIPPED,
        AppointmentStatus.ABSENT,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.SKIPPED: {
        AppointmentStatus.WAITING,
        AppointmentStatus.IN_CONSULTATION,
        AppointmentStatus.ABSENT,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.IN_CONSULTATION: {
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
    },
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AppointmentService:
    async def book_appointment(
        self, db: AsyncSession, current_user: User, request: AppointmentCreate
    ) -> Appointment:
        # All booking, cancellation and queue writers lock this row before reading capacity.
        schedule = await schedule_repo.get_by_id_with_queue(db, request.schedule_id, lock=True)
        if not schedule:
            raise SpandanException(code="NOT_FOUND", message="Schedule not found.", status_code=404)
        if current_user.role != UserRole.PATIENT:
            require_doctor_access(current_user, schedule.doctor_id, "can_manage_appointments")
        doctor = await db.get(DoctorProfile, schedule.doctor_id)
        if (
            doctor.verification_status != DoctorVerificationStatus.APPROVED
            or not schedule.chamber.is_active
            or not (await db.get(User, doctor.user_id)).is_active
        ):
            raise SpandanException(
                code="SCHEDULE_CLOSED", message="This doctor or chamber is unavailable for booking."
            )
        if schedule.status != ScheduleStatus.OPEN:
            raise SpandanException(
                code="SCHEDULE_CLOSED", message="This schedule is not currently open for bookings."
            )
        now = utcnow()
        if session_time(schedule, schedule.end_time) <= now:
            raise SpandanException(code="SCHEDULE_CLOSED", message="This session has ended.")
        if (schedule.booking_open_at and now < aware(schedule.booking_open_at)) or (
            schedule.booking_close_at and now >= aware(schedule.booking_close_at)
        ):
            raise SpandanException(
                code="SCHEDULE_CLOSED",
                message="Bookings are outside this session's booking window.",
            )
        if current_user.role == UserRole.PATIENT:
            patient = await patient_repo.get_by_user_id(db, current_user.id)
            source = BookingSource.ONLINE
        else:
            if request.patient_phone:
                patient_user = await user_repo.get_by_phone(db, request.patient_phone)
                patient = (
                    patient_user.patient_profile
                    if patient_user and patient_user.is_active
                    else None
                )
            elif request.patient_id:
                patient = await patient_repo.get_by_id(db, request.patient_id)
            else:
                raise SpandanException(
                    code="VALIDATION_ERROR",
                    message="A patient phone number is required for staff bookings.",
                )
            source = request.booking_source
        if not patient:
            raise SpandanException(
                code="NOT_FOUND",
                message="Registered patient not found. Please ask the patient to register first.",
                status_code=404,
            )
        if await appointment_repo.check_patient_already_booked(db, schedule.id, patient.id):
            raise SpandanException(
                code="CONFLICT",
                message="Patient already has an active appointment for this schedule.",
                status_code=409,
            )
        active_count = await appointment_repo.count_active_by_schedule(db, schedule.id)
        if active_count >= schedule.maximum_patients:
            raise SpandanException(
                code="SCHEDULE_FULL", message="This schedule has reached its patient limit."
            )
        serial = await appointment_repo.get_max_serial(db, schedule.id) + 1
        estimated = session_time(schedule, schedule.start_time) + timedelta(
            minutes=active_count * schedule.average_consultation_minutes
        )
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=schedule.doctor_id,
            chamber_id=schedule.chamber_id,
            schedule_id=schedule.id,
            serial_number=serial,
            booking_source=source,
            appointment_status=AppointmentStatus.BOOKED,
            estimated_consultation_at=estimated.astimezone(timezone.utc),
            patient_note=request.patient_note,
            booked_by_user_id=current_user.id,
        )
        db.add(appointment)
        await db.flush()
        if active_count + 1 >= schedule.maximum_patients:
            schedule.status = ScheduleStatus.FULL
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                action="appointment.booked",
                entity_type="appointment",
                entity_id=str(appointment.id),
                metadata_json={
                    "schedule_id": str(schedule.id),
                    "serial_number": serial,
                    "booking_source": source.value,
                },
            )
        )
        await db.commit()
        return await appointment_repo.get_by_id_with_details(db, appointment.id)

    async def get_patient_appointments(
        self, db: AsyncSession, current_user: User
    ) -> List[Appointment]:
        profile = await patient_repo.get_by_user_id(db, current_user.id)
        return await appointment_repo.get_by_patient_id(db, profile.id) if profile else []

    async def get_schedule_appointments(
        self, db: AsyncSession, current_user: User, schedule_id: UUID, active_only: bool = False
    ) -> List[Appointment]:
        schedule = await schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise SpandanException(code="NOT_FOUND", message="Schedule not found.", status_code=404)
        require_doctor_access(current_user, schedule.doctor_id, "can_manage_appointments")
        return await appointment_repo.get_by_schedule_id(db, schedule_id, active_only=active_only)

    async def update_status(
        self,
        db: AsyncSession,
        current_user: User,
        appointment_id: UUID,
        request: AppointmentStatusUpdate,
    ) -> Appointment:
        appointment = await appointment_repo.get_by_id_with_details(db, appointment_id)
        if not appointment:
            raise SpandanException(
                code="NOT_FOUND", message="Appointment not found.", status_code=404
            )
        schedule = await schedule_repo.get_by_id_with_queue(db, appointment.schedule_id, lock=True)
        await db.refresh(appointment)
        target = request.appointment_status
        if current_user.role == UserRole.PATIENT:
            profile = await patient_repo.get_by_user_id(db, current_user.id)
            if (
                not profile
                or appointment.patient_id != profile.id
                or target not in (AppointmentStatus.CANCELLED, AppointmentStatus.CONFIRMED)
            ):
                raise SpandanException(
                    code="FORBIDDEN",
                    message="Patients may only confirm or cancel their own appointments.",
                    status_code=403,
                )
            if (
                target == AppointmentStatus.CANCELLED
                and appointment.appointment_status == AppointmentStatus.IN_CONSULTATION
            ):
                raise SpandanException(
                    code="CONFLICT",
                    message="A consultation in progress cannot be cancelled by the patient.",
                    status_code=409,
                )
            if request.actual_consultation_started_at or request.actual_consultation_completed_at:
                raise SpandanException(
                    code="FORBIDDEN",
                    message="Patients cannot edit consultation timestamps.",
                    status_code=403,
                )
        else:
            require_doctor_access(current_user, appointment.doctor_id, "can_manage_appointments")
            if target in (AppointmentStatus.IN_CONSULTATION, AppointmentStatus.COMPLETED):
                require_doctor_access(current_user, appointment.doctor_id, "can_update_queue")
        previous = appointment.appointment_status
        if previous == target:
            return await appointment_repo.get_by_id_with_details(db, appointment.id)
        if previous in TERMINAL:
            raise SpandanException(
                code="CONFLICT",
                message="This appointment is already finished and cannot be reopened.",
                status_code=409,
            )
        if target not in ALLOWED_TRANSITIONS.get(previous, set()):
            raise SpandanException(
                code="CONFLICT",
                message=f"Appointment cannot move from {previous.value} to {target.value}.",
                status_code=409,
            )
        if target == AppointmentStatus.COMPLETED and previous != AppointmentStatus.IN_CONSULTATION:
            raise SpandanException(
                code="CONFLICT",
                message="Start the consultation before completing it.",
                status_code=409,
            )
        if previous == AppointmentStatus.IN_CONSULTATION and target not in TERMINAL:
            raise SpandanException(
                code="CONFLICT",
                message="Complete or cancel the current consultation first.",
                status_code=409,
            )
        if (
            schedule.status in (ScheduleStatus.CANCELLED, ScheduleStatus.COMPLETED)
            and target != AppointmentStatus.CANCELLED
        ):
            raise SpandanException(
                code="SCHEDULE_CLOSED", message="This session is no longer active."
            )
        queue = schedule.queue_state
        if target == AppointmentStatus.IN_CONSULTATION:
            others = await appointment_repo.get_by_schedule_id(db, schedule.id)
            if any(
                a.id != appointment.id and a.appointment_status == AppointmentStatus.IN_CONSULTATION
                for a in others
            ):
                raise SpandanException(
                    code="CONFLICT",
                    message="Complete the current consultation before starting another.",
                    status_code=409,
                )
            appointment.actual_consultation_started_at = utcnow()
            queue.current_serial = appointment.serial_number
            queue.status_message = (
                f"Consultation in progress for Serial #{appointment.serial_number}."
            )
        if target == AppointmentStatus.COMPLETED:
            appointment.actual_consultation_completed_at = utcnow()
        if target == AppointmentStatus.CANCELLED:
            appointment.cancelled_at = utcnow()
            appointment.cancellation_reason = request.cancellation_reason
            if (
                schedule.status == ScheduleStatus.FULL
                and session_time(schedule, schedule.end_time) > utcnow()
            ):
                schedule.status = ScheduleStatus.OPEN
        if target in TERMINAL and queue.current_serial == appointment.serial_number:
            queue.current_serial = 0
            queue.status_message = "Ready to call the next patient."
        if request.actual_consultation_started_at:
            appointment.actual_consultation_started_at = request.actual_consultation_started_at
        if request.actual_consultation_completed_at:
            appointment.actual_consultation_completed_at = request.actual_consultation_completed_at
        appointment.appointment_status = target
        queue.updated_by_user_id = current_user.id
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                action="appointment.status_updated",
                entity_type="appointment",
                entity_id=str(appointment.id),
                metadata_json={
                    "schedule_id": str(schedule.id),
                    "serial_number": appointment.serial_number,
                    "previous_status": previous.value,
                    "new_status": target.value,
                },
            )
        )
        await db.commit()
        return await appointment_repo.get_by_id_with_details(db, appointment.id)

    async def get_serial_tracking(
        self, db: AsyncSession, schedule_id: UUID, current_user: Optional[User] = None
    ) -> SerialTrackingResponse:
        schedule = await schedule_repo.get_by_id_with_queue(db, schedule_id)
        if not schedule:
            raise SpandanException(code="NOT_FOUND", message="Schedule not found.", status_code=404)
        queue = schedule.queue_state
        response = SerialTrackingResponse(
            schedule_id=schedule.id,
            current_serial_running=queue.current_serial if queue else 0,
            delay_minutes=queue.delay_minutes if queue else 0,
            status_message=queue.status_message if queue else None,
        )
        if current_user and current_user.role == UserRole.PATIENT:
            profile = await patient_repo.get_by_user_id(db, current_user.id)
            appointments = await appointment_repo.get_by_schedule_id(
                db, schedule_id, active_only=True
            )
            own = next((a for a in appointments if profile and a.patient_id == profile.id), None)
            if own:
                ahead = sum(
                    1
                    for a in appointments
                    if a.id != own.id
                    and (
                        a.appointment_status == AppointmentStatus.IN_CONSULTATION
                        or (a.serial_number < own.serial_number and a.appointment_status in WAITING)
                    )
                )
                if own.appointment_status not in WAITING:
                    ahead = 0
                now = utcnow()
                starts = session_time(schedule, schedule.start_time) + timedelta(
                    minutes=response.delay_minutes
                )
                baseline = max(now, starts)
                if own.appointment_status in WAITING:
                    estimate = baseline + timedelta(
                        minutes=ahead * schedule.average_consultation_minutes
                    )
                    if starts <= now:
                        estimate += timedelta(minutes=response.delay_minutes)
                else:
                    estimate = now
                response.your_serial_number = own.serial_number
                response.people_ahead = ahead
                response.estimated_waiting_minutes = max(
                    0, ceil((estimate - now).total_seconds() / 60)
                )
                response.estimated_consultation_time = estimate
        return response


appointment_service = AppointmentService()
