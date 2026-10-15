"""Closed tool catalog. Exported verbatim to the independent MCP repository."""

CONTRACT_VERSION = "spandan-tools-v1"
PROTOCOL_VERSION = "2026-07-28"
ALL = ["patient", "doctor", "assistant", "administrator"]
STAFF = ["doctor", "assistant", "administrator"]
MANAGERS = ["doctor", "administrator"]


def string(**extra):
    return {"type": "string", "maxLength": 200, **extra}


def identifier():
    return string(format="uuid")


def schema(properties=None, required=None):
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


PAGE = {"offset": {"type": "integer", "minimum": 0, "maximum": 10000}}
TOOL_CATALOG = []


def tool(name, description, roles, properties=None, required=None, sensitive=False):
    TOOL_CATALOG.append(
        dict(
            name=name,
            description=description,
            roles=roles,
            inputSchema=schema(properties, required),
            sensitive=sensitive,
        )
    )


tool("help", "Find English help about using Spandan. No clinical advice.", ALL, {"topic": string()})
tool(
    "search_doctors",
    "Search approved public doctors. Use exact returned IDs in later tools.",
    ALL,
    {
        **PAGE,
        "query": string(),
        "district": string(),
        "specialization_id": identifier(),
        "max_fee": {"type": "number", "minimum": 0},
        "available_on": string(format="date"),
    },
)
tool("list_specialties", "List active specialties and their identifiers.", ALL, PAGE)
tool(
    "doctor_details",
    "Get a public doctor profile; hospital-sourced information is not confirmed availability.",
    ALL,
    {"doctor_id": identifier()},
    ["doctor_id"],
)
tool(
    "list_chambers",
    "List a doctor's active chambers and fees. Staff may omit doctor_id for own assigned chambers.",
    ALL,
    {**PAGE, "doctor_id": identifier()},
)
tool(
    "list_sessions",
    "List upcoming sessions. Patients must specify doctor_id. Staff can list assigned sessions.",
    ALL,
    {
        **PAGE,
        "doctor_id": identifier(),
        "from_date": string(format="date"),
        "on_date": string(format="date"),
    },
)
tool(
    "list_appointments",
    "List own appointments or a staff member's authorized roster. No clinical notes.",
    ALL,
    {**PAGE, "schedule_id": identifier()},
)
tool(
    "appointment_details",
    "Get one authorized appointment with session, queue and payment information.",
    ALL,
    {"appointment_id": identifier()},
    ["appointment_id"],
)
tool(
    "queue_status",
    "Get queue position for a patient's own appointment, or an authorized staff session.",
    ALL,
    {"schedule_id": identifier(), "appointment_id": identifier()},
    ["schedule_id"],
)
tool("list_payments", "List authorized appointment payment summaries.", ALL, PAGE)
tool(
    "payment_details",
    "Get payment status and fee for one authorized appointment.",
    ALL,
    {"appointment_id": identifier()},
    ["appointment_id"],
)
tool(
    "receipt",
    "Get a paid or refunded appointment's receipt.",
    ALL,
    {"payment_id": identifier()},
    ["payment_id"],
)
tool(
    "list_dependents",
    "List existing dependents belonging to this patient, without medical or birth-date fields.",
    ["patient"],
    PAGE,
)
tool("list_waitlist", "List this patient's current waitlist entries.", ["patient"], PAGE)
tool(
    "list_assistant_assignments",
    "List assistant permissions owned by the doctor or visible to an administrator.",
    MANAGERS,
    PAGE,
)
tool(
    "admin_users",
    "Search account status for administration. No medical profiles or security secrets.",
    ["administrator"],
    {**PAGE, "query": string(), "is_active": {"type": "boolean"}},
)
tool(
    "admin_doctors",
    "Search doctor moderation status.",
    ["administrator"],
    {
        **PAGE,
        "query": string(),
        "status": string(enum=["pending", "approved", "rejected", "suspended"]),
    },
)
tool(
    "admin_summary",
    "Get aggregate operational counts. No transcripts or patient charts.",
    ["administrator"],
)

