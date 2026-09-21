import argparse
import asyncio
import getpass
import os

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import or_, select

from app.core.security import get_password_hash
from app.db.session import async_session_maker
from app.models.user import User, UserRole
from app.schemas.auth import clean_and_validate_phone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the first Spandan administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--name", required=True)
    return parser.parse_args()


async def create_admin(email: str, phone: str, name: str, password: str) -> None:
    normalized_email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    normalized_phone = clean_and_validate_phone(phone)
    normalized_name = name.strip()
    if len(normalized_name) < 2 or len(normalized_name) > 100:
        raise ValueError("Name must contain between 2 and 100 characters")
    if len(password) < 12:
        raise ValueError("Administrator password must contain at least 12 characters")

    async with async_session_maker() as db:
        existing = await db.scalar(
            select(User).where(
                or_(User.email == normalized_email, User.phone_number == normalized_phone)
            )
        )
        if existing:
            raise ValueError("An account already uses this email address or phone number")

        db.add(
            User(
                email=normalized_email,
                phone_number=normalized_phone,
                display_name=normalized_name,
                password_hash=get_password_hash(password),
                role=UserRole.ADMINISTRATOR,
                is_active=True,
                is_email_verified=True,
                is_phone_verified=True,
            )
        )
        await db.commit()
    print(f"Administrator created: {normalized_email}")


def main() -> None:
    args = parse_args()
    password = os.environ.get("SPANDAN_ADMIN_PASSWORD") or getpass.getpass(
        "Administrator password: "
    )
    asyncio.run(create_admin(args.email, args.phone, args.name, password))


if __name__ == "__main__":
    main()
