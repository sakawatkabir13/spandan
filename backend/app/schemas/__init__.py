from app.schemas.ai import SpecialistRecommendationResponse, SymptomCheckRequest
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusUpdate,
    SerialTrackingResponse,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterAssistantRequest,
    RegisterDoctorRequest,
    RegisterPatientRequest,
    TokenResponse,
)
from app.schemas.chamber import ChamberCreate, ChamberResponse, ChamberUpdate
from app.schemas.common import ApiResponse, ErrorDetails, PaginatedResponse
from app.schemas.doctor import (
    DoctorProfileResponse,
    DoctorProfileUpdate,
    DoctorVerificationRequest,
    QualificationCreate,
    QualificationResponse,
    SpecializationCreate,
    SpecializationResponse,
)
from app.schemas.schedule import (
    QueueStateResponse,
    QueueStateUpdate,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.schemas.user import PatientProfileResponse, PatientProfileUpdate, UserResponse

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
