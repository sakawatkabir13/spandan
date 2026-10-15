# ruff: noqa: F811
import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.base import utcnow
from app.models.chat import ChatAction, ChatConversation, ChatMessage
from app.schemas.chat import MessageCreate
from app.services.chat_actions import confirm_action, execute_action
from app.services.chat_retention import cleanup_chat
from app.services.chat_security import seal
from app.services.chat_service import reserve_turn
from app.services.chat_tools import read_tool
from tests.test_chat import actor, mcp_bridge, propose, world  # noqa: F401


async def test_waitlist_answers_include_reserved_offers_for_only_the_current_patient(world, db_session):
    from app.models.operations import WaitlistEntry

    patient = await actor(db_session, world, "patient")
    other = await actor(db_session, world, "other")
    expires = utcnow() + timedelta(minutes=10)
    db_session.add_all([
        WaitlistEntry(patient_id=patient.patient_profile.id, schedule_id=world["schedules"][0].id,
                      status="offered", offered_at=utcnow(), offer_expires_at=expires),
        WaitlistEntry(patient_id=other.patient_profile.id, schedule_id=world["schedules"][1].id,
                      status="waiting"),
    ])
    await db_session.commit()
    answer = await read_tool(db_session, patient, "list_waitlist", {})
    assert len(answer["items"]) == 1
    offer = answer["items"][0]
    assert offer["status"] == "offered"
    assert offer["doctor_name"] == "Dr Chat Test"
    assert offer["chamber"] == "Chat Test Chamber"
    assert offer["offer_expires_at"]
    assert offer["href"] == "/dashboard/patient/tools?tab=waitlist"


