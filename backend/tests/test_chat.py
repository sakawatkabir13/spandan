import json
from datetime import timedelta
from functools import lru_cache
from uuid import UUID, uuid4

import httpx
import httpx2
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.base import utcnow
from app.main import app
from app.models.appointment import Appointment
from app.models.chamber import Chamber
from app.models.chat import ChatAction, ChatConversation, ChatMessage
from app.models.doctor import (
    AssistantAssignment,
    DoctorProfile,
    DoctorVerificationStatus,
    Specialization,
)
from app.models.operations import Dependent
from app.models.schedule import QueueState, Schedule
from app.models.user import PatientProfile, User, UserRole
from app.services.chat_actions import execute_action, prepare_action
from app.services.chat_contract import CONTRACT_VERSION, TOOL_CATALOG
from app.services.chat_mcp import delegation, mcp_client
from app.services.chat_security import digest, public_key_pem, seal
from app.services.chat_tools import read_tool
from app.services.llm import ModelReply


@lru_cache
def password_hash():
    return get_password_hash("Test-only-Password123!")


@pytest_asyncio.fixture
async def world(db_session, client, monkeypatch):
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_MCP_SERVICE_TOKEN", "test-service-credential-" + "x" * 32)
    monkeypatch.setattr(settings, "CHAT_MCP_URL", "http://mcp/mcp")
    users = {}
    for role in ["patient", "other", "doctor", "assistant", "administrator"]:
        user = User(
            id=uuid4(),
            email=role + "@chat.example",
            role=UserRole.PATIENT if role == "other" else UserRole(role),
            password_hash=password_hash(),
        )
        db_session.add(user)
        users[role] = user
    await db_session.flush()
    profiles = {}
    for name in ["patient", "other"]:
        profile = PatientProfile(
            id=uuid4(), user_id=users[name].id, full_name=name.title() + " Person"
        )
        db_session.add(profile)
        profiles[name] = profile
    doctor = DoctorProfile(
        id=uuid4(),
        user_id=users["doctor"].id,
        full_name="Dr Chat Test",
        medical_registration_number="CHAT-TEST-ONLY",
        verification_status=DoctorVerificationStatus.APPROVED,
    )
    specialty = Specialization(id=uuid4(), name="General Medicine", is_active=True)
    doctor.specializations = [specialty]
    db_session.add(doctor)
    await db_session.flush()
    chamber = Chamber(
        id=uuid4(),
        doctor_id=doctor.id,
        name="Chat Test Chamber",
        address="Test road",
        district="Dhaka",
        area="Test area",
        consultation_fee=500,
        follow_up_fee=300,
    )
    db_session.add(chamber)
    await db_session.flush()
    from datetime import time

    from app.core.time import local_now

    schedules = []
    for day in (1, 2):
        row = Schedule(
            id=uuid4(),
            doctor_id=doctor.id,
            chamber_id=chamber.id,
            schedule_date=local_now().date() + timedelta(days=day),
            start_time=time(17),
            end_time=time(21),
            maximum_patients=20,
            status="open",
        )
        db_session.add(row)
        schedules.append(row)
        db_session.add(
            QueueState(id=uuid4(), schedule_id=row.id, current_serial=0, delay_minutes=0)
        )
    assignment = AssistantAssignment(
        id=uuid4(),
        doctor_id=doctor.id,
        assistant_user_id=users["assistant"].id,
        is_active=True,
        can_manage_schedules=True,
        can_manage_appointments=True,
        can_update_queue=True,
    )
    dependent = Dependent(
        id=uuid4(),
        patient_id=profiles["patient"].id,
        full_name="Dependent Child",
        relationship_name="child",
    )
    db_session.add_all([assignment, dependent])
    await db_session.commit()
    headers = {
        name: {"Authorization": "Bearer " + create_access_token(u.id, u.role.value)}
        for name, u in users.items()
    }
    conversations = {}
    for name in users:
        response = await client.post(
            "/api/v1/chat/conversations", headers=headers[name], json={"provider_consent": True}
        )
        assert response.status_code == 201, response.text
        conversations[name] = UUID(response.json()["data"]["id"])
    return {
        "users": users,
        "headers": headers,
        "conversations": conversations,
        "doctor": doctor,
        "chamber": chamber,
        "schedules": schedules,
        "assignment": assignment,
        "dependent": dependent,
    }


