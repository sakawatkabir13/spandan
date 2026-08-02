from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SpandanException
from app.models.appointment import Appointment, AppointmentStatus, BookingSource
from app.models.schedule import ScheduleStatus
from app.models.user import User, UserRole
from app.repositories.appointment import appointment_repo
from app.repositories.doctor import doctor_repo
from app.repositories.schedule import queue_repo, schedule_repo
from app.repositories.user import patient_repo
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentStatusUpdate,
    SerialTrackingResponse,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AppointmentService:
    async def book_appointment(
        self, db: AsyncSession, current_user: User, request: AppointmentCreate
    ) -> Appointment:
        schedule = await schedule_repo.get_by_id_with_queue(db, request.schedule_id)
        if not schedule:
            raise SpandanException(code="NOT_FOUND", message="Schedule not found.", status_code=404)

        if schedule.status != ScheduleStatus.OPEN:
            raise SpandanException(
                code="SCHEDULE_CLOSED",
                message="This schedule is not currently open for bookings.",
                status_code=400,
            )

        # Determine target patient_id
        patient_id: UUID
        if current_user.role == UserRole.PATIENT:
            pat_profile = await patient_repo.get_by_user_id(db, current_user.id)
            if not pat_profile:
                raise SpandanException(
                    code="NOT_FOUND", message="Patient profile not found for this user.", status_code=404
                )
            patient_id = pat_profile.id
        else:
            # Assistant, doctor, or admin booking on behalf of a patient
            if not request.patient_id:
                raise SpandanException(
                    code="VALIDATION_ERROR",
                    message="patient_id is required when booking as an assistant/doctor/admin.",
                    status_code=400,
                )
            patient_id = request.patient_id

        # Concurrency & Integrity Check: Ensure patient hasn't already booked this exact schedule
        already_booked = await appointment_repo.check_patient_already_booked(
            db, schedule.id, patient_id
        )
        if already_booked:
            raise SpandanException(
                code="CONFLICT",
                message="Patient already has an active appointment for this schedule.",
                status_code=409,
            )

        # Check capacity
        active_count = await appointment_repo.count_active_by_schedule(db, schedule.id)
        if active_count >= schedule.maximum_patients:
            schedule.status = ScheduleStatus.FULL
            await db.commit()
            raise SpandanException(
                code="SCHEDULE_FULL",
                message="This schedule has reached its maximum patient limit.",
                status_code=400,
            )

        # Assign serial number safely
        max_serial = await appointment_repo.get_max_serial(db, schedule.id)
        next_serial = max_serial + 1

        # Calculate estimated consultation datetime based on schedule date + start_time + offset
        from datetime import datetime as dt
        start_dt = dt.combine(schedule.schedule_date, schedule.start_time, tzinfo=timezone.utc)
        offset_mins = (next_serial - 1) * schedule.average_consultation_minutes
        estimated_time = start_dt + timedelta(minutes=offset_mins)

        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=schedule.doctor_id,
            chamber_id=schedule.chamber_id,
            schedule_id=schedule.id,
            serial_number=next_serial,
            booking_source=request.booking_source,
            appointment_status=AppointmentStatus.BOOKED,
            estimated_consultation_at=estimated_time,
            patient_note=request.patient_note,
            booked_by_user_id=current_user.id,
        )
        db.add(appointment)
        await db.flush()

        # If after this addition capacity reached, mark schedule FULL
        if active_count + 1 >= schedule.maximum_patients:
            schedule.status = ScheduleStatus.FULL

        await db.commit()
        return await appointment_repo.get_by_id_with_details(db, appointment.id)

    async def get_patient_appointments(self, db: AsyncSession, current_user: User) -> List[Appointment]:
        pat_profile = await patient_repo.get_by_user_id(db, current_user.id)
        if not pat_profile:
            return []
        return await appointment_repo.get_by_patient_id(db, pat_profile.id)

    async def get_schedule_appointments(
        self, db: AsyncSession, current_user: User, schedule_id: UUID, active_only: bool = False
    ) -> List[Appointment]:
        schedule = await schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise SpandanException(code="NOT_FOUND", message="Schedule not found.", status_code=404)

        # Check permissions: doctor, assigned assistant, or admin
        if current_user.role != UserRole.ADMINISTRATOR:
            if current_user.role == UserRole.DOCTOR:
                doc = await doctor_repo.get_by_user_id_with_details(db, current_user.id)
                if not doc or schedule.doctor_id != doc.id:
                    raise SpandanException(code="FORBIDDEN", message="Access denied.", status_code=403)
            elif current_user.role == UserRole.ASSISTANT:
                assigned = any(
                    a.doctor_id == schedule.doctor_id and a.is_active for a in current_user.assistant_assignments
                )
                if not assigned:
                    raise SpandanException(code="FORBIDDEN", message="Access denied.", status_code=403)
            else:
                raise SpandanException(code="FORBIDDEN", message="Access denied.", status_code=403)

        return await appointment_repo.get_by_schedule_id(db, schedule_id, active_only=active_only)

    async def update_status(
        self, db: AsyncSession, current_user: User, appointment_id: UUID, request: AppointmentStatusUpdate
    ) -> Appointment:
        appointment = await appointment_repo.get_by_id_with_details(db, appointment_id)
        if not appointment:
            raise SpandanException(code="NOT_FOUND", message="Appointment not found.", status_code=404)

        # Permission check: patient can only cancel their own. Doctor/assistant/admin can modify all statuses.
        if current_user.role == UserRole.PATIENT:
            pat_profile = await patient_repo.get_by_user_id(db, current_user.id)
            if not pat_profile or appointment.patient_id != pat_profile.id:
                raise SpandanException(code="FORBIDDEN", message="Not authorized to modify this appointment.", status_code=403)
            if request.appointment_status != AppointmentStatus.CANCELLED:
                raise SpandanException(code="FORBIDDEN", message="Patients can only cancel appointments.", status_code=403)
        else:
            if current_user.role == UserRole.DOCTOR:
                doc = await doctor_repo.get_by_user_id_with_details(db, current_user.id)
                if not doc or appointment.doctor_id != doc.id:
                    raise SpandanException(code="FORBIDDEN", message="Not authorized.", status_code=403)
            elif current_user.role == UserRole.ASSISTANT:
                assigned = any(
                    a.doctor_id == appointment.doctor_id and a.is_active for a in current_user.assistant_assignments
                )
                if not assigned:
                    raise SpandanException(code="FORBIDDEN", message="Not authorized.", status_code=403)

        appointment.appointment_status = request.appointment_status
        if request.cancellation_reason:
            appointment.cancellation_reason = request.cancellation_reason
        if request.appointment_status == AppointmentStatus.CANCELLED:
            appointment.cancelled_at = utcnow()
            # If schedule was full before and now someone cancelled, reopen it if not past end time
            schedule = await schedule_repo.get_by_id(db, appointment.schedule_id)
            if schedule and schedule.status == ScheduleStatus.FULL:
                schedule.status = ScheduleStatus.OPEN
        elif request.appointment_status == AppointmentStatus.IN_CONSULTATION:
            if not appointment.actual_consultation_started_at:
                appointment.actual_consultation_started_at = utcnow()
            # Auto-sync queue state current_serial
            queue = await queue_repo.get_by_schedule_id(db, appointment.schedule_id)
            if queue:
                queue.current_serial = appointment.serial_number
                queue.status_message = f"Consultation in progress for Serial #{appointment.serial_number}."
        elif request.appointment_status == AppointmentStatus.COMPLETED:
            if not appointment.actual_consultation_completed_at:
                appointment.actual_consultation_completed_at = utcnow()

        if request.actual_consultation_started_at:
            appointment.actual_consultation_started_at = request.actual_consultation_started_at
        if request.actual_consultation_completed_at:
            appointment.actual_consultation_completed_at = request.actual_consultation_completed_at

        await db.commit()
        return await appointment_repo.get_by_id_with_details(db, appointment.id)

    async def get_serial_tracking(
        self, db: AsyncSession, schedule_id: UUID, current_user: Optional[User] = None
    ) -> SerialTrackingResponse:
        schedule = await schedule_repo.get_by_id_with_queue(db, schedule_id)
        if not schedule:
            raise SpandanException(code="NOT_FOUND", message="Schedule not found.", status_code=404)

        queue = schedule.queue_state
        current_running = queue.current_serial if queue else 0
        delay_mins = queue.delay_minutes if queue else 0
        status_msg = queue.status_message if queue else "Queue not started yet."

        your_serial: Optional[int] = None
        people_ahead: Optional[int] = None
        est_waiting_mins: Optional[int] = None
        est_consult_time: Optional[datetime] = None

        if current_user and current_user.role == UserRole.PATIENT:
            pat_profile = await patient_repo.get_by_user_id(db, current_user.id)
            if pat_profile:
                apps = await appointment_repo.get_by_schedule_id(db, schedule_id, active_only=True)
                for a in apps:
                    if a.patient_id == pat_profile.id:
                        your_serial = a.serial_number
                        break

        if your_serial is not None:
            people_ahead = max(0, your_serial - current_running) if current_running > 0 else your_serial - 1
            if people_ahead < 0:
                people_ahead = 0
            est_waiting_mins = (people_ahead * schedule.average_consultation_minutes) + delay_mins
            est_consult_time = utcnow() + timedelta(minutes=est_waiting_mins)

        return SerialTrackingResponse(
            schedule_id=schedule_id,
            current_serial_running=current_running,
            delay_minutes=delay_mins,
            status_message=status_msg,
            your_serial_number=your_serial,
            people_ahead=people_ahead,
            estimated_waiting_minutes=est_waiting_mins,
            estimated_consultation_time=est_consult_time,
        )


appointment_service = AppointmentService()