async def test_session_answers_distinguish_staff_confirmation_from_hospital_sources(world, db_session, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    patient = await actor(db_session, world, "patient")
    args = {"doctor_id": str(world["doctor"].id)}
    session = world["schedules"][0]
    session.confirmed_at = utcnow()
    await db_session.commit()
    answer = await read_tool(db_session, patient, "list_sessions", args)
    assert "published by chamber staff" in answer["items"][0]["availability_note"]
    assert answer["items"][0]["href"] == f'/doctors/{world["doctor"].id}'
    world["doctor"].is_demo = True
    await db_session.commit()
    answer = await read_tool(db_session, patient, "list_sessions", args)
    assert "Contact the hospital" in answer["items"][0]["availability_note"]
    assert answer["items"][0]["doctor_name"] == "Dr Chat Test"


async def test_expired_generation_does_not_leave_history_stuck_processing(world, db_session, client):
    row = await db_session.get(ChatConversation, world["conversations"]["patient"])
    row.generation_id = uuid4()
    row.generation_until = utcnow() - timedelta(seconds=1)
    await db_session.commit()
    response = await client.get(f"/api/v1/chat/conversations/{row.id}", headers=world["headers"]["patient"])
    assert response.status_code == 200
    assert response.json()["data"]["generating"] is False


async def test_retention_expiry_and_pending_cancellation(world, db_session):  # noqa: F811
    conversation = await db_session.get(ChatConversation, world["conversations"]["patient"])
    conversation.expires_at = utcnow() - timedelta(seconds=1)
    db_session.add(
        ChatMessage(
            conversation_id=conversation.id, role="user", ciphertext=seal({"text": "erase me"})
        )
    )
    # Use a live second conversation to prepare, then move its expiry.
    conversation.expires_at = utcnow() + timedelta(days=1)
    await db_session.commit()
    proposal = await propose(
        db_session,
        world,
        "patient",
        "propose_book_appointment",
        {"schedule_id": str(world["schedules"][0].id)},
    )
    conversation.expires_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()
    await cleanup_chat(db_session, utcnow())
    await db_session.commit()
    assert not list(await db_session.scalars(select(ChatMessage)))
    row = await db_session.get(ChatAction, UUID(proposal["id"]))
    assert row.status == "cancelled"


async def test_quota_duplicate_request_and_generation_lease(world, db_session, monkeypatch):  # noqa: F811
    user = await actor(db_session, world, "patient")
    cid = world["conversations"]["patient"]
    request = MessageCreate(client_message_id=uuid4(), text="Show appointments")
    await reserve_turn(db_session, user, cid, request)
    with pytest.raises(Exception) as error:
        await reserve_turn(db_session, user, cid, request)
    assert error.value.code == "MESSAGE_ALREADY_SENT"
    await db_session.rollback()
    user = await actor(db_session, world, "patient")
    with pytest.raises(Exception) as error:
        await reserve_turn(
            db_session, user, cid, MessageCreate(client_message_id=uuid4(), text="Another")
        )
    assert error.value.code == "CHAT_BUSY"
    await db_session.rollback()
    conversation = await db_session.get(ChatConversation, cid)
    conversation.generation_until = None
    await db_session.commit()
    user = await actor(db_session, world, "patient")
    monkeypatch.setattr(settings, "CHAT_TURNS_PER_MINUTE", 1)
    with pytest.raises(Exception) as error:
        await reserve_turn(
            db_session, user, cid, MessageCreate(client_message_id=uuid4(), text="Another")
        )
    assert error.value.code == "RATE_LIMITED"


async def test_patient_queue_and_staff_queue_only_permission(world, db_session):  # noqa: F811
    from app.schemas.appointment import AppointmentCreate
    from app.services.appointment import appointment_service

    patient = await actor(db_session, world, "patient")
    appointment = await appointment_service.book_appointment(
        db_session, patient, AppointmentCreate(schedule_id=world["schedules"][0].id)
    )
    data = await read_tool(
        db_session,
        patient,
        "queue_status",
        {"schedule_id": str(appointment.schedule_id), "appointment_id": str(appointment.id)},
    )
    assert data["your_serial_number"] == 1
    world["assignment"].can_manage_schedules = False
    world["assignment"].can_manage_appointments = False
    await db_session.commit()
    assistant = await actor(db_session, world, "assistant")
    result = await read_tool(
        db_session, assistant, "queue_status", {"schedule_id": str(appointment.schedule_id)}
    )
    assert result["current_serial_running"] == 0


async def test_stop_invalidates_a_previously_issued_generation_grant(
    world,
    mcp_bridge,
    db_session,
    client,  # noqa: F811
):  # noqa: F811
    from app.services.chat_mcp import delegation
    from app.services.chat_security import actor_from_claims, decode_delegation

    patient = await actor(db_session, world, "patient")
    conversation, _ = await reserve_turn(
        db_session,
        patient,
        world["conversations"]["patient"],
        MessageCreate(client_message_id=uuid4(), text="Book"),
    )
    claims = decode_delegation(
        delegation(patient, conversation, ["propose_book_appointment"]), "spandan-mcp"
    )
    response = await client.post(
        f"/api/v1/chat/conversations/{conversation.id}/stop", headers=world["headers"]["patient"]
    )
    assert response.status_code == 200
    with pytest.raises(Exception) as error:
        await actor_from_claims(db_session, claims, "propose_book_appointment")
    assert error.value.code == "CHAT_STOPPED"


async def test_confirmed_cash_payment_and_refund(world, db_session):  # noqa: F811
    from app.models.operations import Payment
    from app.schemas.appointment import AppointmentCreate, AppointmentStatusUpdate
    from app.services.appointment import appointment_service
    from app.services.chat_actions import step_up

    patient = await actor(db_session, world, "patient")
    appointment = await appointment_service.book_appointment(
        db_session, patient, AppointmentCreate(schedule_id=world["schedules"][0].id)
    )
    apt_id = appointment.id
    doctor = await actor(db_session, world, "doctor")
    proposal = await propose(
        db_session, world, "doctor", "propose_cash_payment", {"appointment_id": str(apt_id)}
    )
    action_id = UUID(proposal["id"])
    proof = await step_up(db_session, doctor, action_id, "Test-only-Password123!", None)
    await confirm_action(db_session, doctor, action_id, proof)
    for _ in range(2):
        assert (await execute_action(db_session, doctor, action_id))["action"][
            "status"
        ] == "succeeded"
    payment = await db_session.scalar(select(Payment).where(Payment.appointment_id == apt_id))
    assert payment.status == "paid" and payment.amount == 500
    await appointment_service.update_status(
        db_session, doctor, apt_id, AppointmentStatusUpdate(appointment_status="cancelled")
    )
    proposal = await propose(
        db_session, world, "doctor", "propose_refund", {"payment_id": str(payment.id)}
    )
    action_id = UUID(proposal["id"])
    proof = await step_up(db_session, doctor, action_id, "Test-only-Password123!", None)
    await confirm_action(db_session, doctor, action_id, proof)
    result = await execute_action(db_session, doctor, action_id)
    assert "cash" in result["action"]["result"]["message"].lower()
    await db_session.refresh(payment)
    assert payment.status == "refunded"


async def test_postgres_duplicate_execution_across_sessions(world, db_session):  # noqa: F811
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("Row-lock concurrency requires PostgreSQL")
    from app.models.appointment import Appointment
    from tests.conftest import test_async_session_maker

    proposal = await propose(
        db_session,
        world,
        "patient",
        "propose_book_appointment",
        {"schedule_id": str(world["schedules"][0].id)},
    )
    user = await actor(db_session, world, "patient")
    aid = UUID(proposal["id"])
    await confirm_action(db_session, user, aid)

    async def execute():
        async with test_async_session_maker() as separate:
            user = await actor(separate, world, "patient")
            return await execute_action(separate, user, aid)

    results = await asyncio.gather(execute(), execute())
    assert all(result["action"]["status"] == "succeeded" for result in results)
    assert len(list(await db_session.scalars(select(Appointment)))) == 1


async def test_checkout_recovers_uncertain_provider_outcome_with_same_operation(
    world, db_session, monkeypatch
):
    from app.core.exceptions import SpandanException
    from app.models.operations import Payment
    from app.schemas.appointment import AppointmentCreate
    from app.services import billing
    from app.services.appointment import appointment_service

    patient = await actor(db_session, world, "patient")
    appointment = await appointment_service.book_appointment(
        db_session, patient, AppointmentCreate(schedule_id=world["schedules"][0].id)
    )
    proposal = await propose(
        db_session, world, "patient", "propose_checkout", {"appointment_id": str(appointment.id)}
    )
    aid = UUID(proposal["id"])
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_fixture")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_fixture")
    keys = []

    async def provider(method, path, data=None, key=None):
        keys.append(key)
        if len(keys) == 1:
            raise SpandanException("PAYMENT_PROVIDER_ERROR", "Response interrupted.", 502)
        return {
            "id": "cs_test_reconciled",
            "url": "https://checkout.stripe.com/test_reconciled",
            "livemode": False,
        }

    monkeypatch.setattr(billing, "stripe", provider)
    await confirm_action(db_session, patient, aid)
    with pytest.raises(SpandanException):
        await execute_action(db_session, patient, aid)
    patient = await actor(db_session, world, "patient")
    result = await execute_action(db_session, patient, aid)
    assert result["action"]["status"] == "succeeded"
    assert keys[0] == keys[1]
    assert len(list(await db_session.scalars(select(Payment)))) == 1


