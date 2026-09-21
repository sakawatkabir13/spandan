from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


def local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE))


def session_time(schedule, clock_time) -> datetime:
    return datetime.combine(schedule.schedule_date, clock_time, ZoneInfo(settings.APP_TIMEZONE))


def aware(value: datetime) -> datetime:
    # SQLite strips offsets from timestamps; persisted timestamps are UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
