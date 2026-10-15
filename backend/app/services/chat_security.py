import base64
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import SpandanException
from app.core.time import aware
from app.db.base import utcnow
from app.models.chat import ChatAction, ChatConversation
from app.models.doctor import AssistantAssignment, DoctorProfile
from app.repositories.user import user_repo
from app.services.chat_contract import CONTRACT_VERSION, TOOL_CATALOG


def canonical(value):
    from fastapi.encoders import jsonable_encoder

    return json.dumps(jsonable_encoder(value), sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def cipher():
    key = settings.CHAT_ENCRYPTION_KEY
    if not key and settings.APP_ENV == "production":
        raise SpandanException("CHAT_UNAVAILABLE", "Support is unavailable.", 503)
    return Fernet(
        base64.urlsafe_b64encode(
            hashlib.sha256(("chat:" + (key or settings.JWT_SECRET_KEY)).encode()).digest()
        )
    )


def seal(value):
    return cipher().encrypt(canonical(value).encode()).decode()


def unseal(value):
    try:
        return json.loads(cipher().decrypt(value.encode()))
    except Exception:
        raise SpandanException(
            "CHAT_UNAVAILABLE", "This conversation could not be opened.", 503
        ) from None


def private_key():
    value = settings.CHAT_SIGNING_PRIVATE_KEY
    if value:
        return serialization.load_pem_private_key(
            value.replace("\\n", "\n").encode(), password=None
        )
    if settings.APP_ENV == "production":
        raise SpandanException("CHAT_UNAVAILABLE", "Support signing is unavailable.", 503)
    return Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(("chat-signing:" + settings.JWT_SECRET_KEY).encode()).digest()
    )


def public_key_pem():
    return (
        private_key()
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


def issue_token(claims, audience):
    now = utcnow()
    return jwt.encode(
        {
            **claims,
            "iss": "spandan",
            "aud": audience,
            "iat": now,
            "exp": now + timedelta(seconds=90),
            "jti": str(uuid4()),
            "contract": CONTRACT_VERSION,
        },
        private_key(),
        algorithm="EdDSA",
    )


def decode_delegation(token, audience):
    try:
        claims = jwt.decode(
            token,
            private_key().public_key(),
            algorithms=["EdDSA"],
            audience=audience,
            issuer="spandan",
            options={
                "require": [
                    "sub",
                    "ver",
                    "exp",
                    "iat",
                    "jti",
                    "aud",
                    "iss",
                    "contract",
                    "conversation_id",
                    "fingerprint",
                    "tools",
                ]
            },
        )
        if claims["contract"] != CONTRACT_VERSION:
            raise ValueError()
        return claims
    except Exception:
        raise SpandanException(
            "INVALID_DELEGATION", "Service authorization is invalid or expired.", 401
        ) from None


async def fingerprint(db, user):
    # Query permission columns each time; do not trust cached ORM relationships or JWT roles.
    await db.refresh(user, ["role", "is_active", "token_version"])
    rows = await db.execute(
        select(
            AssistantAssignment.id,
            AssistantAssignment.doctor_id,
            AssistantAssignment.is_active,
            AssistantAssignment.can_manage_schedules,
            AssistantAssignment.can_manage_appointments,
            AssistantAssignment.can_update_queue,
        )
        .where(AssistantAssignment.assistant_user_id == user.id)
        .order_by(AssistantAssignment.id)
    )
    doctor = (
        await db.execute(
            select(DoctorProfile.id, DoctorProfile.verification_status).where(
                DoctorProfile.user_id == user.id
            )
        )
    ).first()
    return digest(
        {
            "role": user.role.value,
            "active": user.is_active,
            "ver": user.token_version,
            "assignments": [list(r) for r in rows],
            "doctor": list(doctor) if doctor else None,
        }
    )


async def conversation_for_user(db, user, conversation_id, *, lock=False):
    stmt = select(ChatConversation).where(
        ChatConversation.id == conversation_id, ChatConversation.user_id == user.id
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    row = await db.scalar(stmt)
    if not row or row.deleted_at or aware(row.expires_at) <= utcnow():
        raise SpandanException("NOT_FOUND", "Conversation not found or expired.", 404)
    if not user.is_active or row.access_fingerprint != await fingerprint(db, user):
        raise SpandanException(
            "CHAT_ACCESS_CHANGED", "Your access has changed. Start a new conversation.", 403
        )
    return row


async def actor_from_claims(db, claims, tool_name):
    if tool_name not in claims.get("tools", []):
        raise SpandanException("FORBIDDEN", "This delegated tool is not permitted.", 403)
    try:
        user = await user_repo.get_by_id_with_profiles(db, UUID(claims["sub"]))
        if not user or not user.is_active or user.token_version != claims["ver"]:
            raise ValueError()
        if tool_name == "execute_confirmed_action":
            action = await db.get(ChatAction, UUID(claims["action_id"]))
            conversation = await execution_conversation(db, user, action)
            if str(conversation.id) != claims["conversation_id"]:
                raise ValueError()
        else:
            conversation = await conversation_for_user(
                db, user, UUID(claims["conversation_id"]), lock=tool_name.startswith("propose_")
            )
        if conversation.access_fingerprint != claims["fingerprint"]:
            raise ValueError()
        if (
            claims.get("generation_id")
            and str(conversation.generation_id) != claims["generation_id"]
        ):
            raise SpandanException("CHAT_STOPPED", "This generation has been stopped.", 409)
        return user, conversation
    except SpandanException:
        raise
    except Exception:
        raise SpandanException("INVALID_DELEGATION", "Delegated access has expired.", 401) from None


async def execution_conversation(db, user, action):
    """A confirmed business operation survives transcript deletion and generation stop."""
    if (
        not action
        or action.actor_user_id != user.id
        or action.status not in {"confirmed", "succeeded"}
    ):
        raise SpandanException(
            "CONFIRMATION_REQUIRED", "An owned confirmed action is required.", 403
        )
    row = await db.get(ChatConversation, action.conversation_id)
    access = await fingerprint(db, user)
    if (
        not row
        or row.user_id != user.id
        or access != action.access_fingerprint
        or access != row.access_fingerprint
        or not user.is_active
    ):
        raise SpandanException(
            "CHAT_ACCESS_CHANGED", "Your access changed. This action cannot be retried.", 403
        )
    return row


def chat_release_ready():
    if not settings.CHAT_ENABLED:
        return False
    if settings.APP_ENV != "production":
        return True
    try:
        from app.services.chat_service import SYSTEM

        report = json.loads(Path(settings.CHAT_EVALUATION_FILE).read_text())
        return bool(
            report["qualified"]
            and report["scenario_count"] == 100
            and report["selected_model"] == settings.BEDROCK_CHAT_MODEL
            and report["contract_sha256"] == digest(TOOL_CATALOG)
            and report["prompt_sha256"] == digest(SYSTEM)
            and report["security_passed"]
        )
    except (OSError, ValueError, KeyError):
        return False


def require_chat():
    if not chat_release_ready():
        raise SpandanException(
            "CHAT_UNAVAILABLE",
            "Spandan Assistant is not available yet. Please use the website controls.",
            503,
        )
