from fastapi import APIRouter
from app.api.routes import auth, patients, doctors, chambers, schedules, appointments, ai

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(doctors.router)
api_router.include_router(chambers.router)
api_router.include_router(schedules.router)
api_router.include_router(appointments.router)
api_router.include_router(ai.router)

__all__ = ["api_router"]