@pytest_asyncio.fixture
async def mcp_bridge(world, monkeypatch):
    # This is the real independently packaged server and the real SDK client, not a mocked MCP implementation.
    from spandan_mcp.server import Settings as MCPSettings
    from spandan_mcp.server import create_app

    mcp_app = create_app(
        MCPSettings(
            env="development",
            api_base_url="http://test/api/v1/internal/chat-tools",
            service_token=settings.CHAT_MCP_SERVICE_TOKEN,
            public_key=public_key_pem(),
            allowed_hosts="mcp",
        ),
        http_factory=lambda: httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ),
    )

    def http_client(token):
        return httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=mcp_app),
            base_url="http://mcp",
            headers={"Authorization": "Bearer " + token},
        )

    monkeypatch.setattr(mcp_client, "_http_client", http_client)
    import asyncio

    started, stopped = asyncio.Event(), asyncio.Event()

    async def lifespan():
        async with mcp_app.app.router.lifespan_context(mcp_app.app):
            started.set()
            await stopped.wait()

    task = asyncio.create_task(lifespan())
    await started.wait()
    try:
        yield mcp_app
    finally:
        stopped.set()
        await task


async def actor(db, world, role):
    from sqlalchemy import inspect

    from app.repositories.user import user_repo

    return await user_repo.get_by_id_with_profiles(db, inspect(world["users"][role]).identity[0])


async def propose(db, world, role, name, args):
    user = await actor(db, world, role)
    conv = await db.get(ChatConversation, world["conversations"][role])
    return (await prepare_action(db, user, conv, name, args))["proposal"]


async def test_chat_is_gated_and_requires_consent(client, monkeypatch):
    monkeypatch.setattr(settings, "CHAT_ENABLED", False)
    assert (await client.get("/api/v1/chat/conversations")).status_code == 503
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    assert (await client.get("/api/v1/chat/conversations")).status_code == 401


