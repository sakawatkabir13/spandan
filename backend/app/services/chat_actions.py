"""Prepare, confirm and execute exact operations. The model cannot confirm an action."""

import hashlib
import secrets
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions import SpandanException
from app.core.security import verify_password
from app.core.time import aware
from app.db.base import utcnow
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit import AuditLog
from app.models.chamber import Chamber
from app.models.chat import ChatAction
from app.models.doctor import AssistantAssignment, DoctorProfile
from app.models.operations import Dependent, Payment, WaitlistEntry
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.repositories.schedule import schedule_repo
from app.schemas.appointment import AppointmentCreate, AppointmentStatusUpdate
from app.schemas.doctor import DoctorVerificationRequest
from app.schemas.schedule import QueueStateUpdate, ScheduleCreate, ScheduleUpdate
from app.services import appointment_operations, billing
from app.services.account_security import validate_mfa
from app.services.appointment import appointment_service
from app.services.chat_contract import CATALOG, validate_tool
from app.services.chat_security import (
    conversation_for_user,
    digest,
    execution_conversation,
    fingerprint,
    seal,
    unseal,
)
from app.services.chat_tools import (
    authorized_appointment,
    chamber_card,
    payment_card,
    project,
    schedule_card,
    uid,
)
from app.services.doctor import doctor_service
from app.services.permissions import require_doctor_access
from app.services.schedule import schedule_service


