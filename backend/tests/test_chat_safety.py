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
