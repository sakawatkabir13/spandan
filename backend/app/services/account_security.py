import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import SpandanException
from app.core.time import aware
from app.models.audit import AuditLog
from app.models.operations import AccountAction, Notification
from app.models.user import User


def cipher():
    return Fernet(
        base64.urlsafe_b64encode(
            hashlib.sha256(
                ("mfa:" + (settings.MFA_ENCRYPTION_KEY or settings.JWT_SECRET_KEY)).encode()
            ).digest()
        )
    )


def totp(secret, counter):
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{number % 1000000:06d}"


def validate_mfa(user, code, allow_pending=False):
    if not user.mfa_secret or (not allow_pending and not user.mfa_enabled):
        return
    if not code:
        raise SpandanException("MFA_REQUIRED", "Enter the six-digit authenticator code.", 401)
    try:
        secret = cipher().decrypt(user.mfa_secret.encode()).decode()
    except Exception:
        raise SpandanException(
            "MFA_UNAVAILABLE", "Contact the administrator to recover this authenticator.", 503
        )
    current = int(time.time() // 30)
    counter = next(
        (
            c
            for c in (current - 1, current, current + 1)
            if c > user.mfa_last_counter and hmac.compare_digest(totp(secret, c), str(code))
        ),
        None,
    )
    if counter is None:
        raise SpandanException("INVALID_MFA", "Authenticator code is invalid or already used.", 401)
    user.mfa_last_counter = counter


async def issue_action(db, user, purpose):
    channel = "sms" if purpose == "phone" else "email"
    configured = bool(settings.TWILIO_ACCOUNT_SID) if channel == "sms" else bool(settings.SMTP_HOST)
    if not configured:
        raise SpandanException(
            "DELIVERY_UNAVAILABLE",
            "Contact verification and recovery delivery is not configured. Please contact support.",
            503,
        )
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    # Only one outstanding challenge per user/purpose. Tokens never appear in API responses.
    existing = list(
        (
            await db.scalars(
                select(AccountAction)
                .where(
                    AccountAction.user_id == user.id,
                    AccountAction.purpose == purpose,
                    AccountAction.consumed_at.is_(None),
                )
                .with_for_update()
            )
        ).all()
    )
    now = datetime.now(timezone.utc)
    if any(aware(action.created_at) > now - timedelta(minutes=1) for action in existing):
        raise SpandanException(
            "RATE_LIMITED", "Wait one minute before requesting another code.", 429
        )
    for action in existing:
        action.consumed_at = now
    token = f"{secrets.randbelow(1000000):06d}" if purpose == "phone" else secrets.token_urlsafe(32)
    digest = hashlib.sha256(f"{user.id}:{purpose}:{token}".encode()).hexdigest()
    action = AccountAction(
        user_id=user.id, purpose=purpose, token_hash=digest, expires_at=now + timedelta(minutes=15)
    )
    db.add(action)
    if purpose == "phone":
        message = f"Your Spandan verification code is {token}. It expires in 15 minutes."
    else:
        message = f"{settings.FRONTEND_URL}/account-action?{urlencode({'purpose': purpose, 'token': token, 'email': user.email})}"
    db.add(
        Notification(
            user_id=user.id, channel=channel, subject="Spandan account security", message=message
        )
    )
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action=f"account.{purpose}_requested",
            entity_type="user",
            entity_id=str(user.id),
        )
    )


async def consume_action(db, user, purpose, token):
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    await db.refresh(user)
    digest = hashlib.sha256(f"{user.id}:{purpose}:{token}".encode()).hexdigest()
    action = await db.scalar(
        select(AccountAction)
        .where(
            AccountAction.user_id == user.id,
            AccountAction.purpose == purpose,
            AccountAction.consumed_at.is_(None),
        )
        .order_by(AccountAction.created_at.desc())
        .with_for_update()
        .limit(1)
    )
    if not action or action.attempts >= 5 or aware(action.expires_at) <= datetime.now(timezone.utc):
        raise SpandanException("INVALID_TOKEN", "This link or code is invalid or has expired.", 400)
    if not hmac.compare_digest(action.token_hash, digest):
        action.attempts += 1
        await db.commit()  # Persist failed attempts even though the request returns an error.
        raise SpandanException("INVALID_TOKEN", "This link or code is invalid or has expired.", 400)
    action.consumed_at = datetime.now(timezone.utc)
    return action
