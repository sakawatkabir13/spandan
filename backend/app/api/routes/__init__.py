from fastapi import APIRouter

from app.api.routes import (
    account_sessions,
    ai,
    appointments,
    assistants,
    auth,
    care,
    chambers,
    chat,
    chat_internal,
    directory,
    doctors,
    events,
    medical,
    operations,
    patients,
    payments,
    schedules,
    security,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(chat.router)
api_router.include_router(chat_internal.router)
api_router.include_router(auth.router)
api_router.include_router(account_sessions.router)
api_router.include_router(patients.router)
api_router.include_router(medical.router)
api_router.include_router(care.router)
api_router.include_router(doctors.router)
api_router.include_router(chambers.router)
api_router.include_router(schedules.router)
api_router.include_router(appointments.router)
api_router.include_router(ai.router)

__all__ = ["api_router"]

api_router.include_router(users.router)
api_router.include_router(security.router)
api_router.include_router(operations.router)
api_router.include_router(payments.router)
api_router.include_router(events.router)
api_router.include_router(assistants.router)

api_router.include_router(directory.router)
