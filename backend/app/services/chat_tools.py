"""Explicit operational projections. Never serialize ORM users, charts or raw notes."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import SpandanException
from app.core.time import local_now
from app.models.appointment import Appointment
from app.models.chamber import Chamber
from app.models.doctor import AssistantAssignment, DoctorProfile, DoctorVerificationStatus
from app.models.operations import Dependent, Payment, WaitlistEntry
from app.models.schedule import Schedule, ScheduleStatus
from app.models.user import User, UserRole
from app.repositories.appointment import appointment_repo
from app.repositories.doctor import doctor_repo, specialization_repo
from app.repositories.schedule import schedule_repo
from app.services.appointment import appointment_service
from app.services.chat_contract import validate_tool
from app.services.permissions import require_doctor_access

FAQ = [
    {
        "title": "Find and book a doctor",
        "text": "Search by specialty, district, fee or available date. Choose a chamber session and review the date, fee and serial booking before confirming. A session uses serials, not exact consultation times.",
        "href": "/doctors",
    },
    {
        "title": "Appointments and rescheduling",
        "text": "View upcoming appointments on your dashboard. Rescheduling requires another session with the same doctor. Paid appointments require the same fee; pending payments must be resolved first.",
        "href": "/dashboard/patient",
    },
    {
        "title": "Payments and receipts",
        "text": "Open Payments to use secure Stripe Checkout or view a receipt. Never send card details in chat. The chamber can record received cash. Eligible refunds require a cancelled paid appointment and authorized staff.",
        "href": "/dashboard/patient/payments",
    },
    {
        "title": "Queue and arrival",
        "text": "Check your serial, people ahead and estimated delay before travelling. The queue provides estimates; the chamber controls consultation progress.",
        "href": "/dashboard/patient",
    },
    {
        "title": "Patient profile and records",
        "text": "Use your profile to maintain your information and private records. Support chat cannot read your medical history or reports. Use the existing symptom checker for specialty guidance.",
        "href": "/dashboard/patient/profile",
    },
    {
        "title": "Hospital-sourced profiles",
        "text": "Hospital-sourced details and generated sessions are not hospital-confirmed availability. Contact the hospital to arrange and confirm a visit when indicated on the doctor profile.",
        "href": "/doctors",
    },
    {
        "title": "Staff sessions and queues",
        "text": "Doctors and assigned assistants manage sessions and queues within their permissions. Closing or cancelling a session can affect existing appointments; review the affected booking count before confirming.",
        "href": "/dashboard/doctor",
    },
    {
        "title": "Account help",
        "text": "Use Forgot password on the sign-in page to recover access. Contact community.cuetinsights@gmail.com for help. Never send passwords or verification codes in chat.",
        "href": "/forgot-password",
    },
]


def uid(value):
    return UUID(str(value))


def page(rows, offset=0):
    # Callers query at most eleven rows to determine continuation without bulk disclosure.
    return {"items": rows[:10], "next_offset": offset + 10 if len(rows) > 10 else None}


def project(row, names):
    from fastapi.encoders import jsonable_encoder

    from app.core.time import aware

    values = {k: getattr(row, k) for k in names}
    for key, value in values.items():
        if isinstance(value, datetime):
            values[key] = aware(value).isoformat()
    return jsonable_encoder(values)


def doctor_card(row):
    return {
        **project(
            row, ["id", "full_name", "current_workplace", "verification_status", "source_url"]
        ),
        "specialties": [s.name for s in row.specializations],
        "href": f"/doctors/{row.id}",
        "availability_note": "Contact the hospital to confirm availability."
        if row.is_demo
        else "Use published chamber sessions; queue times are estimates.",
    }


def chamber_card(row):
    card = project(
        row,
        [
            "id",
            "doctor_id",
            "name",
            "address",
            "district",
            "area",
            "consultation_fee",
            "follow_up_fee",
        ],
    )
    for field in ("consultation_fee", "follow_up_fee"):
        card[field] = str(Decimal(str(getattr(row, field))).quantize(Decimal("0.01")))
    return card


def schedule_card(row):
    return {
        **project(
            row,
            [
                "id",
                "doctor_id",
                "chamber_id",
                "schedule_date",
                "start_time",
                "end_time",
                "maximum_patients",
                "status",
            ],
        ),
        "timezone": settings.APP_TIMEZONE,
        "chamber": chamber_card(row.chamber),
        "queue": project(row.queue_state, ["current_serial", "delay_minutes"])
        if row.queue_state
        else None,
    }


def dashboard_role(user):
    return "admin" if user.role == UserRole.ADMINISTRATOR else user.role.value


def appointment_card(row, user=None):
    return {
        **project(
            row,
            [
                "id",
                "doctor_id",
                "schedule_id",
                "chamber_id",
                "dependent_id",
                "serial_number",
                "appointment_status",
                "estimated_consultation_at",
            ],
        ),
        "attendee_name": row.attendee_name or row.patient.full_name,
        "doctor_name": row.doctor.full_name,
        "session": schedule_card(row.schedule),
        "href": "/dashboard/patient"
        if user is None or user.role == UserRole.PATIENT
        else f"/dashboard/{dashboard_role(user)}/queue?schedule_id={row.schedule_id}",
    }


def payment_card(payment, appointment, user=None):
    return {
        "id": str(payment.id) if payment else None,
        "appointment_id": str(appointment.id),
        "amount": str(
            Decimal(
                str(payment.amount if payment else appointment.chamber.consultation_fee)
            ).quantize(Decimal("0.01"))
        ),
        "currency": payment.currency if payment else settings.PAYMENT_CURRENCY,
        "status": payment.status if payment else "unpaid",
        "method": payment.provider if payment else None,
        "doctor_name": appointment.doctor.full_name,
        "serial_number": appointment.serial_number,
        "session_date": str(appointment.schedule.schedule_date),
        "href": f"/dashboard/patient/payments?appointment_id={appointment.id}"
        if user is None or user.role == UserRole.PATIENT
        else f"/dashboard/{dashboard_role(user)}/tools?tab=billing&appointment_id={appointment.id}",
    }


async def staff_doctor_ids(db, user, capability=None):
    if user.role == UserRole.ADMINISTRATOR:
        return None
    if user.role == UserRole.DOCTOR:
        return [user.doctor_profile.id]
    if user.role != UserRole.ASSISTANT:
        raise SpandanException("FORBIDDEN", "Staff access is required.", 403)
    query = select(AssistantAssignment.doctor_id).where(
        AssistantAssignment.assistant_user_id == user.id, AssistantAssignment.is_active.is_(True)
    )
    if capability:
        query = query.where(getattr(AssistantAssignment, capability).is_(True))
    else:
        query = query.where(
            or_(
                AssistantAssignment.can_manage_schedules.is_(True),
                AssistantAssignment.can_manage_appointments.is_(True),
                AssistantAssignment.can_update_queue.is_(True),
            )
        )
    return list((await db.scalars(query)).all())


async def public_doctor(db, doctor_id):
    row = await doctor_repo.get_by_id_with_details(db, doctor_id)
    owner = await db.get(User, row.user_id) if row else None
    if (
        not row
        or not owner
        or not owner.is_active
        or row.verification_status != DoctorVerificationStatus.APPROVED
        or (row.is_demo and not settings.DEMO_MODE)
    ):
        raise SpandanException("NOT_FOUND", "Public doctor not found.", 404)
    return row


async def authorized_appointment(db, user, appointment_id, capability="can_manage_appointments"):
    row = await appointment_repo.get_by_id_with_details(db, appointment_id)
    if not row:
        raise SpandanException("NOT_FOUND", "Appointment not found.", 404)
    if user.role == UserRole.PATIENT:
        if not user.patient_profile or row.patient_id != user.patient_profile.id:
            raise SpandanException(
                "FORBIDDEN", "This appointment is not available for your account.", 403
            )
    else:
        require_doctor_access(user, row.doctor_id, capability)
    return row


async def read_tool(db, user, name, args):
    validate_tool(name, args, user.role.value)
    offset = args.get("offset", 0)
    if name == "help":
        topic = args.get("topic", "").lower().split()
        matches = sorted(
            FAQ,
            key=lambda f: sum(w in (f["title"] + " " + f["text"]).lower() for w in topic),
            reverse=True,
        )
        items = [dict(item) for item in matches[:3]]
        if user.role != UserRole.PATIENT:
            base = f"/dashboard/{dashboard_role(user)}"
            for item in items:
                item["href"] = {
                    "/dashboard/patient": base,
                    "/dashboard/doctor": base,
                    "/dashboard/patient/profile": base + "/profile",
                    "/dashboard/patient/payments": base + "/tools?tab=billing",
                }.get(item["href"], item["href"])
        return {"items": items}
    if name == "search_doctors":
        args = {**args}
        args.pop("offset", None)
        if args.get("specialization_id"):
            args["specialization_id"] = uid(args["specialization_id"])
        if args.get("available_on"):
            args["available_on"] = date.fromisoformat(args["available_on"])
        return page(
            [
                doctor_card(x)
                for x in await doctor_repo.search_doctors(db, skip=offset, limit=11, **args)
            ],
            offset,
        )
    if name == "list_specialties":
        rows = await specialization_repo.get_active_all(db)
        return page([project(x, ["id", "name"]) for x in rows[offset : offset + 11]], offset)
    if name == "doctor_details":
        return doctor_card(await public_doctor(db, uid(args["doctor_id"])))
    if name in {"list_chambers", "list_sessions"}:
        doctor_id = uid(args["doctor_id"]) if args.get("doctor_id") else None
        if user.role == UserRole.PATIENT:
            if not doctor_id:
                raise SpandanException("VALIDATION_ERROR", "Choose a doctor first.", 422)
            await public_doctor(db, doctor_id)
            ids = [doctor_id]
        elif doctor_id:
            # Staff may also browse public doctors, but private operational data stays scoped.
            allowed = await staff_doctor_ids(db, user)
            if allowed is not None and doctor_id not in allowed:
                raise SpandanException("FORBIDDEN", "This doctor is outside your assignments.", 403)
            ids = [doctor_id]
        else:
            ids = await staff_doctor_ids(db, user)
        if name == "list_chambers":
            stmt = select(Chamber).where(Chamber.is_active.is_(True))
            if ids is not None:
                stmt = stmt.where(Chamber.doctor_id.in_(ids))
            rows = await db.scalars(
                stmt.order_by(Chamber.name, Chamber.id).offset(offset).limit(11)
            )
            return page([chamber_card(x) for x in rows], offset)
        stmt = select(Schedule).options(
            selectinload(Schedule.queue_state), selectinload(Schedule.chamber)
        )
        stmt = stmt.where(
            Schedule.schedule_date >= date.fromisoformat(args["from_date"])
            if args.get("from_date")
            else Schedule.schedule_date >= local_now().date()
        )
        if args.get("on_date"):
            stmt = stmt.where(Schedule.schedule_date == date.fromisoformat(args["on_date"]))
        if ids is not None:
            stmt = stmt.where(Schedule.doctor_id.in_(ids))
        if user.role == UserRole.PATIENT:
            stmt = stmt.where(
                Schedule.status.in_([ScheduleStatus.OPEN, ScheduleStatus.FULL]),
                Schedule.chamber.has(Chamber.is_active.is_(True)),
            )
        rows = await db.scalars(
            stmt.order_by(Schedule.schedule_date, Schedule.start_time, Schedule.id)
            .offset(offset)
            .limit(11)
        )
        return page([schedule_card(x) for x in rows], offset)
    if name in {"list_appointments", "list_payments"}:
        stmt = select(Appointment.id)
        if user.role == UserRole.PATIENT:
            stmt = stmt.where(Appointment.patient_id == user.patient_profile.id)
        else:
            ids = await staff_doctor_ids(db, user, "can_manage_appointments")
            if ids is not None:
                stmt = stmt.where(Appointment.doctor_id.in_(ids))
        if args.get("schedule_id"):
            if user.role != UserRole.PATIENT:
                schedule = await schedule_repo.get_by_id_with_queue(db, uid(args["schedule_id"]))
                if not schedule:
                    raise SpandanException("NOT_FOUND", "Session not found.", 404)
                require_doctor_access(user, schedule.doctor_id, "can_manage_appointments")
            stmt = stmt.where(Appointment.schedule_id == uid(args["schedule_id"]))
        ids = list(
            await db.scalars(
                stmt.order_by(Appointment.created_at.desc(), Appointment.id)
                .offset(offset)
                .limit(11)
            )
        )
        items = []
        for ident in ids:
            row = await authorized_appointment(db, user, ident)
            if name == "list_appointments":
                items.append(appointment_card(row, user))
            else:
                p = await db.scalar(select(Payment).where(Payment.appointment_id == ident))
                items.append(payment_card(p, row, user))
        return page(items, offset)
    if name in {"appointment_details", "payment_details", "receipt"}:
        p = None
        if name == "receipt":
            p = await db.get(Payment, uid(args["payment_id"]))
            if not p:
                raise SpandanException("NOT_FOUND", "Receipt not found.", 404)
            ident = p.appointment_id
        else:
            ident = uid(args["appointment_id"])
        row = await authorized_appointment(db, user, ident)
        p = p or await db.scalar(select(Payment).where(Payment.appointment_id == ident))
        if name == "receipt" and p.status not in {"paid", "refunded", "refund_pending"}:
            raise SpandanException("CONFLICT", "No receipt is available until payment.", 409)
        if name == "appointment_details":
            return {**appointment_card(row, user), "payment": payment_card(p, row, user)}
        return payment_card(p, row, user)
    if name == "queue_status":
        sid = uid(args["schedule_id"])
        if user.role == UserRole.PATIENT:
            if not args.get("appointment_id"):
                raise SpandanException(
                    "VALIDATION_ERROR", "Choose your appointment to track its queue.", 422
                )
            appointment = await authorized_appointment(db, user, uid(args["appointment_id"]))
            if appointment.schedule_id != sid:
                raise SpandanException(
                    "FORBIDDEN", "The session does not match your appointment.", 403
                )
        else:
            schedule = await schedule_repo.get_by_id_with_queue(db, sid)
            if not schedule:
                raise SpandanException("NOT_FOUND", "Session not found.", 404)
            require_doctor_access(user, schedule.doctor_id, "can_update_queue")
        result = await appointment_service.get_serial_tracking(
            db, sid, user, uid(args["appointment_id"]) if args.get("appointment_id") else None
        )
        # status_message is staff-authored free text and is not needed for numeric queue tracking.
        return result.model_dump(mode="json", exclude={"status_message"})
    if name in {"list_dependents", "list_waitlist"}:
        cls = Dependent if name == "list_dependents" else WaitlistEntry
        stmt = select(cls).where(cls.patient_id == user.patient_profile.id)
        stmt = (
            stmt.where(cls.is_active.is_(True))
            if cls == Dependent
            else stmt.where(cls.status == "waiting")
        )
        rows = await db.scalars(stmt.order_by(cls.created_at, cls.id).offset(offset).limit(11))
        fields = (
            ["id", "full_name", "relationship_name"]
            if cls == Dependent
            else ["id", "schedule_id", "status"]
        )
        return page([project(x, fields) for x in rows], offset)
    if name == "list_assistant_assignments":
        stmt = select(AssistantAssignment).options(selectinload(AssistantAssignment.assistant))
        if user.role == UserRole.DOCTOR:
            stmt = stmt.where(AssistantAssignment.doctor_id == user.doctor_profile.id)
        rows = await db.scalars(stmt.order_by(AssistantAssignment.id).offset(offset).limit(11))
        return page(
            [
                {
                    **project(
                        x,
                        [
                            "id",
                            "doctor_id",
                            "is_active",
                            "can_manage_schedules",
                            "can_manage_appointments",
                            "can_update_queue",
                        ],
                    ),
                    "email": x.assistant.email,
                }
                for x in rows
            ],
            offset,
        )
    if name in {"admin_users", "admin_doctors"}:
        cls = User if name == "admin_users" else DoctorProfile
        stmt = select(cls)
        if cls == DoctorProfile:
            stmt = stmt.options(selectinload(DoctorProfile.specializations))
        if args.get("query"):
            field = User.email if cls == User else DoctorProfile.full_name
            stmt = stmt.where(field.ilike("%" + args["query"] + "%"))
        if cls == User and "is_active" in args:
            stmt = stmt.where(User.is_active == args["is_active"])
        if cls == DoctorProfile and args.get("status"):
            stmt = stmt.where(
                DoctorProfile.verification_status == DoctorVerificationStatus(args["status"])
            )
        rows = await db.scalars(
            stmt.order_by(cls.created_at.desc(), cls.id).offset(offset).limit(11)
        )
        return page(
            [
                project(x, ["id", "email", "role", "is_active"]) if cls == User else doctor_card(x)
                for x in rows
            ],
            offset,
        )
    if name == "admin_summary":
        return {
            "users": await db.scalar(select(func.count(User.id))),
            "pending_doctors": await db.scalar(
                select(func.count(DoctorProfile.id)).where(
                    DoctorProfile.verification_status == DoctorVerificationStatus.PENDING
                )
            ),
            "today_sessions": await db.scalar(
                select(func.count(Schedule.id)).where(Schedule.schedule_date == local_now().date())
            ),
        }
    raise SpandanException("NOT_FOUND", "Unknown support tool.", 404)
