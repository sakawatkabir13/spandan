from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends, Header, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SpandanException
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user import user_repo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_token_from_header(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    if token:
        return token
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ")[1]
    raise SpandanException(
        code="INVALID_CREDENTIALS",
        message="Missing authentication token.",
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


async def get_current_user(
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise SpandanException(
                code="INVALID_CREDENTIALS",
                message="Invalid token type provided.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise SpandanException(
                code="INVALID_CREDENTIALS",
                message="Token payload invalid.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        user_id = UUID(user_id_str)
    except Exception as e:
        if isinstance(e, SpandanException):
            raise
        raise SpandanException(
            code="INVALID_CREDENTIALS",
            message=f"Authentication error: {str(e)}",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = await user_repo.get_by_id_with_profiles(db, user_id)
    if not user:
        raise SpandanException(
            code="INVALID_CREDENTIALS",
            message="User associated with token no longer exists.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if payload.get("ver", 0) != user.token_version:
        raise SpandanException(code="INVALID_CREDENTIALS", message="Session has expired. Please sign in again.", status_code=401)
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise SpandanException(
            code="ACCOUNT_INACTIVE",
            message="Your account has been deactivated or suspended.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return current_user


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    user = await get_current_user(token, db)
    return await get_current_active_user(user)


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise SpandanException(
                code="FORBIDDEN",
                message=f"Access denied. Required role(s): {[r.value for r in allowed_roles]}.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return current_user

    return role_checker
