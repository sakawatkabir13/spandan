import asyncio
import sys

from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.user import User, UserRole
from app.services.notifications import notify


async def run(message):
    async with async_session_maker() as db:
        for user in await db.scalars(
            select(User).where(User.role == UserRole.ADMINISTRATOR, User.is_active.is_(True))
        ):
            await notify(db, user, "Operational alert", message[:2000])
        await db.commit()


if __name__ == "__main__":
    asyncio.run(run(sys.stdin.read()))
