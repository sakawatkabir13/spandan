import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.chamber import Chamber
from app.models.directory import DirectoryDoctor
from app.models.doctor import DoctorProfile
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.directory import DIVISIONS, DirectoryImportRow
from scripts.import_directory import import_rows, load_dataset
from tests.test_workflows import admin, register


@pytest.mark.asyncio
async def test_directory_import_is_idempotent_and_not_booking_inventory(client, db_session):
    rows = load_dataset()
    assert {row.division for row in rows} == DIVISIONS
    assert len(rows) == 22
    assert (await import_rows(db_session, rows))["added"] == 22
    await db_session.commit()
    assert await import_rows(db_session, rows) == {"added": 0, "updated": 0, "unchanged": 22}
    await db_session.commit()
    for model in (User, DoctorProfile, Chamber, Schedule):
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0
    page = (await client.get("/api/v1/directory/doctors?limit=12")).json()["data"]
    assert page["total"] == 22 and len(page["items"]) == 12
    second = (await client.get("/api/v1/directory/doctors?skip=12&limit=12")).json()["data"]
    assert len(second["items"]) == 10
    assert not {r["id"] for r in page["items"]} & {r["id"] for r in second["items"]}
    assert page["items"][0]["booking_status"] == "contact_hospital"
    assert "medical_registration_number" not in page["items"][0]
    assert (await client.get("/api/v1/doctors")).json()["data"] == []
    id = page["items"][0]["id"]
    assert (await client.get(f"/api/v1/doctors/{id}")).status_code == 404
    assert (
        (await client.get(f"/api/v1/directory/doctors/{id}"))
        .json()["data"]["source_url"]
        .startswith("https://")
    )
    for division in DIVISIONS:
        found = (
            await client.get("/api/v1/directory/doctors", params={"division": division.lower()})
        ).json()["data"]
        assert found["total"] >= 2
        assert all(r["division"] == division for r in found["items"])
    filtered = (await client.get("/api/v1/directory/doctors", params={"query": "আফরোজা"})).json()[
        "data"
    ]
    assert filtered["total"] == 1
    assert (await client.get("/api/v1/directory/doctors", params={"query": "%"})).json()["data"][
        "total"
    ] == 0
    assert (
        await client.get(
            "/api/v1/directory/doctors", params={"specialty": "Urology", "district": "Barishal"}
        )
    ).json()["data"]["total"] == 1
    assert (await client.get("/api/v1/directory/doctors?limit=1000")).status_code == 422
    assert (
        set((await client.get("/api/v1/directory/filters")).json()["data"]["divisions"])
        == DIVISIONS
    )


@pytest.mark.asyncio
async def test_admin_moderation_is_audited_and_survives_reimport(client, db_session):
    rows = load_dataset()
    await import_rows(db_session, rows)
    await db_session.commit()
    listing = await db_session.scalar(
        select(DirectoryDoctor).where(DirectoryDoctor.listing_key == rows[0].listing_key)
    )
    path = f"/api/v1/directory/admin/doctors/{listing.id}"
    assert (await client.patch(path, json={"is_active": False})).status_code == 401
    patient, _ = await register(client, "patient", "directory-reader")
    assert (await client.get("/api/v1/directory/admin/doctors", headers=patient)).status_code == 403
    assert (await client.patch(path, headers=patient, json={"is_active": False})).status_code == 403
    headers = await admin(client, db_session)
    assert (
        len((await client.get("/api/v1/directory/admin/doctors", headers=headers)).json()["data"])
        == 22
    )
    response = await client.patch(path, headers=headers, json={"is_active": False})
    assert response.status_code == 200
    assert not response.json()["data"]["is_active"]
    assert (await client.get(f"/api/v1/directory/doctors/{listing.id}")).status_code == 404
    assert (await client.get("/api/v1/directory/doctors")).json()["data"]["total"] == 21
    assert await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "directory.visibility_changed")
    )
    rows[0].qualifications = "MBBS, FCPS (Internal Medicine), MD (Cardiology); reviewed"
    assert (await import_rows(db_session, rows))["updated"] == 1
    await db_session.commit()
    await db_session.refresh(listing)
    assert not listing.is_active
    assert (await client.patch(path, headers=headers, json={"is_active": True})).status_code == 200
    assert (await client.get(f"/api/v1/directory/doctors/{listing.id}")).status_code == 200


def test_import_rejects_unsafe_sources_and_account_fields():
    row = load_dataset()[0].model_dump()
    for url in (
        "javascript:alert(1)",
        "https://www.evercarebd.com.attacker.example/a",
        "https://user:pass@www.evercarebd.com/a",
        "http://www.evercarebd.com/a",
    ):
        with pytest.raises(ValidationError):
            DirectoryImportRow.model_validate({**row, "source_url": url})
    with pytest.raises(ValidationError):
        DirectoryImportRow.model_validate({**row, "verification_status": "approved"})