async def snapshot(db, user, name, args, *, lock=False):
    """Only operational state is compared. No clinical data enters proposals or tools."""
    validate_tool(name, args, user.role.value)
    state = {"action": name, "arguments": args}
    schedules = set()
    appointment = None
    payment = None
    if args.get("appointment_id"):
        capability = (
            "can_update_queue"
            if name == "propose_appointment_status"
            and args["status"] not in {"cancelled", "confirmed"}
            else "can_manage_appointments"
        )
        appointment = await authorized_appointment(
            db, user, uid(args["appointment_id"]), capability
        )
    if args.get("payment_id"):
        payment = await db.get(Payment, uid(args["payment_id"]))
        if not payment:
            raise SpandanException("NOT_FOUND", "Payment not found.", 404)
        appointment = await authorized_appointment(db, user, payment.appointment_id)
    if appointment:
        schedules.add(appointment.schedule_id)
        await db.refresh(appointment, ["appointment_status", "updated_at", "dependent_id"])
        state["appointment"] = project(
            appointment,
            [
                "id",
                "patient_id",
                "dependent_id",
                "appointment_status",
                "updated_at",
                "serial_number",
            ],
        )
        state["attendee_name"] = appointment.attendee_name or appointment.patient.full_name
        state["doctor_name"] = appointment.doctor.full_name
        payment = payment or await db.scalar(
            select(Payment).where(Payment.appointment_id == appointment.id)
        )
        state["payment"] = payment_card(payment, appointment)
    if args.get("schedule_id"):
        schedules.add(uid(args["schedule_id"]))
    if (
        name == "propose_appointment_status"
        and user.role == UserRole.PATIENT
        and args["status"] not in {"confirmed", "cancelled"}
    ):
        raise SpandanException(
            "FORBIDDEN", "Patients can only confirm or cancel their own visits.", 403
        )
    if name == "propose_refund" and (
        not payment
        or payment.status != "paid"
        or appointment.appointment_status != AppointmentStatus.CANCELLED
    ):
        raise SpandanException(
            "CONFLICT", "Cancel a paid appointment before requesting a refund.", 409
        )
    if name == "propose_cash_payment" and payment:
        raise SpandanException("CONFLICT", "A payment already exists for this appointment.", 409)
    if name == "propose_checkout" and appointment.appointment_status in {
        AppointmentStatus.CANCELLED,
        AppointmentStatus.ABSENT,
    }:
        raise SpandanException("CONFLICT", "This appointment cannot be paid.", 409)
    if args.get("dependent_id"):
        dep = await db.get(Dependent, uid(args["dependent_id"]))
        if not dep or not dep.is_active or dep.patient_id != user.patient_profile.id:
            raise SpandanException(
                "FORBIDDEN", "Choose an active dependent from your own account.", 403
            )
        state["dependent"] = project(dep, ["id", "full_name", "is_active"])
    if name == "propose_book_appointment" and not args.get("dependent_id"):
        state["attendee_name"] = user.patient_profile.full_name
    if name == "propose_leave_waitlist":
        entry = await db.get(WaitlistEntry, uid(args["entry_id"]))
        if not entry or entry.patient_id != user.patient_profile.id:
            raise SpandanException("NOT_FOUND", "Waitlist entry not found.", 404)
        state["waitlist"] = project(entry, ["id", "schedule_id", "status"])
        schedules.add(entry.schedule_id)
    if args.get("chamber_id"):
        chamber = await db.get(Chamber, uid(args["chamber_id"]))
        if not chamber or not chamber.is_active:
            raise SpandanException("NOT_FOUND", "Active chamber not found.", 404)
        require_doctor_access(user, chamber.doctor_id, "can_manage_schedules")
        if lock:
            await db.execute(
                select(DoctorProfile.id)
                .where(DoctorProfile.id == chamber.doctor_id)
                .with_for_update()
            )
            await db.refresh(chamber, with_for_update=True)
        state["chamber"] = chamber_card(chamber)
        if name == "propose_create_session":
            ScheduleCreate.model_validate(args)
            state["existing_sessions"] = [
                str(x)
                for x in await db.scalars(
                    select(Schedule.id)
                    .where(
                        Schedule.doctor_id == chamber.doctor_id,
                        Schedule.schedule_date == ScheduleCreate.model_validate(args).schedule_date,
                    )
                    .order_by(Schedule.id)
                )
            ]
    session_rows = []
    if lock and schedules:
        # Match the website's doctor -> schedule -> payment lock order.
        doctor_ids = list(
            await db.scalars(
                select(Schedule.doctor_id).where(Schedule.id.in_(schedules)).distinct()
            )
        )
        for doctor_id in sorted(doctor_ids, key=str):
            await db.execute(
                select(DoctorProfile.id).where(DoctorProfile.id == doctor_id).with_for_update()
            )
    for ident in sorted(schedules, key=str):
        row = await schedule_repo.get_by_id_with_queue(db, ident, lock=lock)
        if not row:
            raise SpandanException("NOT_FOUND", "Session not found.", 404)
        if name in {"propose_create_session", "propose_update_session"}:
            require_doctor_access(user, row.doctor_id, "can_manage_schedules")
        elif name in {"propose_advance_queue", "propose_queue_delay"}:
            require_doctor_access(user, row.doctor_id, "can_update_queue")
        elif (
            name == "propose_appointment_status"
            and args["status"] not in {"cancelled", "confirmed"}
            and user.role != UserRole.PATIENT
        ):
            require_doctor_access(user, row.doctor_id, "can_update_queue")
        elif user.role != UserRole.PATIENT:
            require_doctor_access(user, row.doctor_id, "can_manage_appointments")
        if lock:
            await db.refresh(row.chamber, with_for_update=True)
        item = schedule_card(row)
        doctor = await db.get(DoctorProfile, row.doctor_id)
        item["doctor_name"] = doctor.full_name
        item["active_bookings"] = await db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.schedule_id == ident,
                Appointment.appointment_status.notin_(
                    [
                        AppointmentStatus.CANCELLED,
                        AppointmentStatus.COMPLETED,
                        AppointmentStatus.ABSENT,
                    ]
                ),
            )
        )
        if name == "propose_advance_queue":
            item["roster"] = [
                project(a, ["id", "serial_number", "appointment_status"])
                for a in await appointment_repo_rows(db, ident)
            ]
        session_rows.append(item)
    if session_rows:
        state["sessions"] = session_rows
    if payment and lock:
        await db.refresh(payment, with_for_update=True)
        state["payment"] = payment_card(payment, appointment)
    if name == "propose_assistant_permissions":
        stmt = select(AssistantAssignment).where(
            AssistantAssignment.id == uid(args["assignment_id"])
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        assignment = await db.scalar(stmt)
        if not assignment:
            raise SpandanException("NOT_FOUND", "Assistant assignment not found.", 404)
        require_doctor_access(user, assignment.doctor_id, "can_manage_appointments")
        state["assignment"] = project(
            assignment,
            [
                "id",
                "doctor_id",
                "assistant_user_id",
                "is_active",
                "can_manage_schedules",
                "can_manage_appointments",
                "can_update_queue",
            ],
        )
        assistant = await db.get(User, assignment.assistant_user_id)
        state["assistant_email"] = assistant.email
    if name == "propose_user_status":
        stmt = select(User).where(User.id == uid(args["user_id"]))
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        target = await db.scalar(stmt)
        if not target:
            raise SpandanException("NOT_FOUND", "Account not found.", 404)
        if target.role == UserRole.ADMINISTRATOR and not args["is_active"]:
            raise SpandanException(
                "FORBIDDEN", "Administrator accounts cannot be deactivated here.", 403
            )
        state["user"] = project(target, ["id", "email", "role", "is_active"])
    if name == "propose_doctor_verification":
        stmt = select(DoctorProfile).where(DoctorProfile.id == uid(args["doctor_id"]))
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        doctor = await db.scalar(stmt)
        if not doctor:
            raise SpandanException("NOT_FOUND", "Doctor not found.", 404)
        state["doctor"] = project(doctor, ["id", "full_name", "verification_status"])
    return state


async def appointment_repo_rows(db, schedule_id):
    return list(
        await db.scalars(
            select(Appointment)
            .where(Appointment.schedule_id == schedule_id)
            .order_by(Appointment.serial_number)
        )
    )


def action_view(action):
    result = {
        "id": str(action.id),
        "name": action.name,
        "status": action.status,
        "requires_step_up": CATALOG[action.name]["sensitive"],
        "expires_at": action.expires_at.isoformat(),
        "summary": {
            "requested_changes": unseal(action.arguments_ciphertext),
            **unseal(action.summary_ciphertext),
        },
        "error_code": action.error_code,
    }
    if action.result_ciphertext:
        result["result"] = unseal(action.result_ciphertext)
    return result


async def prepare_action(db, user, conversation, name, args):
    if not name.startswith("propose_"):
        raise SpandanException("FORBIDDEN", "Only an action proposal may be prepared.", 403)
    current = await snapshot(db, user, name, args)
    action = ChatAction(
        id=uuid4(),
        actor_user_id=user.id,
        conversation_id=conversation.id,
        name=name,
        arguments_ciphertext=seal(args),
        summary_ciphertext=seal(current),
        state_hash=digest(current),
        access_fingerprint=await fingerprint(db, user),
        expires_at=utcnow() + timedelta(minutes=5),
    )
    db.add(action)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="chat.action_prepared",
            entity_type="chat_action",
            entity_id=str(action.id),
            metadata_json={"tool": name},
        )
    )
    await db.commit()
    return {"proposal": action_view(action)}


