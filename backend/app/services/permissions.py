from uuid import UUID

from app.core.exceptions import SpandanException
from app.models.user import User, UserRole


def require_doctor_access(user: User, doctor_id: UUID, capability: str) -> None:
    """Enforce ownership and the specific delegated permission for a staff operation."""
    if user.role == UserRole.ADMINISTRATOR:
        return
    if user.role == UserRole.DOCTOR and user.doctor_profile and user.doctor_profile.id == doctor_id:
        return
    if user.role == UserRole.ASSISTANT and any(
        assignment.doctor_id == doctor_id
        and assignment.is_active
        and getattr(assignment, capability, False)
        for assignment in user.assistant_assignments
    ):
        return
    raise SpandanException(
        code="FORBIDDEN",
        message="You do not have permission for this doctor's session.",
        status_code=403,
    )
