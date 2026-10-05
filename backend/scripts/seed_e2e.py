"""Synthetic browser-test administrator. Refuses production databases."""

import asyncio

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import async_session_maker
from app.models.user import User, UserRole


async def main():
    if settings.APP_ENV == "production" or not (
        make_url(settings.DATABASE_URL).database or ""
    ).startswith("spandan_test"):
        raise RuntimeError("Browser fixtures require a spandan_test database outside production")
    async with async_session_maker() as db:
        if not await db.scalar(select(User.id).where(User.email == "e2e-admin@example.com")):
            db.add(
                User(
                    email="e2e-admin@example.com",
                    password_hash=get_password_hash("E2EAdminPassword123!"),
                    role=UserRole.ADMINISTRATOR,
                    is_active=True,
                )
            )
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