tool(
    "propose_book_appointment",
    "Prepare a booking for this patient or an existing dependent. Does not reserve a place or execute a booking.",
    ["patient"],
    {"schedule_id": identifier(), "dependent_id": identifier()},
    ["schedule_id"],
)
tool(
    "propose_appointment_status",
    "Prepare a status change. Patients can confirm or cancel their own appointment only.",
    ALL,
    {
        "appointment_id": identifier(),
        "status": string(
            enum=[
                "confirmed",
                "cancelled",
                "checked_in",
                "waiting",
                "in_consultation",
                "completed",
                "skipped",
                "absent",
            ]
        ),
    },
    ["appointment_id", "status"],
)
tool(
    "propose_reschedule",
    "Prepare moving an appointment to another session with the same doctor.",
    ALL,
    {"appointment_id": identifier(), "schedule_id": identifier()},
    ["appointment_id", "schedule_id"],
)
tool(
    "propose_join_waitlist",
    "Prepare joining a session's cancellation waitlist.",
    ["patient"],
    {"schedule_id": identifier()},
    ["schedule_id"],
)
tool(
    "propose_leave_waitlist",
    "Prepare leaving an existing waitlist entry.",
    ["patient"],
    {"entry_id": identifier()},
    ["entry_id"],
)
tool(
    "propose_checkout",
    "Prepare opening secure Stripe Checkout for the patient's own appointment. Never collect card details.",
    ["patient"],
    {"appointment_id": identifier()},
    ["appointment_id"],
)
tool(
    "propose_cancel_checkout",
    "Prepare cancelling a pending Stripe checkout.",
    ALL,
    {"payment_id": identifier()},
    ["payment_id"],
)
tool(
    "propose_create_session",
    "Prepare a single session at an existing authorized chamber. Times are Asia/Dhaka local time.",
    STAFF,
    {
        "chamber_id": identifier(),
        "schedule_date": string(format="date"),
        "start_time": string(pattern=r"^\d{2}:\d{2}(:\d{2})?$"),
        "end_time": string(pattern=r"^\d{2}:\d{2}(:\d{2})?$"),
        "maximum_patients": {"type": "integer", "minimum": 1, "maximum": 1000},
        "average_consultation_minutes": {"type": "integer", "minimum": 1, "maximum": 240},
    },
    ["chamber_id", "schedule_date", "start_time", "end_time", "maximum_patients"],
)
tool(
    "propose_update_session",
    "Prepare a session change, showing affected bookings. Cancelled or completed sessions cannot be reopened.",
    STAFF,
    {
        "schedule_id": identifier(),
        "changes": schema(
            {
                "start_time": string(),
                "end_time": string(),
                "maximum_patients": {"type": "integer", "minimum": 1, "maximum": 1000},
                "average_consultation_minutes": {"type": "integer", "minimum": 1, "maximum": 240},
                "status": string(
                    enum=["draft", "open", "full", "closed", "completed", "cancelled"]
                ),
            }
        ),
    },
    ["schedule_id", "changes"],
)
tool(
    "propose_advance_queue",
    "Prepare calling the next waiting patient and completing any current consultation.",
    STAFF,
    {"schedule_id": identifier()},
    ["schedule_id"],
)
tool(
    "propose_queue_delay",
    "Prepare changing a session's delay estimate in minutes.",
    STAFF,
    {
        "schedule_id": identifier(),
        "delay_minutes": {"type": "integer", "minimum": 0, "maximum": 1440},
    },
    ["schedule_id", "delay_minutes"],
)
tool(
    "propose_cash_payment",
    "Prepare recording cash already received at the chamber. Requires fresh authentication.",
    STAFF,
    {"appointment_id": identifier()},
    ["appointment_id"],
    sensitive=True,
)
tool(
    "propose_refund",
    "Prepare a full refund of a paid, cancelled appointment. Cash recording does not physically return money. Requires fresh authentication.",
    MANAGERS,
    {"payment_id": identifier()},
    ["payment_id"],
    sensitive=True,
)
tool(
    "propose_assistant_permissions",
    "Prepare changes to an existing owned assignment. Assistants cannot change permissions. Requires fresh authentication.",
    MANAGERS,
    {
        "assignment_id": identifier(),
        **{
            k: {"type": "boolean"}
            for k in [
                "is_active",
                "can_manage_schedules",
                "can_manage_appointments",
                "can_update_queue",
            ]
        },
    },
    [
        "assignment_id",
        "is_active",
        "can_manage_schedules",
        "can_manage_appointments",
        "can_update_queue",
    ],
    sensitive=True,
)
tool(
    "propose_user_status",
    "Prepare account activation/deactivation. Administrator accounts cannot be deactivated. Requires fresh authentication.",
    ["administrator"],
    {"user_id": identifier(), "is_active": {"type": "boolean"}},
    ["user_id", "is_active"],
    sensitive=True,
)
tool(
    "propose_doctor_verification",
    "Prepare doctor approval, rejection or suspension. Requires fresh authentication.",
    ["administrator"],
    {"doctor_id": identifier(), "status": string(enum=["approved", "rejected", "suspended"])},
    ["doctor_id", "status"],
    sensitive=True,
)
tool(
    "execute_confirmed_action",
    "Internal execution handler. Requires an exact-action delegated grant issued after the confirmation button. Never expose to the model.",
    ALL,
    {"action_id": identifier()},
    ["action_id"],
)

CATALOG = {t["name"]: t for t in TOOL_CATALOG}


def tools_for_role(role, *, execution=False):
    return [
        t
        for t in TOOL_CATALOG
        if role in t["roles"] and (execution or t["name"] != "execute_confirmed_action")
    ]


def validate_tool(name, arguments, role, *, execution=False):
    from jsonschema import Draft202012Validator, FormatChecker

    from app.core.exceptions import SpandanException

    item = CATALOG.get(name)
    if (
        not item
        or role not in item["roles"]
        or (name == "execute_confirmed_action" and not execution)
    ):
        raise SpandanException("FORBIDDEN", "This tool is not available for your account.", 403)
    errors = list(
        Draft202012Validator(item["inputSchema"], format_checker=FormatChecker()).iter_errors(
            arguments
        )
    )
    if errors:
        paths = sorted(
            {
                (
                    "/" + "/".join(str(part) for part in error.absolute_path)
                    if error.absolute_path
                    else "input"
                )
                + " ("
                + error.validator
                + ")"
                for error in errors
            }
        )
        raise SpandanException(
            "VALIDATION_ERROR",
            "Invalid tool fields: "
            + ", ".join(paths[:5])
            + ". Follow the tool schema and use exact returned identifiers.",
            422,
        )
    return item
