import base64
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.dependencies.auth import get_current_active_user
from app.core.exceptions import SpandanException, create_success_response
from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.repositories.user import user_repo
from app.services.account_security import cipher, consume_action, issue_action, validate_mfa
from app.services.email_otp import consume_email_otp, issue_email_otp

router = APIRouter(prefix="/auth", tags=["Account recovery and verification"])


class RecoveryRequest(BaseModel):
    email: EmailStr


class CompleteAction(RecoveryRequest):
    token: str = Field(min_length=6, max_length=100)
    purpose: str = Field(pattern="^(reset|email|phone)$")
    new_password: str | None = Field(None, min_length=12, max_length=128)


class MfaRequest(BaseModel):
    password: str = Field(max_length=128)
    code: str | None = Field(None, pattern="^[0-9]{6}$")


@router.post("/registration-code")
async def registration_code(request: RecoveryRequest, db=Depends(get_db)):
    if await user_repo.get_by_email(db, request.email):
        raise SpandanException("CONFLICT", "An account with this email already exists. Sign in or reset your password.", 409)
    await issue_email_otp(db, request.email, "registration")
    await db.commit()
    return create_success_response("A six-digit verification code has been sent. Check your inbox and spam folder.")


@router.post("/forgot-password")
async def forgot_password(request: RecoveryRequest, db=Depends(get_db)):
    from app.core.config import settings

    if not settings.email_enabled:
        raise SpandanException(
            "DELIVERY_UNAVAILABLE",
            "Password recovery delivery is not configured. Contact support.",
            503,
        )
    user = await user_repo.get_by_email(db, request.email)
    await issue_email_otp(db, request.email, "reset", deliver=bool(user and user.is_active and not user.email.endswith((".invalid", "@demo.spandan.example.com"))))
    await db.commit()
    return create_success_response("If an active account exists, a six-digit reset code has been sent. Check your inbox and spam folder.")


@router.post("/verify/{purpose}/request")
async def request_verification(
    purpose: str, user=Depends(get_current_active_user), db=Depends(get_db)
):
    if purpose not in ("email", "phone"):
        raise SpandanException("VALIDATION_ERROR", "Choose email or phone verification.")
    await issue_action(db, user, purpose)
    await db.commit()
    return create_success_response("Verification instructions have been queued.")


@router.post("/account-action")
async def complete_action(request: CompleteAction, db=Depends(get_db)):
    user = await user_repo.get_by_email(db, request.email)
    if not user or not user.is_active:
        raise SpandanException("INVALID_TOKEN", "This link or code is invalid or expired.")
    if request.purpose == "reset":
        if not request.new_password:
            raise SpandanException(
                "VALIDATION_ERROR", "A new password of at least 12 characters is required."
            )
        if len(request.token) != 6 or not request.token.isascii() or not request.token.isdigit():
            raise SpandanException("INVALID_OTP", "Enter the six-digit code from your email.", 400)
        await consume_email_otp(db, user.email, "reset", request.token)
        user = await db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
        if not user.is_active:
            raise SpandanException("INVALID_OTP", "This code is invalid or expired.", 400)
        user.is_email_verified = True
        user.password_hash = get_password_hash(request.new_password)
        user.token_version += 1
    else:
        await consume_action(db, user, request.purpose, request.token)
        if request.purpose == "email":
            user.is_email_verified = True
        else:
            user.is_phone_verified = True
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action=f"account.{request.purpose}_completed",
            entity_type="user",
            entity_id=str(user.id),
        )
    )
    await db.commit()
    return create_success_response("Account security action completed.")


@router.post("/mfa/setup")
async def setup_mfa(
    request: MfaRequest, current=Depends(get_current_active_user), db=Depends(get_db)
):
    user = await db.scalar(
        select(User)
        .where(User.id == current.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not verify_password(request.password, user.password_hash):
        raise SpandanException("INVALID_CREDENTIALS", "Incorrect password.", 401)
    if user.mfa_enabled:
        raise SpandanException(
            "CONFLICT", "Disable the existing authenticator before replacing it.", 409
        )
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    user.mfa_secret = cipher().encrypt(secret.encode()).decode()
    user.mfa_last_counter = -1
    await db.commit()
    return create_success_response(
        "Save the secret in an authenticator, then confirm a code.",
        {
            "secret": secret,
            "uri": f"otpauth://totp/Spandan:{quote(user.email)}?secret={secret}&issuer=Spandan&digits=6&period=30",
        },
    )


@router.post("/mfa/{action}")
async def manage_mfa(
    action: str, request: MfaRequest, current=Depends(get_current_active_user), db=Depends(get_db)
):
    user = await db.scalar(
        select(User)
        .where(User.id == current.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if action not in ("enable", "disable"):
        raise SpandanException("VALIDATION_ERROR", "Choose enable or disable.")
    if not verify_password(request.password, user.password_hash):
        raise SpandanException("INVALID_CREDENTIALS", "Incorrect password.", 401)
    if not user.mfa_secret or (action == "disable" and not user.mfa_enabled):
        raise SpandanException("CONFLICT", "Set up an authenticator first.", 409)
    validate_mfa(user, request.code, allow_pending=action == "enable")
    user.mfa_enabled = action == "enable"
    if action == "disable":
        user.mfa_secret = None
    user.token_version += 1
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action=f"account.mfa_{action}d",
            entity_type="user",
            entity_id=str(user.id),
        )
    )
    await db.commit()
    return create_success_response("Authenticator updated. Please sign in again.")
