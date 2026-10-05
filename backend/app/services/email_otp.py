import asyncio
import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from app.core.config import settings
from app.core.exceptions import SpandanException
from app.core.time import aware
from app.models.email_otp import EmailOTP
from app.services import mail

logger = logging.getLogger(__name__)


def digest(email, purpose, nonce, code):
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        f"otp:{email}:{purpose}:{nonce}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


async def lock_email(db, email, purpose):
    if db.bind.dialect.name == "postgresql":
        key = (
            int.from_bytes(hashlib.sha256(f"otp:{email}:{purpose}".encode()).digest()[:8], "big")
            >> 1
        )
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


async def issue_email_otp(db, email, purpose, *, deliver=True):
    if not settings.email_enabled:
        raise SpandanException(
            "DELIVERY_UNAVAILABLE",
            "Email delivery is unavailable. Please try again later or contact support.",
            503,
        )
    email = email.strip().lower()
    await lock_email(db, email, purpose)
    challenge = await db.scalar(
        select(EmailOTP)
        .where(
            EmailOTP.email == email,
            EmailOTP.purpose == purpose,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(timezone.utc)
    if challenge and aware(challenge.created_at) > now - timedelta(seconds=60):
        raise SpandanException(
            "RATE_LIMITED", "Wait one minute before requesting another code.", 429
        )
    if (
        challenge
        and aware(challenge.window_started_at) > now - timedelta(hours=1)
        and challenge.requests_in_window >= 6
    ):
        raise SpandanException(
            "RATE_LIMITED", "Too many code requests. Please try again in one hour.", 429
        )
    if not challenge:
        challenge = EmailOTP(
            email=email, purpose=purpose, window_started_at=now, requests_in_window=0
        )
        db.add(challenge)
    elif aware(challenge.window_started_at) <= now - timedelta(hours=1):
        challenge.window_started_at = now
        challenge.requests_in_window = 0
    code = f"{secrets.randbelow(1000000):06d}"
    challenge.nonce = str(uuid.uuid4())
    challenge.token_hash = digest(email, purpose, challenge.nonce, code)
    challenge.attempts = 0
    challenge.created_at = now
    challenge.expires_at = now + timedelta(minutes=10)
    challenge.consumed_at = None
    challenge.requests_in_window += 1
    await db.flush()
    if deliver:
        label = "registration" if purpose == "registration" else "password reset"
        try:
            await asyncio.to_thread(
                mail.send_email,
                email,
                f"Spandan {label} code",
                f"Your Spandan {label} code is {code}.\n\nIt expires in 10 minutes and can be used once. "
                "Do not share this code. If you did not request it, ignore this email.\n\nSpandan — community.cuetinsights@gmail.com",
            )
        except Exception as exc:
            # Keep resend limits even when the provider fails; the undelivered code is unusable.
            challenge.consumed_at = now
            await db.commit()
            logger.warning("otp_delivery_failed type=%s", type(exc).__name__)
            raise SpandanException(
                "DELIVERY_UNAVAILABLE",
                "We could not send the email. Please try again in one minute.",
                503,
            ) from None
    else:
        challenge.consumed_at = now


async def consume_email_otp(db, email, purpose, code):
    email = email.strip().lower()
    await lock_email(db, email, purpose)
    challenge = await db.scalar(
        select(EmailOTP)
        .where(
            EmailOTP.email == email,
            EmailOTP.purpose == purpose,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(timezone.utc)
    if (
        not code
        or not challenge
        or challenge.consumed_at
        or challenge.attempts >= 5
        or aware(challenge.expires_at) <= now
    ):
        raise SpandanException(
            "INVALID_OTP", "The verification code is invalid or expired. Request a new code.", 400
        )
    if not hmac.compare_digest(challenge.token_hash, digest(email, purpose, challenge.nonce, code)):
        challenge.attempts += 1
        await db.commit()
        raise SpandanException(
            "INVALID_OTP", "The verification code is invalid or expired. Request a new code.", 400
        )
    challenge.consumed_at = now