async def owned_action(db, user, action_id, *, lock=False):
    stmt = select(ChatAction).where(ChatAction.id == action_id, ChatAction.actor_user_id == user.id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    action = await db.scalar(stmt)
    if not action:
        raise SpandanException("NOT_FOUND", "Action not found.", 404)
    if action.access_fingerprint != await fingerprint(db, user):
        raise SpandanException(
            "CHAT_ACCESS_CHANGED", "Your access changed. Prepare a new action.", 403
        )
    return action


async def step_up(db, user, action_id, password, code):
    action = await owned_action(db, user, action_id, lock=True)
    await conversation_for_user(db, user, action.conversation_id)
    if action.status != "pending" or aware(action.expires_at) <= utcnow():
        raise SpandanException("ACTION_EXPIRED", "Prepare a new action before verifying.", 409)
    # Failed attempts are recorded and limited independently from model usage.
    failures = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.actor_user_id == user.id,
            AuditLog.action == "chat.step_up_failed",
            AuditLog.created_at >= utcnow() - timedelta(minutes=15),
        )
    )
    if failures >= 5:
        raise SpandanException("RATE_LIMITED", "Wait fifteen minutes before verifying again.", 429)
    target = await db.scalar(
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.patient_profile),
            selectinload(User.doctor_profile),
            selectinload(User.assistant_assignments),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    try:
        if not verify_password(password, target.password_hash):
            raise SpandanException(
                "INVALID_CREDENTIALS", "Verification failed. Check your password.", 401
            )
        validate_mfa(target, code)
    except SpandanException:
        db.add(
            AuditLog(
                actor_user_id=user.id,
                action="chat.step_up_failed",
                entity_type="chat_action",
                entity_id=str(action.id),
            )
        )
        await db.commit()
        raise
    token = secrets.token_urlsafe(32)
    action.step_up_hash = hashlib.sha256(token.encode()).hexdigest()
    action.step_up_expires_at = utcnow() + timedelta(minutes=5)
    await db.commit()
    return token


