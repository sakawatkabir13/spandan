import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.exceptions import SpandanException
from app.db.session import async_session_maker
from app.models.chamber import Chamber
from app.models.doctor import DoctorProfile, DoctorVerificationStatus
from app.models.schedule import QueueState, Schedule, ScheduleStatus
from app.models.user import User

router = APIRouter(prefix="/events", tags=["Live queue events"])


@router.get("/queue/{schedule_id}")
async def queue_events(schedule_id: UUID, request: Request):
    async with async_session_maker() as db:
        schedule = await db.get(Schedule, schedule_id)
        if not schedule:
            raise SpandanException("NOT_FOUND", "Session not found.", 404)
        doctor = await db.get(DoctorProfile, schedule.doctor_id)
        owner = await db.get(User, doctor.user_id)
        chamber = await db.get(Chamber, schedule.chamber_id)
        if (
            doctor.verification_status != DoctorVerificationStatus.APPROVED
            or not owner.is_active
            or not chamber.is_active
            or schedule.status == ScheduleStatus.DRAFT
        ):
            raise SpandanException("NOT_FOUND", "Session not found.", 404)

    async def stream():
        previous = None
        # Release each DB connection before waiting; no client holds a pool slot.
        for tick in range(150):
            if await request.is_disconnected():
                return
            async with async_session_maker() as db:
                queue = await db.scalar(
                    select(QueueState).where(QueueState.schedule_id == schedule_id)
                )
                if not queue:
                    return
                payload = json.dumps(
                    {
                        "schedule_id": str(schedule_id),
                        "current_serial": queue.current_serial,
                        "delay_minutes": queue.delay_minutes,
                        "status_message": queue.status_message,
                        "updated_at": queue.updated_at.isoformat(),
                    }
                )
            if payload != previous:
                yield f"event: queue\ndata: {payload}\n\n"
                previous = payload
            elif tick % 5 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
        },
    )
