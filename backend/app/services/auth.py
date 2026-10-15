import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import SpandanException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.core.time import aware
from app.models.account_session import AccountSession
from app.models.doctor import AssistantAssignment, DoctorProfile, DoctorVerificationStatus
from app.models.user import PatientProfile, User, UserRole
from app.repositories.user import user_repo
from app.schemas.auth import (
    RegisterAssistantRequest,
    RegisterDoctorRequest,
    RegisterPatientRequest,
    TokenResponse,
)
from app.services.audit import audit
from app.services.email_otp import consume_email_otp


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    async def register_patient(
        self, db: AsyncSession, request: RegisterPatientRequest
    ) -> TokenResponse:
        existing = await user_repo.get_by_email(db, request.email)
        if existing:
            raise SpandanException(
                code="CONFLICT", message="An account with this email already exists.", status_code=409
            )
        existing_phone = await user_repo.get_by_phone(db, request.phone_number)
        if existing_phone:
            raise SpandanException(
                code="CONFLICT", message="An account with this phone number already exists.", status_code=409
            )

        await consume_email_otp(db, request.email, "registration", request.email_otp)
        hashed_password = get_password_hash(request.password)
        user = User(
            email=request.email.lower(),
            phone_number=request.phone_number,
            password_hash=hashed_password,
            role=UserRole.PATIENT,
            is_active=True,
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()

        patient_profile = PatientProfile(
            user_id=user.id,
            full_name=request.full_name,
            date_of_birth=request.date_of_birth,
            gender=request.gender,
            address=request.address,
            emergency_contact=request.emergency_contact,
        )
        db.add(patient_profile)
        audit(db, user, "account.registered", user)
        await db.commit()
        loaded_user = await user_repo.get_by_id_with_profiles(db, user.id)
        return await self.create_tokens(db, loaded_user)

    async def register_doctor(
        self, db: AsyncSession, request: RegisterDoctorRequest
    ) -> TokenResponse:
        existing = await user_repo.get_by_email(db, request.email)
        if existing:
            raise SpandanException(
                code="CONFLICT", message="An account with this email already exists.", status_code=409
            )
        existing_phone = await user_repo.get_by_phone(db, request.phone_number)
        if existing_phone:
            raise SpandanException(
                code="CONFLICT", message="An account with this phone number already exists.", status_code=409
            )

        existing_registration = await db.scalar(select(DoctorProfile.id).where(
            DoctorProfile.medical_registration_number == request.medical_registration_number
        ))
        if existing_registration:
            raise SpandanException(code="CONFLICT", message="This medical registration number is already registered.", status_code=409)
        await consume_email_otp(db, request.email, "registration", request.email_otp)
        hashed_password = get_password_hash(request.password)
        user = User(
            email=request.email.lower(),
            phone_number=request.phone_number,
            password_hash=hashed_password,
            role=UserRole.DOCTOR,
            is_active=True,
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()

        doctor_profile = DoctorProfile(
            user_id=user.id,
            full_name=request.full_name,
            medical_registration_number=request.medical_registration_number,
            current_workplace=request.current_workplace,
            years_of_experience=request.years_of_experience,
            biography=request.biography,
            verification_status=DoctorVerificationStatus.PENDING,
        )
        db.add(doctor_profile)
        audit(db, user, "account.registered", user)
        await db.commit()
        loaded_user = await user_repo.get_by_id_with_profiles(db, user.id)
        return await self.create_tokens(db, loaded_user)

    async def register_assistant(
        self, db: AsyncSession, request: RegisterAssistantRequest
    ) -> TokenResponse:
        existing = await user_repo.get_by_email(db, request.email)
        if existing:
            raise SpandanException(
                code="CONFLICT", message="An account with this email already exists.", status_code=409
            )
        existing_phone = await user_repo.get_by_phone(db, request.phone_number)
        if existing_phone:
            raise SpandanException(
                code="CONFLICT", message="An account with this phone number already exists.", status_code=409
            )

        await consume_email_otp(db, request.email, "registration", request.email_otp)
        hashed_password = get_password_hash(request.password)
        user = User(
            email=request.email.lower(),
            phone_number=request.phone_number,
            password_hash=hashed_password,
            role=UserRole.ASSISTANT,
            display_name=request.full_name,
            is_active=True,
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()

        doctor = await db.get(DoctorProfile, request.doctor_id)
        if not doctor:
            raise SpandanException(code="NOT_FOUND", message="Doctor not found.", status_code=404)
        db.add(AssistantAssignment(doctor_id=request.doctor_id, assistant_user_id=user.id, is_active=True))

        audit(db, user, "account.registered", user)
        await db.commit()
        loaded_user = await user_repo.get_by_id_with_profiles(db, user.id)
        return await self.create_tokens(db, loaded_user)

    async def authenticate(
        self, db: AsyncSession, email: str, password: str, mfa_code: Optional[str] = None,
        *, ip_address=None, user_agent="",
    ) -> Optional[User]:
        user = await user_repo.get_by_email(db, email)
        if user:
            user = await db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
        if not user or not verify_password(password, user.password_hash):
            await self.audit_login_failure(db, user, "credentials", ip_address, user_agent)
            return None
        demo = await db.scalar(select(DoctorProfile.is_demo).where(DoctorProfile.user_id == user.id))
        if not user.is_active or (demo and not settings.DEMO_MODE):
            await self.audit_login_failure(db, user, "inactive_account", ip_address, user_agent)
            raise SpandanException(
                code="ACCOUNT_INACTIVE",
                message="Your account has been deactivated or suspended.",
                status_code=403,
            )
        if user.mfa_enabled:
            from app.services.account_security import validate_login_mfa
            user = await db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
            try:
                await validate_login_mfa(db, user, mfa_code)
            except SpandanException as exc:
                if exc.code != "MFA_REQUIRED":
                    await self.audit_login_failure(db, user, "authenticator", ip_address, user_agent)
                raise
        user.last_login_at = utcnow()
        from app.models.audit import AuditLog
        db.add(AuditLog(actor_user_id=user.id, action="account.login", entity_type="user", entity_id=str(user.id)))
        await db.commit()
        return await user_repo.get_by_id_with_profiles(db, user.id)

    async def audit_login_failure(self, db, user, reason, ip_address, user_agent):
        from app.models.audit import AuditLog
        db.add(AuditLog(actor_user_id=user.id if user else None, action="account.login_failed", entity_type="user", entity_id=str(user.id) if user else None, ip_address=ip_address, metadata_json={"reason": reason, "user_agent": user_agent[:250]}))
        await db.commit()

    async def create_tokens(self, db, user: User, *, session=None, ip_address=None, user_agent="") -> TokenResponse:
        if session is None:
            session = AccountSession(id=uuid4(), user_id=user.id, token_version=user.token_version, user_agent=user_agent[:250], ip_address=ip_address, expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
            db.add(session)
        access_token = create_access_token(subject=user.id, role=user.role.value, extra_claims={"ver": user.token_version, "sid": str(session.id)})
        refresh_token = create_refresh_token(subject=user.id, role=user.role.value, token_version=user.token_version, extra_claims={"sid": str(session.id), "jti": uuid4().hex})
        session.refresh_digest = hashlib.sha256(refresh_token.encode()).hexdigest()
        session.last_seen_at = utcnow()
        await db.commit()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user_id=str(user.id),
            role=user.role,
            user=user,
        )

    async def refresh_tokens(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise SpandanException(
                    code="INVALID_CREDENTIALS", message="Invalid token type.", status_code=401
                )
            user_id = UUID(payload.get("sub"))
        except (ValueError, TypeError, SpandanException) as e:
            raise SpandanException(
                code="INVALID_CREDENTIALS", message=str(e), status_code=401
            )

        await db.execute(select(User.id).where(User.id == user_id).with_for_update())
        user = await user_repo.get_by_id_with_profiles(db, user_id)
        if user and payload.get("ver", 0) != user.token_version:
            raise SpandanException(code="INVALID_CREDENTIALS", message="Session has expired. Please sign in again.", status_code=401)
        if not user or not user.is_active or (user.doctor_profile and user.doctor_profile.is_demo and not settings.DEMO_MODE):
            raise SpandanException(
                code="ACCOUNT_INACTIVE",
                message="User not found or account inactive.",
                status_code=403,
            )
        try:
            session_id = UUID(payload.get("sid", ""))
        except (ValueError, TypeError):
            raise SpandanException("INVALID_CREDENTIALS", "Please sign in again to start a secure device session.", 401)
        session = await db.scalar(select(AccountSession).where(AccountSession.id == session_id, AccountSession.user_id == user.id).with_for_update().execution_options(populate_existing=True))
        if not session or session.revoked_at or aware(session.expires_at) <= utcnow():
            raise SpandanException("INVALID_CREDENTIALS", "This device session has expired or been revoked.", 401)
        if not hmac.compare_digest(session.refresh_digest, hashlib.sha256(refresh_token.encode()).hexdigest()):
            session.revoked_at = utcnow()
            user.token_version += 1
            from app.models.audit import AuditLog
            db.add(AuditLog(actor_user_id=user.id, action="account.refresh_reuse_detected", entity_type="account_session", entity_id=str(session.id)))
            await db.commit()
            raise SpandanException("INVALID_CREDENTIALS", "A reused session token was detected. Sign in again on your devices.", 401)
        return await self.create_tokens(db, user, session=session)


auth_service = AuthService()
