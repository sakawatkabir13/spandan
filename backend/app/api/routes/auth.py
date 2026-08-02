from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user
from app.core.exceptions import create_success_response, SpandanException
from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterAssistantRequest,
    RegisterDoctorRequest,
    RegisterPatientRequest,
    TokenResponse,
)
from app.schemas.common import ApiResponse
from app.schemas.user import UserResponse
from app.services.auth import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register/patient", response_model=ApiResponse[TokenResponse], status_code=status.HTTP_201_CREATED)
async def register_patient(
    request: RegisterPatientRequest, db: AsyncSession = Depends(get_db)
):
    tokens = await auth_service.register_patient(db, request)
    return create_success_response(message="Patient registered successfully.", data=tokens)


@router.post("/register/doctor", response_model=ApiResponse[TokenResponse], status_code=status.HTTP_201_CREATED)
async def register_doctor(
    request: RegisterDoctorRequest, db: AsyncSession = Depends(get_db)
):
    tokens = await auth_service.register_doctor(db, request)
    return create_success_response(
        message="Doctor registered successfully. Profile is pending administrator verification.",
        data=tokens,
    )


@router.post("/register/assistant", response_model=ApiResponse[TokenResponse], status_code=status.HTTP_201_CREATED)
async def register_assistant(
    request: RegisterAssistantRequest, db: AsyncSession = Depends(get_db)
):
    tokens = await auth_service.register_assistant(db, request)
    return create_success_response(message="Assistant registered successfully.", data=tokens)


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate(db, request.email, request.password)
    if not user:
        raise SpandanException(
            code="INVALID_CREDENTIALS",
            message="Incorrect email or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    tokens = auth_service.create_tokens(user)
    return create_success_response(message="Login successful.", data=tokens)


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.refresh_tokens(db, request.refresh_token)
    return create_success_response(message="Tokens refreshed successfully.", data=tokens)


@router.post("/logout", response_model=ApiResponse[None])
async def logout(current_user: User = Depends(get_current_active_user)):
    # In stateless JWT, client deletes tokens. If token blacklist DB is needed, we record JTI.
    return create_success_response(message="Logged out successfully.")


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_me(current_user: User = Depends(get_current_active_user)):
    return create_success_response(message="Current user fetched successfully.", data=current_user)


@router.post("/change-password", response_model=ApiResponse[None])
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(request.current_password, current_user.password_hash):
        raise SpandanException(
            code="INVALID_CREDENTIALS",
            message="Current password is incorrect.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    current_user.password_hash = get_password_hash(request.new_password)
    await db.commit()
    return create_success_response(message="Password updated successfully.")
