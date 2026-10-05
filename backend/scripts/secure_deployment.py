"""One-time private admin bootstrap and revocation of unchanged demo credentials."""

import asyncio
import json
import os
import secrets
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.db.session import async_session_maker
from app.models.audit import AuditLog
from app.models.user import User, UserRole

DEMO_EMAILS = (
    "admin@spandan.com.bd",
    "dr.rahman@spandan.com.bd",
    "dr.farhana@spandan.com.bd",
    "dr.tariq@spandan.com.bd",
    "assistant.karim@spandan.com.bd",
    "assistant.nasrin@spandan.com.bd",
    "patient.jamal@gmail.com",
    "patient.sadia@gmail.com",
)


async def main():
    os.umask(0o077)
    path = Path(
        os.environ.get("ADMIN_CREDENTIALS_FILE", "/app/uploads/.private/admin-credentials.json")
    )
    # Refuse paths under public uploads; the operator must mount a private directory.
    if Path(settings.UPLOAD_DIR).resolve() in path.resolve().parents:
        raise RuntimeError("Administrator credentials must be stored outside public uploads")
    async with async_session_maker() as db:
        admin = await db.scalar(
            select(User).where(User.email == settings.OPERATOR_EMAIL).with_for_update()
        )
        if admin and (admin.role != UserRole.ADMINISTRATOR or not admin.is_active):
            raise RuntimeError(
                "Operator email already belongs to a non-administrator or inactive account"
            )
        if not admin:
            password = secrets.token_urlsafe(32)
            admin = User(
                email=settings.OPERATOR_EMAIL,
                password_hash=get_password_hash(password),
                role=UserRole.ADMINISTRATOR,
                display_name="Spandan operator",
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open("x") as file:
                json.dump(
                    {
                        "email": admin.email,
                        "password": password,
                        "next_step": "Sign in, change password, and enable an authenticator from Account & Chamber Tools.",
                    },
                    file,
                )
            path.chmod(0o600)
        disabled = 0
        for demo in await db.scalars(
            select(User).where(User.email.in_(DEMO_EMAILS)).with_for_update()
        ):
            if verify_password("Password123!", demo.password_hash):
                demo.password_hash = get_password_hash(secrets.token_urlsafe(32))
                demo.is_active = False
                demo.token_version += 1
                disabled += 1
                db.add(
                    AuditLog(
                        actor_user_id=admin.id,
                        action="account.demo_disabled",
                        entity_type="user",
                        entity_id=str(demo.id),
                    )
                )
        await db.commit()
        print(
            json.dumps(
                {
                    "private_admin_ready": True,
                    "unchanged_demo_accounts_disabled": disabled,
                    "credentials_file": str(path),
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
