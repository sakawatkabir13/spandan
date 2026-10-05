from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.api.dependencies.auth import require_roles
from app.core.config import settings
from app.core.exceptions import SpandanException, create_success_response
from app.db.session import get_db
from app.models.directory import DirectoryDoctor
from app.models.doctor import DoctorProfile, DoctorVerificationStatus, Specialization
from app.models.user import User, UserRole
from app.schemas.directory import DirectoryDoctorResponse, DirectoryVisibilityRequest
from app.services.audit import audit
from app.services.specialty_taxonomy import BENGALI, canonical_specialty, department_names

router = APIRouter(prefix="/directory", tags=["Public doctor directory"])


def public(row, eligible=()):
    response = DirectoryDoctorResponse.model_validate(row)
    if not settings.DEMO_MODE or response.demo_doctor_id not in eligible:
        response.demo_doctor_id = None
    elif response.demo_doctor_id:
        response.booking_status = "demo_only"
    return response.model_dump(mode="json")


async def public_rows(db, rows):
    rows = list(rows)
    ids = [row.demo_doctor_id for row in rows if row.demo_doctor_id]
    eligible = (
        set(
            await db.scalars(
                select(DoctorProfile.id)
                .join(User, User.id == DoctorProfile.user_id)
                .where(
                    DoctorProfile.id.in_(ids),
                    DoctorProfile.is_demo.is_(True),
                    DoctorProfile.verification_status == DoctorVerificationStatus.APPROVED,
                    User.is_active.is_(True),
                )
            )
        )
        if settings.DEMO_MODE and ids
        else set()
    )
    return [public(row, eligible) for row in rows]


@router.get("/doctors")
async def search_directory(
    query: str = Query("", max_length=100),
    district: str = Query("", max_length=80),
    division: str = Query("", max_length=50),
    specialty: str = Query("", max_length=100),
    specialization_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    filters = [DirectoryDoctor.is_active.is_(True)]
    if query.strip():
        term = (
            "%" + query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        matching = (
            [func.lower(DirectoryDoctor.specialty).in_(department_names(BENGALI[query.strip()]))]
            if query.strip() in BENGALI
            else []
        )
        filters.append(
            or_(
                *matching,
                *(
                    field.ilike(term, escape="\\")
                    for field in (
                        DirectoryDoctor.full_name,
                        DirectoryDoctor.native_name,
                        DirectoryDoctor.specialty,
                        DirectoryDoctor.institution,
                        DirectoryDoctor.qualifications,
                    )
                ),
            )
        )
    for value, field in (
        (district, DirectoryDoctor.district),
        (division, DirectoryDoctor.division),
    ):
        if value.strip():
            filters.append(func.lower(field) == value.strip().lower())
    if specialization_id:
        category = await db.get(Specialization, specialization_id)
        if not category:
            raise SpandanException("NOT_FOUND", "Specialty not found.", 404)
        specialty = category.name
    if specialty.strip():
        filters.append(func.lower(DirectoryDoctor.specialty).in_(department_names(specialty)))
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
            "items": await public_rows(db, rows),
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
    result["specialties"] = sorted({canonical_specialty(value) for value in result["specialties"]})
    return create_success_response("Directory filters.", result)


@router.get("/admin/doctors")
async def admin_directory(user=Depends(require_roles(UserRole.ADMINISTRATOR)), db=Depends(get_db)):
    rows = await db.scalars(select(DirectoryDoctor).order_by(DirectoryDoctor.full_name).limit(500))
    return create_success_response("Directory moderation.", await public_rows(db, rows))


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
    return create_success_response(
        "Directory visibility updated.", (await public_rows(db, [row]))[0]
    )


@router.get("/doctors/{id}")
async def directory_detail(id: UUID, db=Depends(get_db)):
    row = await db.get(DirectoryDoctor, id)
    if not row or not row.is_active:
        raise SpandanException("NOT_FOUND", "Directory listing not found.", 404)
    return create_success_response(
        "Public hospital listing, not a confirmed Spandan booking.",
        (await public_rows(db, [row]))[0],
    )