async def test_confirmed_operation_survives_transcript_deletion(world, client, db_session):
    proposal = await propose(
        db_session,
        world,
        "patient",
        "propose_book_appointment",
        {"schedule_id": str(world["schedules"][0].id)},
    )
    patient = await actor(db_session, world, "patient")
    aid = UUID(proposal["id"])
    await confirm_action(db_session, patient, aid)
    response = await client.delete(
        f"/api/v1/chat/conversations/{world['conversations']['patient']}",
        headers=world["headers"]["patient"],
    )
    assert response.status_code == 200
    assert (await execute_action(db_session, patient, aid))["action"]["status"] == "succeeded"


async def test_staff_session_and_queue_actions_use_common_services(world, db_session):
    from app.core.time import local_now

    assistant = await actor(db_session, world, "assistant")
    proposal = await propose(
        db_session,
        world,
        "assistant",
        "propose_create_session",
        {
            "chamber_id": str(world["chamber"].id),
            "schedule_date": str(local_now().date() + timedelta(days=5)),
            "start_time": "17:00",
            "end_time": "20:00",
            "maximum_patients": 12,
        },
    )
    aid = UUID(proposal["id"])
    await confirm_action(db_session, assistant, aid)
    result = await execute_action(db_session, assistant, aid)
    schedule_id = result["action"]["result"]["schedule_id"]
    proposal = await propose(
        db_session,
        world,
        "assistant",
        "propose_queue_delay",
        {"schedule_id": schedule_id, "delay_minutes": 15},
    )
    aid = UUID(proposal["id"])
    await confirm_action(db_session, assistant, aid)
    result = await execute_action(db_session, assistant, aid)
    assert result["action"]["result"]["delay_minutes"] == 15


async def test_restoring_permissions_does_not_resurrect_old_conversation(world, db_session):
    from app.services.appointment_operations import update_assistant_permissions
    from app.services.chat_security import conversation_for_user

    doctor = await actor(db_session, world, "doctor")
    assignment_id = world["assignment"].id
    changes = dict(
        is_active=True,
        can_manage_schedules=True,
        can_manage_appointments=True,
        can_update_queue=False,
    )
    await update_assistant_permissions(db_session, doctor, assignment_id, changes)
    await update_assistant_permissions(
        db_session, doctor, assignment_id, {**changes, "can_update_queue": True}
    )
    assistant = await actor(db_session, world, "assistant")
    with pytest.raises(Exception) as error:
        await conversation_for_user(db_session, assistant, world["conversations"]["assistant"])
    assert error.value.code == "CHAT_ACCESS_CHANGED"


async def test_staff_cards_link_to_their_own_authorized_workspace(world, db_session):
    from app.schemas.appointment import AppointmentCreate
    from app.services.appointment import appointment_service

    patient = await actor(db_session, world, "patient")
    await appointment_service.book_appointment(
        db_session, patient, AppointmentCreate(schedule_id=world["schedules"][0].id)
    )
    for role in ["doctor", "assistant", "administrator"]:
        user = await actor(db_session, world, role)
        slug = "admin" if role == "administrator" else role
        cards = await read_tool(db_session, user, "list_appointments", {})
        assert cards["items"][0]["href"].startswith(f"/dashboard/{slug}/queue")
        cards = await read_tool(db_session, user, "list_payments", {})
        assert cards["items"][0]["href"].startswith(f"/dashboard/{slug}/tools?tab=billing")
