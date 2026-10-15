import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.api.dependencies.auth import get_current_active_user, get_token_from_header
from app.core.exceptions import SpandanException, create_success_response
from app.core.security import decode_token, verify_password
from app.db.session import get_db
from app.models.account_session import AccountSession, MFARecoveryCode
from app.models.audit import AuditLog
from app.models.user import User
from app.services.account_security import validate_login_mfa

router = APIRouter(prefix="/auth", tags=["Account devices & recovery"])


@router.get("/sessions")
async def sessions(user=Depends(get_current_active_user), token=Depends(get_token_from_header), db=Depends(get_db)):
    current_id = decode_token(token).get("sid")
    rows = await db.scalars(select(AccountSession).where(AccountSession.user_id == user.id, AccountSession.revoked_at.is_(None), AccountSession.expires_at > datetime.now(timezone.utc), AccountSession.token_version == user.token_version).order_by(AccountSession.last_seen_at.desc()).limit(50))
    return create_success_response("Active devices.", [{"id": str(row.id), "current": str(row.id) == current_id, "user_agent": row.user_agent, "ip_address": row.ip_address, "created_at": row.created_at, "last_seen_at": row.last_seen_at} for row in rows])


@router.delete("/sessions/{id}")
async def revoke_session(id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    row = await db.scalar(select(AccountSession).where(AccountSession.id == id, AccountSession.user_id == user.id).with_for_update())
    if not row:
        raise SpandanException("NOT_FOUND", "Device session not found.", 404)
    row.revoked_at = datetime.now(timezone.utc)
    db.add(AuditLog(actor_user_id=user.id, action="account.session_revoked", entity_type="account_session", entity_id=str(id)))
    await db.commit()
    return create_success_response("Device signed out.")


@router.get("/login-activity")
async def login_activity(limit: int = Query(20, ge=1, le=100), user=Depends(get_current_active_user), db=Depends(get_db)):
    rows = await db.scalars(select(AuditLog).where(AuditLog.actor_user_id == user.id, AuditLog.action.in_(["account.login", "account.login_failed", "account.refresh_reuse_detected", "account.recovery_code_used"])).order_by(AuditLog.created_at.desc()).limit(limit))
    return create_success_response("Recent sign-in activity.", [{"id": str(row.id), "action": row.action, "ip_address": row.ip_address, "created_at": row.created_at, "user_agent": (row.metadata_json or {}).get("user_agent", "")} for row in rows])


class RecoveryBody(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=6, max_length=30)


@router.post("/mfa/recovery-codes")
async def recovery_codes(request: RecoveryBody, current=Depends(get_current_active_user), db=Depends(get_db)):
    user = await db.scalar(select(User).where(User.id == current.id).with_for_update().execution_options(populate_existing=True))
    if not user.mfa_enabled:
        raise SpandanException("CONFLICT", "Enable your authenticator before creating recovery codes.", 409)
    if not verify_password(request.password, user.password_hash):
        raise SpandanException("INVALID_CREDENTIALS", "Incorrect password.", 401)
    await validate_login_mfa(db, user, request.code)
    await db.execute(delete(MFARecoveryCode).where(MFARecoveryCode.user_id == user.id))
    codes = [secrets.token_hex(8) for _ in range(10)]
    for code in codes:
        db.add(MFARecoveryCode(user_id=user.id, digest=hashlib.sha256(f"{user.id}:{code}".encode()).hexdigest()))
    db.add(AuditLog(actor_user_id=user.id, action="account.recovery_codes_generated", entity_type="user", entity_id=str(user.id)))
    await db.commit()
    return create_success_response("Save these codes privately. Each works once. Previous codes are now invalid.", {"codes": ["-".join(code[i:i + 4] for i in range(0, 16, 4)) for code in codes]})
