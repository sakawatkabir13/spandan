import re
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from sqlalchemy import func, select

from app.core.config import settings
from app.models.email_otp import EmailOTP
from app.models.user import User
from app.services import mail

PAYLOAD = dict(
    email="new@gmail.com",
    password="FirstPassword123!",
    phone_number="+8801799998888",
    full_name="OTP Patient",
)


def code(client):
    return re.search(r"code is ([0-9]{6})", client.mailbox[-1][2])[1]


async def request(client, email=PAYLOAD["email"]):
    response = await client.post("/api/v1/auth/registration-code", json={"email": email})
    assert response.status_code == 200, response.text
    assert "token" not in response.text and "otp" not in (response.json().get("data") or {})
    return code(client)


async def test_no_account_until_registration_email_ownership_proven(client, db_session):
    assert (await client.post("/api/v1/auth/register/patient", json=PAYLOAD)).status_code == 422
    assert (
        await client.post("/api/v1/auth/register/patient", json={**PAYLOAD, "email_otp": "000000"})
    ).status_code == 400
    otp = await request(client)
    assert await db_session.scalar(select(func.count(User.id))) == 0
    challenge = await db_session.get(EmailOTP, (PAYLOAD["email"], "registration"))
    assert otp not in challenge.token_hash
    response = await client.post(
        "/api/v1/auth/register/patient", json={**PAYLOAD, "email_otp": otp}
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["user"]["is_email_verified"] is True
    await db_session.refresh(challenge)
    assert challenge.consumed_at
    assert (
        await client.post("/api/v1/auth/registration-code", json={"email": PAYLOAD["email"]})
    ).status_code == 409


async def test_signup_codes_are_email_bound_single_use_and_wrong_attempts_persist(
    client, db_session
):
    otp = await request(client)
    assert (
        await client.post(
            "/api/v1/auth/register/patient",
            json={**PAYLOAD, "email": "other@gmail.com", "email_otp": otp},
        )
    ).status_code == 400
    wrong = "999999" if otp != "999999" else "888888"
    for _ in range(5):
        assert (
            await client.post("/api/v1/auth/register/patient", json={**PAYLOAD, "email_otp": wrong})
        ).status_code == 400
    assert (
        await client.post("/api/v1/auth/register/patient", json={**PAYLOAD, "email_otp": otp})
    ).status_code == 400
    challenge = await db_session.get(EmailOTP, (PAYLOAD["email"], "registration"))
    await db_session.refresh(challenge)
    assert challenge.attempts == 5
    assert await db_session.scalar(select(func.count(User.id))) == 0


async def test_resend_cooldown_expiry_hourly_limit_and_previous_code_invalidated(
    client, db_session
):
    old = await request(client)
    assert (
        await client.post("/api/v1/auth/registration-code", json={"email": PAYLOAD["email"]})
    ).status_code == 429
    challenge = await db_session.get(EmailOTP, (PAYLOAD["email"], "registration"))
    challenge.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    await db_session.commit()
    new = await request(client)
    if new != old:
        assert (
            await client.post("/api/v1/auth/register/patient", json={**PAYLOAD, "email_otp": old})
        ).status_code == 400
    await db_session.refresh(challenge)
    challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    assert (
        await client.post("/api/v1/auth/register/patient", json={**PAYLOAD, "email_otp": new})
    ).status_code == 400
    challenge.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    challenge.requests_in_window = 6
    await db_session.commit()
    assert (
        await client.post("/api/v1/auth/registration-code", json={"email": PAYLOAD["email"]})
    ).status_code == 429


async def test_delivery_failure_is_explicit_and_does_not_create_account(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(mail, "send_email", Mock(side_effect=OSError("provider unavailable")))
    assert (
        await client.post("/api/v1/auth/registration-code", json={"email": PAYLOAD["email"]})
    ).status_code == 503
    challenge = await db_session.get(EmailOTP, (PAYLOAD["email"], "registration"))
    assert challenge.consumed_at is not None
    assert await db_session.scalar(select(func.count(User.id))) == 0
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    assert (
        await client.post("/api/v1/auth/registration-code", json={"email": "no-mail@gmail.com"})
    ).status_code == 503


async def test_password_reset_code_revokes_tokens_and_requires_same_email_and_purpose(
    client, db_session
):
    signup = await request(client)
    registered = await client.post(
        "/api/v1/auth/register/patient", json={**PAYLOAD, "email_otp": signup}
    )
    tokens = registered.json()["data"]
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    reset = dict(
        email=PAYLOAD["email"],
        purpose="reset",
        token=signup,
        new_password="ReplacementPassword123!",
    )
    assert (await client.post("/api/v1/auth/account-action", json=reset)).status_code == 400
    response = await client.post("/api/v1/auth/forgot-password", json={"email": PAYLOAD["email"]})
    assert response.status_code == 200
    reset["token"] = code(client)
    assert (
        await client.post("/api/v1/auth/account-action", json={**reset, "new_password": "short"})
    ).status_code == 422
    assert (await client.post("/api/v1/auth/account-action", json=reset)).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401
    assert (await client.post("/api/v1/auth/account-action", json=reset)).status_code == 400
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": PAYLOAD["email"], "password": reset["new_password"]},
        )
    ).status_code == 200
    before = len(client.mailbox)
    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "unknown@gmail.com"})
    assert unknown.status_code == 200 and unknown.json() == response.json()
    assert len(client.mailbox) == before
    assert (
        await client.post("/api/v1/auth/forgot-password", json={"email": "unknown@gmail.com"})
    ).status_code == 429


async def test_otp_not_exposed_in_notifications_and_normalized_email(client, db_session):
    from app.models.operations import Notification

    otp = await request(client, "NEW@gmail.com")
    assert client.mailbox[-1][0] == "new@gmail.com"
    assert await db_session.scalar(select(func.count(Notification.id))) == 0
    response = await client.post(
        "/api/v1/auth/register/patient",
        json={**PAYLOAD, "email": "NEW@gmail.com", "email_otp": otp},
    )
    assert response.status_code == 201
    assert response.json()["data"]["user"]["email"] == "new@gmail.com"


async def test_postgres_parallel_requests_and_registration_do_not_reuse_otp(client, db_session):
    import asyncio

    import pytest
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db
    from app.main import app
    from tests.conftest import test_async_session_maker

    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("Concurrent verification requires PostgreSQL row and advisory locks")

    async def independent_db():
        async with test_async_session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = independent_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            requests = await asyncio.gather(
                *[
                    ac.post("/api/v1/auth/registration-code", json={"email": PAYLOAD["email"]})
                    for _ in range(2)
                ]
            )
            assert sorted(r.status_code for r in requests) == [200, 429]
            assert len(client.mailbox) == 1
            otp = code(client)
            results = await asyncio.gather(
                *[
                    ac.post(
                        "/api/v1/auth/register/patient",
                        json={**PAYLOAD, "phone_number": f"+880179999888{i}", "email_otp": otp},
                    )
                    for i in range(2)
                ]
            )
            statuses = sorted(r.status_code for r in results)
            assert statuses[0] == 201 and statuses[1] in (400, 409)
        assert await db_session.scalar(select(func.count(User.id))) == 1
    finally:
        app.dependency_overrides[get_db] = previous
