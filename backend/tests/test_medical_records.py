from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.time import local_now
from app.models.audit import AuditLog
from app.models.medical import MedicalHistory, MedicalReport
from app.services import medical_records as storage
from app.services.public_uploads import PublicUploads
from tests.test_operations import book
from tests.test_workflows import admin, register, session

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def private_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


async def upload(client, headers, **fields):
    return await client.post("/api/v1/medical-records/me/reports", headers=headers, data={"title": "Blood test", "report_type": "lab", **fields}, files={"file": ("blood-test.pdf", PDF, "application/pdf")})


async def test_report_encryption_sharing_ownership_and_revocation(client, db_session, private_storage):
    doctor, _, schedule, _ = await session(client, db_session)
    patient, _ = await register(client, "patient", "medical")
    stranger, _ = await register(client, "patient", "outsider")
    other_doctor, _ = await register(client, "doctor", "unrelated")
    appointment = await book(client, patient, schedule)
    response = await upload(client, patient, notes="For my appointment")
    assert response.status_code == 201, response.text
    report = response.json()["data"]
    assert "storage_key" not in report and "patient_id" not in report
    row = await db_session.get(MedicalReport, UUID(report["id"]))
    encrypted = (private_storage / ".medical" / row.storage_key).read_bytes()
    assert PDF not in encrypted and encrypted != PDF
    own_url = f"/api/v1/medical-records/me/reports/{report['id']}/download"
    downloaded = await client.get(own_url, headers=patient)
    assert downloaded.content == PDF
    assert downloaded.headers["cache-control"] == "no-store, private"
    assert (await client.get(own_url, headers=stranger)).status_code == 404
    assert (await client.get(own_url)).status_code == 401
    records_url = f"/api/v1/medical-records/appointments/{appointment['id']}"
    assert (await client.get(records_url, headers=other_doctor)).status_code == 404
    assert (await client.get(records_url, headers=stranger)).status_code == 403
    assert not (await client.get(records_url, headers=doctor)).json()["data"]["shared"]
    history = {"allergies": "Penicillin", "medications": "None", "history_reviewed": True, "share_with_doctors": True}
    assert (await client.patch("/api/v1/medical-records/me/history", headers=patient, json=history)).status_code == 200
    shared = (await client.get(records_url, headers=doctor)).json()["data"]
    assert shared["shared"] and shared["history"]["allergies"] == "Penicillin"
    assert len(shared["reports"]) == 1
    doctor_download = records_url + f"/reports/{report['id']}/download"
    assert (await client.get(doctor_download, headers=doctor)).content == PDF
    assert (await client.get(records_url + f"/reports/{uuid4()}/download", headers=doctor)).status_code == 404
    admin_headers = await admin(client, db_session)
    assert (await client.get(records_url, headers=admin_headers)).status_code == 403
    public_doctor = (await client.get(f"/api/v1/doctors/{schedule['doctor_id']}")).text
    assert "Penicillin" not in public_doctor and "medical_histories" not in public_doctor
    history["share_with_doctors"] = False
    await client.patch("/api/v1/medical-records/me/history", headers=patient, json=history)
    assert (await client.get(doctor_download, headers=doctor)).status_code == 403
    await client.patch("/api/v1/medical-records/me/history", headers=patient, json={**history, "share_with_doctors": True})
    await client.patch(f"/api/v1/appointments/{appointment['id']}/status", headers=patient, json={"appointment_status": "cancelled"})
    assert (await client.get(doctor_download, headers=doctor)).status_code == 403
    assert (await client.delete(f"/api/v1/medical-records/me/reports/{report['id']}", headers=stranger)).status_code == 404
    assert (await client.delete(f"/api/v1/medical-records/me/reports/{report['id']}", headers=patient)).status_code == 200
    assert not (private_storage / ".medical" / row.storage_key).exists()
    assert (await client.get(own_url, headers=patient)).status_code == 404
    assert await db_session.scalar(select(AuditLog.id).where(AuditLog.action == "medical.records_viewed"))


