from app.schemas.common import ApiResponse, PaginatedResponse, ErrorDetails
from app.schemas.auth import (
    RegisterPatientRequest,
    RegisterDoctorRequest,
    RegisterAssistantRequest,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
)
from app.schemas.user import UserResponse, PatientProfileResponse, PatientProfileUpdate
from app.schemas.doctor import (
    DoctorProfileResponse,
    DoctorProfileUpdate,
    QualificationResponse,
    QualificationCreate,
    SpecializationResponse,
    SpecializationCreate,
    DoctorVerificationRequest,
)
from app.schemas.chamber import ChamberCreate, ChamberUpdate, ChamberResponse
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    QueueStateResponse,
    QueueStateUpdate,
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentStatusUpdate,
    AppointmentResponse,
    SerialTrackingResponse,
)
from app.schemas.ai import SymptomCheckRequest, SpecialistRecommendationResponse

__all__ = [
    "ApiResponse",
    "PaginatedResponse",
    "ErrorDetails",
    "RegisterPatientRequest",
    "RegisterDoctorRequest",
    "RegisterAssistantRequest",
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "ChangePasswordRequest",
    "UserResponse",
    "PatientProfileResponse",
    "PatientProfileUpdate",
    "DoctorProfileResponse",
    "DoctorProfileUpdate",
    "QualificationResponse",
    "QualificationCreate",
    "SpecializationResponse",
    "SpecializationCreate",
    "DoctorVerificationRequest",
    "ChamberCreate",
    "ChamberUpdate",
    "ChamberResponse",
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleResponse",
    "QueueStateResponse",
    "QueueStateUpdate",
    "AppointmentCreate",
    "AppointmentStatusUpdate",
    "AppointmentResponse",
    "SerialTrackingResponse",
    "SymptomCheckRequest",
    "SpecialistRecommendationResponse",
]