async def test_mcp_booking_confirmation_is_atomic_and_retryable(
    world, mcp_bridge, client, db_session
):
    patient = await actor(db_session, world, "patient")
    conv = await db_session.get(ChatConversation, world["conversations"]["patient"])
    proposal = await mcp_client.call(
        patient, conv, "propose_book_appointment", {"schedule_id": str(world["schedules"][0].id)}
    )
    action_id = proposal["proposal"]["id"]
    assert not list(await db_session.scalars(select(Appointment)))
    with pytest.raises(Exception) as error:
        await execute_action(db_session, patient, UUID(action_id))
    assert error.value.code == "CONFIRMATION_REQUIRED"
    await db_session.rollback()
    for _ in range(2):
        response = await client.post(
            f"/api/v1/chat/actions/{action_id}/confirm",
            headers=world["headers"]["patient"],
            json={},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "succeeded"
    assert len(list(await db_session.scalars(select(Appointment)))) == 1


async def test_cross_user_and_role_access(world, mcp_bridge, client, db_session):
    proposal = await propose(
        db_session,
        world,
        "patient",
        "propose_book_appointment",
        {"schedule_id": str(world["schedules"][0].id)},
    )
    assert (
        await client.get(
            f"/api/v1/chat/actions/{proposal['id']}", headers=world["headers"]["other"]
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/chat/conversations/{world['conversations']['patient']}",
            headers=world["headers"]["other"],
        )
    ).status_code == 404
    patient = await actor(db_session, world, "patient")
    with pytest.raises(Exception) as error:
        await read_tool(db_session, patient, "admin_users", {})
    assert error.value.code == "FORBIDDEN"
    with pytest.raises(Exception):
        await propose(
            db_session,
            world,
            "assistant",
            "propose_user_status",
            {"user_id": str(patient.id), "is_active": False},
        )


async def test_fee_change_requires_new_proposal(world, client, db_session):
    proposal = await propose(
        db_session,
        world,
        "patient",
        "propose_book_appointment",
        {"schedule_id": str(world["schedules"][0].id)},
    )
    world["chamber"].consultation_fee = 700
    await db_session.commit()
    response = await client.post(
        f"/api/v1/chat/actions/{proposal['id']}/confirm",
        headers=world["headers"]["patient"],
        json={},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACTION_CHANGED"
    assert not list(await db_session.scalars(select(Appointment)))


async def test_expiry_and_dependent_ownership(world, client, db_session):
    with pytest.raises(Exception):
        await propose(
            db_session,
            world,
            "other",
            "propose_book_appointment",
            {
                "schedule_id": str(world["schedules"][0].id),
                "dependent_id": str(world["dependent"].id),
            },
        )
    proposal = await propose(
        db_session,
        world,
        "patient",
        "propose_book_appointment",
        {"schedule_id": str(world["schedules"][0].id)},
    )
    row = await db_session.get(ChatAction, UUID(proposal["id"]))
    row.expires_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()
    response = await client.post(
        f"/api/v1/chat/actions/{row.id}/confirm", headers=world["headers"]["patient"], json={}
    )
    assert response.status_code == 409


async def test_sensitive_action_requires_exact_fresh_auth(world, mcp_bridge, client, db_session):
    proposal = await propose(
        db_session,
        world,
        "administrator",
        "propose_user_status",
        {"user_id": str(world["users"]["other"].id), "is_active": False},
    )
    url = f"/api/v1/chat/actions/{proposal['id']}/confirm"
    headers = world["headers"]["administrator"]
    assert (await client.post(url, headers=headers, json={})).status_code == 403
    assert (
        await client.post(
            "/api/v1/chat/step-up",
            headers=headers,
            json={"action_id": proposal["id"], "password": "incorrect"},
        )
    ).status_code == 401
    verified = await client.post(
        "/api/v1/chat/step-up",
        headers=headers,
        json={"action_id": proposal["id"], "password": "Test-only-Password123!"},
    )
    assert verified.status_code == 200, verified.text
    assert (
        await client.post(url, headers=headers, json={"step_up_token": "tampered"})
    ).status_code == 403
    response = await client.post(url, headers=headers, json=verified.json()["data"])
    assert response.status_code == 200, response.text
    target = await db_session.get(User, world["users"]["other"].id)
    assert target.is_active is False


async def test_permission_revocation_invalidates_history_and_tools(world, client, db_session):
    assignment = world["assignment"]
    assignment.can_update_queue = False
    await db_session.commit()
    response = await client.get(
        f"/api/v1/chat/conversations/{world['conversations']['assistant']}",
        headers=world["headers"]["assistant"],
    )
    assert response.status_code == 403


async def test_transcript_encryption_and_deletion(world, client, db_session):
    ident = world["conversations"]["patient"]
    message = ChatMessage(
        conversation_id=ident, role="user", ciphertext=seal({"text": "private support request"})
    )
    db_session.add(message)
    await db_session.commit()
    assert "private support request" not in message.ciphertext
    proposal = await propose(
        db_session,
        world,
        "patient",
        "propose_book_appointment",
        {"schedule_id": str(world["schedules"][0].id)},
    )
    response = await client.delete(
        f"/api/v1/chat/conversations/{ident}", headers=world["headers"]["patient"]
    )
    assert response.status_code == 200
    assert not list(
        await db_session.scalars(select(ChatMessage).where(ChatMessage.conversation_id == ident))
    )
    row = await db_session.get(ChatAction, UUID(proposal["id"]))
    await db_session.refresh(row)
    assert row.status == "cancelled"


async def test_tool_outputs_exclude_medical_and_security_fields(world, db_session):
    admin = await actor(db_session, world, "administrator")
    result = await read_tool(db_session, admin, "admin_users", {})
    text = json.dumps(result)
    for secret in [
        "password_hash",
        "mfa_secret",
        "date_of_birth",
        "emergency_contact",
        "patient_profile",
    ]:
        assert secret not in text
    assert len(result["items"]) <= 10


async def test_audience_separation_and_unknown_contract(world, client, db_session):
    user = await actor(db_session, world, "patient")
    conv = await db_session.get(ChatConversation, world["conversations"]["patient"])
    subject = delegation(user, conv, ["help"])
    headers = {
        "X-MCP-Service-Token": settings.CHAT_MCP_SERVICE_TOKEN,
        "Authorization": "Bearer " + subject,
    }
    response = await client.post(
        "/api/v1/internal/chat-tools/call/help",
        headers=headers,
        json={"contract_version": CONTRACT_VERSION, "arguments": {}},
    )
    assert response.status_code == 401
    response = await client.post(
        "/api/v1/internal/chat-tools/exchange",
        headers=headers,
        json={"contract_version": "unknown", "subject_token": subject, "tool_name": "help"},
    )
    assert response.status_code == 409


async def test_streamed_tool_results_and_no_execution_from_yes(
    world, mcp_bridge, client, db_session, monkeypatch
):
    calls = []

    async def complete(**kwargs):
        calls.append(kwargs)
        return ModelReply(
            [
                {
                    "toolUse": {
                        "toolUseId": "test-call",
                        "name": "propose_book_appointment",
                        "input": {"schedule_id": str(world["schedules"][0].id)},
                    }
                }
            ],
            "tool_use",
            100,
            20,
        )

    monkeypatch.setattr("app.services.chat_service.bedrock_provider.complete", complete)

    async def stream(**kwargs):
        yield {"type": "reply", "reply": await complete(**kwargs)}

    monkeypatch.setattr("app.services.chat_service.bedrock_provider.stream", stream)
    response = await client.post(
        f"/api/v1/chat/conversations/{world['conversations']['patient']}/messages",
        headers=world["headers"]["patient"],
        json={"client_message_id": str(uuid4()), "text": "Book that session, yes."},
    )
    assert response.status_code == 200
    assert "event: proposal" in response.text, response.text
    assert "event: done" in response.text, response.text
    assert len(calls) == 1
    assert not list(await db_session.scalars(select(Appointment)))


async def test_contract_matches_standalone_server():
    from spandan_mcp.server import CONTRACT

    assert CONTRACT["version"] == CONTRACT_VERSION
    assert CONTRACT["sha256"] == digest(TOOL_CATALOG)
    assert CONTRACT["tools"] == TOOL_CATALOG
