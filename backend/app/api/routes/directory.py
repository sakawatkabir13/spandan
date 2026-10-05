from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.api.dependencies.auth import require_roles
from app.core.exceptions import SpandanException, create_success_response
from app.db.session import get_db
from app.models.directory import DirectoryDoctor
from app.models.user import UserRole
from app.schemas.directory import DirectoryDoctorResponse, DirectoryVisibilityRequest
from app.services.audit import audit

router = APIRouter(prefix="/directory", tags=["Public doctor directory"])


def public(row):
    return DirectoryDoctorResponse.model_validate(row).model_dump(mode="json")


@router.get("/doctors")
async def search_directory(
    query: str = Query("", max_length=100),
    district: str = Query("", max_length=80),
    division: str = Query("", max_length=50),
    specialty: str = Query("", max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    filters = [DirectoryDoctor.is_active.is_(True)]
    if query.strip():
        term = (
            "%" + query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        filters.append(
            or_(
                *(
                    field.ilike(term, escape="\\")
                    for field in (
                        DirectoryDoctor.full_name,
                        DirectoryDoctor.native_name,
                        DirectoryDoctor.specialty,
                        DirectoryDoctor.institution,
                        DirectoryDoctor.qualifications,
                    )
                )
            )
        )
    for value, field in (
        (district, DirectoryDoctor.district),
        (division, DirectoryDoctor.division),
        (specialty, DirectoryDoctor.specialty),
    ):
        if value.strip():
            filters.append(func.lower(field) == value.strip().lower())
    total = await db.scalar(select(func.count()).select_from(DirectoryDoctor).where(*filters))
    rows = await db.scalars(
        select(DirectoryDoctor)
        .where(*filters)
        .order_by(DirectoryDoctor.full_name, DirectoryDoctor.id)
        .offset(skip)
        .limit(limit)
    )
    return create_success_response(
        "Public hospital listings. Confirm availability directly with the hospital.",
        {
            "items": [public(row) for row in rows],
            "total": total,
            "skip": skip,
            "limit": limit,
        },
    )


@router.get("/filters")
async def directory_filters(db=Depends(get_db)):
    result = {}
    for name, field in (
        ("divisions", DirectoryDoctor.division),
        ("districts", DirectoryDoctor.district),
        ("specialties", DirectoryDoctor.specialty),
    ):
        result[name] = list(
            await db.scalars(
                select(field).where(DirectoryDoctor.is_active.is_(True)).distinct().order_by(field)
            )
        )
    return create_success_response("Directory filters.", result)


@router.get("/admin/doctors")
async def admin_directory(user=Depends(require_roles(UserRole.ADMINISTRATOR)), db=Depends(get_db)):
    rows = await db.scalars(select(DirectoryDoctor).order_by(DirectoryDoctor.full_name).limit(500))
    return create_success_response("Directory moderation.", [public(row) for row in rows])


@router.patch("/admin/doctors/{id}")
async def moderate_listing(
    id: UUID,
    request: DirectoryVisibilityRequest,
    user=Depends(require_roles(UserRole.ADMINISTRATOR)),
    db=Depends(get_db),
):
    row = await db.scalar(select(DirectoryDoctor).where(DirectoryDoctor.id == id).with_for_update())
    if not row:
        raise SpandanException("NOT_FOUND", "Directory listing not found.", 404)
    row.is_active = request.is_active
    audit(db, user, "directory.visibility_changed", row, ["is_active"])
    await db.commit()
    return create_success_response("Directory visibility updated.", public(row))


@router.get("/doctors/{id}")
async def directory_detail(id: UUID, db=Depends(get_db)):
    row = await db.get(DirectoryDoctor, id)
    if not row or not row.is_active:
        raise SpandanException("NOT_FOUND", "Directory listing not found.", 404)
    return create_success_response(
        "Public hospital listing, not a confirmed Spandan booking.", public(row)
    )
