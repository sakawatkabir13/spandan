from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase, declared_attr


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"