async def confirm_action(db, user, action_id, step_up_token=None):
    action = await owned_action(db, user, action_id, lock=True)
    if action.status in {"succeeded", "confirmed"}:
        await execution_conversation(db, user, action)
        return action
    await conversation_for_user(db, user, action.conversation_id)
    if action.status != "pending" or aware(action.expires_at) <= utcnow():
        raise SpandanException(
            "ACTION_EXPIRED", "This action expired. Ask the assistant to prepare it again.", 409
        )
    if CATALOG[action.name]["sensitive"]:
        if (
            not action.step_up_hash
            or not action.step_up_expires_at
            or aware(action.step_up_expires_at) <= utcnow()
            or not step_up_token
            or not secrets.compare_digest(
                action.step_up_hash, hashlib.sha256(step_up_token.encode()).hexdigest()
            )
        ):
            raise SpandanException(
                "STEP_UP_REQUIRED", "Verify your password and authenticator before confirming.", 403
            )
    current = await snapshot(db, user, action.name, unseal(action.arguments_ciphertext), lock=True)
    if digest(current) != action.state_hash:
        action.status = "needs_reconfirmation"
        await db.commit()
        raise SpandanException(
            "ACTION_CHANGED",
            "The appointment, fee, availability or account state changed. Prepare a new action.",
            409,
        )
    action.status = "confirmed"
    action.confirmed_at = utcnow()
    action.step_up_hash = None
    action.step_up_expires_at = None
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="chat.action_confirmed",
            entity_type="chat_action",
            entity_id=str(action.id),
        )
    )
    await db.commit()
    return action


async def execute_action(db, user, action_id):
    action = await owned_action(db, user, action_id, lock=True)
    if action.status == "succeeded":
        return {"action": action_view(action)}
    await execution_conversation(db, user, action)
    if action.status != "confirmed":
        raise SpandanException(
            "CONFIRMATION_REQUIRED",
            "Confirm this exact action using its button before execution.",
            403,
        )
    name = action.name
    args = unseal(action.arguments_ciphertext)
    try:
        current = await snapshot(db, user, name, args, lock=True)
        if digest(current) != action.state_hash:
            action.status = "needs_reconfirmation"
            await db.commit()
            raise SpandanException("ACTION_CHANGED", "Details changed. Prepare a new action.", 409)
        result = await mutate(db, user, name, args, action.id)
        action.status = "succeeded"
        action.completed_at = utcnow()
        action.result_ciphertext = seal(result)
        db.add(
            AuditLog(
                actor_user_id=user.id,
                action="chat.action_executed",
                entity_type="chat_action",
                entity_id=str(action.id),
                metadata_json={"tool": name},
            )
        )
        await db.commit()
        return {"action": action_view(action)}
    except Exception:
        await db.rollback()
        # An uncertain provider response remains confirmed and is retryable using the
        # same operation and provider idempotency keys, never a freshly invented payment.
        raise