async def test_family_booking_does_not_expose_account_holder_history(client, db_session):
    doctor, _, schedule, _ = await session(client, db_session)
    patient, _ = await register(client, "patient", "parent")
    dependent = (await client.post("/api/v1/dependents", headers=patient, json={"full_name": "Child", "relationship_name": "Child"})).json()["data"]
    await client.patch("/api/v1/medical-records/me/history", headers=patient, json={"allergies": "Private parent history", "share_with_doctors": True})
    report = (await upload(client, patient)).json()["data"]
    appointment = await book(client, patient, schedule, dependent_id=dependent["id"])
    base = f"/api/v1/medical-records/appointments/{appointment['id']}"
    response = await client.get(base, headers=doctor)
    assert response.json()["data"]["dependent_booking"]
    assert "Private parent history" not in response.text
    assert (await client.get(base + f"/reports/{report['id']}/download", headers=doctor)).status_code == 403


async def test_report_validation_quotas_and_profile_dates(client, monkeypatch):
    patient, _ = await register(client, "patient", "limits")
    future = str(local_now().date() + timedelta(days=1))
    assert (await upload(client, patient, report_date=future)).status_code == 400
    assert (await upload(client, patient, title="  ")).status_code == 400
    bad = await client.post("/api/v1/medical-records/me/reports", headers=patient, data={"title": "Bad file"}, files={"file": ("fake.pdf", b"<script>alert(1)</script>", "application/pdf")})
    assert bad.status_code == 400
    spoofed = await client.post("/api/v1/medical-records/me/reports", headers=patient, data={"title": "Wrong content"}, files={"file": ("fake.png", PDF, "image/png")})
    assert spoofed.status_code == 400
    monkeypatch.setattr(storage, "MAX_REPORT_BYTES", 20)
    assert (await upload(client, patient)).status_code == 413
    monkeypatch.setattr(storage, "MAX_REPORT_BYTES", 5 * 1024 * 1024)
    monkeypatch.setattr(storage, "MAX_REPORTS", 1)
    assert (await upload(client, patient)).status_code == 201
    assert (await upload(client, patient)).status_code == 409
    assert (await client.patch("/api/v1/patients/me", headers=patient, json={"date_of_birth": future})).status_code == 422
    assert (await client.patch("/api/v1/medical-records/me/history", headers=patient, json={"blood_group": "INVALID"})).status_code == 422


async def test_private_upload_paths_are_never_public(private_storage):
    folder = private_storage / ".medical"
    folder.mkdir()
    (folder / "known-file").write_bytes(b"private encrypted file")
    (private_storage / "public.txt").write_text("public photo stand-in")
    app = FastAPI()
    app.mount("/uploads", PublicUploads(directory=private_storage))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/uploads/public.txt")).status_code == 200
        for path in ("/uploads/.medical/known-file", "/uploads/%2emedical/known-file", "/uploads/.medical%2fknown-file"):
            assert (await client.get(path)).status_code == 404


async def test_medical_data_export_and_anonymization(client, db_session, private_storage):
    patient, user = await register(client, "patient", "privacy-medical")
    await client.patch("/api/v1/medical-records/me/history", headers=patient, json={"conditions": "Private history", "history_reviewed": True})
    response = await upload(client, patient)
    report = await db_session.get(MedicalReport, UUID(response.json()["data"]["id"]))
    path = private_storage / ".medical" / report.storage_key
    exported = (await client.get("/api/v1/privacy/export", headers=patient)).json()["data"]["medical_records"]
    assert exported["history"]["conditions"] == "Private history"
    assert len(exported["reports"]) == 1 and "storage_key" not in exported["reports"][0]
    request = (await client.post("/api/v1/privacy/requests", headers=patient, json={"kind": "deletion"})).json()["data"]
    admin_headers = await admin(client, db_session)
    resolved = await client.post(f"/api/v1/privacy/requests/{request['id']}/resolve", headers=admin_headers)
    assert resolved.status_code == 200, resolved.text
    assert not path.exists()
    assert await db_session.get(MedicalHistory, UUID(user["patient_profile"]["id"])) is None
    assert await db_session.get(MedicalReport, report.id) is None
