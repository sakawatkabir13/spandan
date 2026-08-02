from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SpandanException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User, UserRole, PatientProfile
from app.models.doctor import DoctorProfile, DoctorVerificationStatus, AssistantAssignment
from app.repositories.user import user_repo, patient_repo
from app.schemas.auth import (
    RegisterAssistantRequest,
    RegisterDoctorRequest,
    RegisterPatientRequest,
    TokenResponse,
)


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

        hashed_password = get_password_hash(request.password)
        user = User(
            email=request.email.lower(),
            phone_number=request.phone_number,
            password_hash=hashed_password,
            role=UserRole.PATIENT,
            is_active=True,
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
        await db.commit()
        loaded_user = await user_repo.get_by_id_with_profiles(db, user.id)
        return self.create_tokens(loaded_user)

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

        hashed_password = get_password_hash(request.password)
        user = User(
            email=request.email.lower(),
            phone_number=request.phone_number,
            password_hash=hashed_password,
            role=UserRole.DOCTOR,
            is_active=True,
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
        await db.commit()
        loaded_user = await user_repo.get_by_id_with_profiles(db, user.id)
        return self.create_tokens(loaded_user)

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

        hashed_password = get_password_hash(request.password)
        user = User(
            email=request.email.lower(),
            phone_number=request.phone_number,
            password_hash=hashed_password,
            role=UserRole.ASSISTANT,
            is_active=True,
        )
        db.add(user)
        await db.flush()

        if request.doctor_id:
            try:
                doc_id_uuid = UUID(request.doctor_id)
                assignment = AssistantAssignment(
                    doctor_id=doc_id_uuid,
                    assistant_user_id=user.id,
                    is_active=True,
                )
                db.add(assignment)
            except ValueError:
                pass

        await db.commit()
        loaded_user = await user_repo.get_by_id_with_profiles(db, user.id)
        return self.create_tokens(loaded_user)

    async def authenticate(
        self, db: AsyncSession, email: str, password: str
    ) -> Optional[User]:
        user = await user_repo.get_by_email(db, email)
        if not user or not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            raise SpandanException(
                code="ACCOUNT_INACTIVE",
                message="Your account has been deactivated or suspended.",
                status_code=403,
            )
        user.last_login_at = utcnow()
        await db.commit()
        return await user_repo.get_by_id_with_profiles(db, user.id)

    def create_tokens(self, user: User) -> TokenResponse:
        access_token = create_access_token(subject=user.id, role=user.role.value)
        refresh_token = create_refresh_token(subject=user.id, role=user.role.value)
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

        user = await user_repo.get_by_id_with_profiles(db, user_id)
        if not user or not user.is_active:
            raise SpandanException(
                code="ACCOUNT_INACTIVE",
                message="User not found or account inactive.",
                status_code=403,
            )
        return self.create_tokens(user)


auth_service = AuthService()