async def mutate(db, user, name, args, action_id):
    def ident(key):
        return uid(args[key])

    result = {"message": "The confirmed change was completed."}
    if name == "propose_book_appointment":
        row = await appointment_service.book_appointment(
            db,
            user,
            AppointmentCreate(
                schedule_id=ident("schedule_id"),
                dependent_id=ident("dependent_id") if args.get("dependent_id") else None,
            ),
            commit=False,
        )
        result.update(
            appointment_id=str(row.id), serial_number=row.serial_number, href="/dashboard/patient"
        )
    elif name == "propose_appointment_status":
        row = await appointment_service.update_status(
            db,
            user,
            ident("appointment_id"),
            AppointmentStatusUpdate(appointment_status=args["status"]),
            commit=False,
        )
        result.update(appointment_id=str(row.id), status=row.appointment_status.value)
    elif name == "propose_reschedule":
        outcome = await appointment_operations.reschedule(
            ident("appointment_id"),
            appointment_operations.RescheduleBody(schedule_id=ident("schedule_id")),
            user,
            db,
            commit=False,
        )
        result.update(
            appointment_id=str(outcome["data"].id),
            serial_number=outcome["data"].serial_number,
            href="/dashboard/patient",
        )
    elif name == "propose_join_waitlist":
        outcome = await appointment_operations.join_waitlist(
            ident("schedule_id"), user, db, commit=False
        )
        result["message"] = outcome["message"]
    elif name == "propose_leave_waitlist":
        await appointment_operations.leave_waitlist(ident("entry_id"), user, db, commit=False)
    elif name == "propose_checkout":
        outcome = await billing.checkout(
            ident("appointment_id"),
            user,
            db,
            commit=False,
            payment_id=uuid5(NAMESPACE_URL, "spandan-chat-payment:" + str(action_id)),
        )
        result.update(message=outcome["message"], checkout_url=outcome["data"]["url"])
    elif name == "propose_cancel_checkout":
        outcome = await billing.cancel_checkout(ident("payment_id"), user, db, commit=False)
        result["message"] = outcome["message"]
    elif name == "propose_cash_payment":
        outcome = await billing.record_cash(
            ident("appointment_id"), billing.CashBody(), user, db, commit=False
        )
        result["message"] = outcome["message"]
    elif name == "propose_refund":
        outcome = await billing.refund(ident("payment_id"), user, db, commit=False)
        result["message"] = outcome["message"]
    elif name == "propose_create_session":
        row = await schedule_service.create_schedule(
            db, user, ScheduleCreate.model_validate(args), commit=False
        )
        result.update(schedule_id=str(row.id))
    elif name == "propose_update_session":
        await schedule_service.update_schedule(
            db,
            user,
            ident("schedule_id"),
            ScheduleUpdate.model_validate(args["changes"]),
            commit=False,
        )
    elif name == "propose_advance_queue":
        row = await schedule_service.increment_queue(db, user, ident("schedule_id"), commit=False)
        result.update(current_serial=row.current_serial, delay_minutes=row.delay_minutes)
    elif name == "propose_queue_delay":
        row = await schedule_service.update_queue_state(
            db,
            user,
            ident("schedule_id"),
            QueueStateUpdate(delay_minutes=args["delay_minutes"]),
            commit=False,
        )
        result.update(current_serial=row.current_serial, delay_minutes=row.delay_minutes)
    elif name == "propose_assistant_permissions":
        await appointment_operations.update_assistant_permissions(
            db,
            user,
            ident("assignment_id"),
            {k: v for k, v in args.items() if k != "assignment_id"},
            commit=False,
        )
    elif name == "propose_user_status":
        await appointment_operations.update_user_status(
            db, user, ident("user_id"), args["is_active"], commit=False
        )
    elif name == "propose_doctor_verification":
        await doctor_service.verify_doctor(
            db,
            user,
            ident("doctor_id"),
            DoctorVerificationRequest(status=args["status"]),
            commit=False,
        )
    else:
        raise SpandanException("FORBIDDEN", "This action is not supported.", 403)
    return result
