import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.account_session import MFARecoveryCode
from app.models.operations import WaitlistEntry
from app.services.account_security import totp
from tests.test_medical_records import PDF, upload
from tests.test_operations import book
from tests.test_workflows import register, session


async def test_dependent_chart_visit_selection_preview_and_access_history(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    doctor, _, schedule, _ = await session(client, db_session)
    parent, _ = await register(client, "patient", "care-parent")
    stranger, _ = await register(client, "patient", "care-stranger")
    child = (await client.post('/api/v1/dependents', headers=parent, json={"full_name": "Child chart", "relationship_name": "Child", "date_of_birth": "2020-01-01"})).json()["data"]
    suffix = f"?dependent_id={child['id']}"
    assert (await client.get('/api/v1/medical-records/me' + suffix, headers=stranger)).status_code == 404
    parent_report = (await upload(client, parent)).json()["data"]
    await client.patch('/api/v1/medical-records/me/history', headers=parent, json={"allergies": "Parent-only allergy", "share_with_doctors": True})
    assert (await client.patch('/api/v1/medical-records/me/history' + suffix, headers=parent, json={"allergies": "Child allergy", "history_reviewed": True, "share_with_doctors": False})).status_code == 200
    report = (await client.post('/api/v1/medical-records/me/reports' + suffix, headers=parent, data={"title": "Child report", "report_type": "lab"}, files={"file": ("child.pdf", PDF, "application/pdf")})).json()["data"]
    appointment = await book(client, parent, schedule, dependent_id=child["id"])
    sharing = f"/api/v1/appointments/{appointment['id']}/sharing"
    assert (await client.put(sharing, headers=parent, json={"share_history": True, "report_ids": [parent_report["id"]]})).status_code == 400
    assert (await client.put(sharing, headers=stranger, json={"share_history": True, "report_ids": []})).status_code == 404
    assert (await client.put(sharing, headers=parent, json={"share_history": True, "report_ids": [report["id"]]})).status_code == 200
    base = f"/api/v1/medical-records/appointments/{appointment['id']}"
    response = await client.get(base, headers=doctor)
    assert "Child allergy" in response.text and "Parent-only allergy" not in response.text
    assert [r["id"] for r in response.json()["data"]["reports"]] == [report["id"]]
    preview = await client.get(base + f"/reports/{report['id']}/preview", headers=doctor)
    assert preview.content == PDF and preview.headers["content-disposition"].startswith("inline")
    assert preview.headers["cache-control"] == "no-store, private"
    access = (await client.get('/api/v1/medical-records/access-history', headers=parent)).json()["data"]
    assert {row["action"] for row in access} >= {"medical.records_viewed", "medical.report_previewed"}
    assert not (await client.get('/api/v1/medical-records/access-history', headers=stranger)).json()["data"]
    assert (await client.patch(f"/api/v1/medical-records/me/reports/{report['id']}/sharing?shared=false", headers=parent)).status_code == 200
    assert (await client.get(base + f"/reports/{report['id']}/preview", headers=doctor)).status_code == 403
    assert (await client.put(sharing, headers=parent, json={"share_history": False, "report_ids": []})).status_code == 200
    assert not (await client.get(base, headers=doctor)).json()["data"]["shared"]


async def test_doctor_reviewed_summary_draft_visibility_revision_and_followup(client, db_session):
    doctor, _, schedule, _ = await session(client, db_session)
    patient, _ = await register(client, "patient", "care-summary")
    stranger, _ = await register(client, "patient", "care-summary-other")
    appointment = await book(client, patient, schedule)
    path = f"/api/v1/appointments/{appointment['id']}/visit-summary"
    body = {"summary": "Reviewed consultation", "prescription": "Doctor-authored prescription", "follow_up_instructions": "Bring the requested report", "revision": 0}
    assert (await client.put(path, headers=patient, json=body)).status_code == 403
    assert (await client.put(path, headers=doctor, json=body)).status_code == 409
    assert (await client.patch(f"/api/v1/appointments/{appointment['id']}/status", headers=doctor, json={"appointment_status": "in_consultation"})).status_code == 200
    draft = await client.put(path, headers=doctor, json=body)
    assert draft.status_code == 200, draft.text
    assert draft.json()["data"]["revision"] == 1
    assert (await client.get(path, headers=patient)).json()["data"] is None
    assert (await client.get(path, headers=stranger)).status_code == 403
    assert (await client.put(path, headers=doctor, json={**body, "publish": True})).status_code == 409
    published = await client.put(path, headers=doctor, json={**body, "revision": 1, "publish": True})
    assert published.status_code == 200 and published.json()["data"]["published_at"]
    assert (await client.get(path, headers=patient)).json()["data"]["prescription"] == body["prescription"]
    assert (await client.put(path, headers=doctor, json={**body, "revision": 2})).status_code == 409


async def test_reserved_waitlist_expiry_ownership_and_duplicate_accept(client, db_session):
    _, _, schedule, _ = await session(client, db_session, capacity=1)
    owner, _ = await register(client, "patient", "offer-owner")
    first, _ = await register(client, "patient", "offer-first")
    second, _ = await register(client, "patient", "offer-second")
    booking = await book(client, owner, schedule)
    one = (await client.post(f"/api/v1/waitlist/{schedule['id']}", headers=first)).json()["data"]
    two = (await client.post(f"/api/v1/waitlist/{schedule['id']}", headers=second)).json()["data"]
    await client.patch(f"/api/v1/appointments/{booking['id']}/status", headers=owner, json={"appointment_status": "cancelled"})
    assert (await client.post("/api/v1/appointments", headers=second, json={"schedule_id": schedule["id"]})).status_code == 409
    assert (await client.post(f"/api/v1/waitlist/{one['id']}/accept", headers=second, json={})).status_code == 404
    row = await db_session.get(WaitlistEntry, UUID(one["id"]))
    assert row.status == "offered" and row.offer_expires_at
    row.offer_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    assert (await client.post(f"/api/v1/waitlist/{one['id']}/accept", headers=first, json={})).status_code == 409
    # The next worker/cancellation pass advances the queue after a restart using stored timestamps.
    from app.repositories.schedule import schedule_repo
    from app.services.waitlist import offer_places
    await offer_places(db_session, await schedule_repo.get_by_id_with_queue(db_session, UUID(schedule["id"]), lock=True))
    await db_session.commit()
    accepted = await client.post(f"/api/v1/waitlist/{two['id']}/accept", headers=second, json={})
    assert accepted.status_code == 201, accepted.text
    repeated = await client.post(f"/api/v1/waitlist/{two['id']}/accept", headers=second, json={})
    assert repeated.status_code == 201 and repeated.json()["data"]["id"] == accepted.json()["data"]["id"]
    assert (await client.post(f"/api/v1/waitlist/{one['id']}/accept", headers=first, json={})).status_code == 409


async def test_device_revocation_refresh_reuse_failed_login_and_recovery_codes(client, db_session, monkeypatch):
    headers, user = await register(client, "patient", "device-security")
    credentials = {"email": user["email"], "password": "Password123!"}
    bad = await client.post('/api/v1/auth/login', json={**credentials, "password": "incorrect"})
    assert bad.status_code == 401
    activity = (await client.get('/api/v1/auth/login-activity', headers=headers)).json()["data"]
    assert any(row["action"] == "account.login_failed" for row in activity)
    tokens = (await client.post('/api/v1/auth/login', json=credentials)).json()["data"]
    rotated = await client.post('/api/v1/auth/refresh', json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200 and rotated.json()["data"]["refresh_token"] != tokens["refresh_token"]
    assert (await client.post('/api/v1/auth/refresh', json={"refresh_token": tokens["refresh_token"]})).status_code == 401
    assert (await client.get('/api/v1/auth/me', headers={"Authorization": "Bearer " + rotated.json()["data"]["access_token"]})).status_code == 401
    login = (await client.post('/api/v1/auth/login', json=credentials)).json()["data"]
    headers = {"Authorization": "Bearer " + login["access_token"]}
    second = (await client.post('/api/v1/auth/login', json=credentials)).json()["data"]
    devices = (await client.get('/api/v1/auth/sessions', headers=headers)).json()["data"]
    other = next(d for d in devices if not d["current"])
    assert (await client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=headers)).status_code == 200
    assert (await client.get('/api/v1/auth/me', headers={"Authorization": "Bearer " + second["access_token"]})).status_code == 401
    secret = (await client.post('/api/v1/auth/mfa/setup', headers=headers, json={"password": credentials["password"]})).json()["data"]["secret"]
    import time
    stamp = time.time()
    counter = int(stamp // 30)
    await client.post('/api/v1/auth/mfa/enable', headers=headers, json={"password": credentials["password"], "code": totp(secret, counter)})
    login = (await client.post('/api/v1/auth/login', json={**credentials, "mfa_code": totp(secret, counter + 1)})).json()["data"]
    headers = {"Authorization": "Bearer " + login["access_token"]}
    monkeypatch.setattr("app.services.account_security.time.time", lambda: stamp + 30)
    response = await client.post('/api/v1/auth/mfa/recovery-codes', headers=headers, json={"password": credentials["password"], "code": totp(secret, counter + 2)})
    assert response.status_code == 200, response.text
    codes = response.json()["data"]["codes"]
    assert len(codes) == 10
    stored = list(await db_session.scalars(select(MFARecoveryCode)))
    assert all(code not in row.digest for code in codes for row in stored)
    assert (await client.post('/api/v1/auth/login', json={**credentials, "mfa_code": codes[0]})).status_code == 200
    assert (await client.post('/api/v1/auth/login', json={**credentials, "mfa_code": codes[0]})).status_code == 401


async def test_postgresql_booking_and_queue_burst(client, db_session):
    """A burst uses independent transactions, exercising the real locking path."""
    import pytest

    from tests.conftest import TEST_DATABASE_URL, test_async_session_maker
    if TEST_DATABASE_URL.startswith('sqlite'):
        pytest.skip('Requires PostgreSQL row locks')
    doctor, _, schedule, _ = await session(client, db_session, capacity=5)
    patients = [(await register(client, 'patient', f'burst-{i}'))[0] for i in range(12)]
    async def independent_db():
        async with test_async_session_maker() as db:
            try:
                yield db
            except Exception:
                await db.rollback()
                raise
    app.dependency_overrides[get_db] = independent_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        responses = await asyncio.gather(*(ac.post('/api/v1/appointments', headers=h, json={"schedule_id": schedule["id"]}) for h in patients))
        assert sum(r.status_code == 201 for r in responses) == 5
        assert sum(r.status_code == 400 for r in responses) == 7
        serials = [r.json()["data"]["serial_number"] for r in responses if r.status_code == 201]
        assert len(set(serials)) == 5
        calls = await asyncio.gather(*(ac.post(f"/api/v1/schedules/{schedule['id']}/queue/increment", headers=doctor) for _ in range(4)))
        assert all(r.status_code == 200 for r in calls)
        roster = (await ac.get(f"/api/v1/appointments/schedule/{schedule['id']}", headers=doctor)).json()["data"]
        assert sum(a['appointment_status'] == 'in_consultation' for a in roster) == 1
        assert sum(a['appointment_status'] == 'completed' for a in roster) == 3


async def test_family_age_rules_favorites_and_doctor_unavailability(client, db_session):
    from app.models.operations import Notification
    from tests.test_workflows import admin

    staff, doctor, schedule, _ = await session(client, db_session, capacity=3)
    patient, _ = await register(client, 'patient', 'care-age-parent')
    other, _ = await register(client, 'patient', 'care-age-other')
    assert (await client.patch('/api/v1/doctors/me/profile', headers=staff, json={
        'languages': 'English, Bengali', 'minimum_patient_age': 0, 'maximum_patient_age': 12,
    })).status_code == 200
    facts = (await client.get(f'/api/v1/doctors/{doctor.id}/booking-facts')).json()['data']
    assert facts['maximum_patient_age'] == 12 and facts['next_session']['confirmed_at']
    assert (await client.put(f'/api/v1/patients/me/favorites/{doctor.id}?saved=true', headers=patient)).status_code == 200
    saved = (await client.get('/api/v1/patients/me/favorite-doctors', headers=patient)).json()['data']
    assert [row['id'] for row in saved] == [str(doctor.id)]
    assert not (await client.get('/api/v1/patients/me/favorites', headers=other)).json()['data']
    assert (await client.post('/api/v1/appointments', headers=patient, json={'schedule_id': schedule['id']})).status_code == 400
    assert (await client.patch('/api/v1/patients/me', headers=patient, json={'date_of_birth': '1990-01-01'})).status_code == 200
    response = await client.post('/api/v1/appointments', headers=patient, json={'schedule_id': schedule['id']})
    assert response.status_code == 400 and response.json()['error']['code'] == 'AGE_RESTRICTION'
    body = {'full_name': 'Family chart', 'relationship_name': 'Child', 'date_of_birth': '2020-01-01'}
    child = (await client.post('/api/v1/dependents', headers=patient, json=body)).json()['data']
    path = f"/api/v1/dependents/{child['id']}"
    assert (await client.patch(path, headers=other, json=body)).status_code == 404
    assert (await client.patch(path, headers=patient, json={**body, 'full_name': 'Updated child'})).status_code == 200
    booking = await book(client, patient, schedule, dependent_id=child['id'])
    assert booking['attendee_name'] == 'Updated child'
    await client.delete(path, headers=patient)
    assert not (await client.get('/api/v1/dependents', headers=patient)).json()['data']
    assert (await client.get('/api/v1/dependents?include_archived=true', headers=patient)).json()['data'][0]['is_active'] is False
    assert (await client.get(f"/api/v1/medical-records/me?dependent_id={child['id']}", headers=patient)).status_code == 200
    assert (await client.post(path + '/restore', headers=patient)).status_code == 200
    wait = (await client.post(f"/api/v1/waitlist/{schedule['id']}", headers=other)).json()['data']
    administrator = await admin(client, db_session)
    assert (await client.post(f'/api/v1/doctors/{doctor.id}/verify', headers=administrator, json={'status': 'suspended'})).status_code == 200
    notices = list(await db_session.scalars(select(Notification).where(Notification.subject == 'Chamber availability changed')))
    assert notices and all(booking['id'] in notice.message for notice in notices)
    from app.repositories.schedule import schedule_repo
    from app.services.waitlist import offer_places
    await offer_places(db_session, await schedule_repo.get_by_id_with_queue(db_session, UUID(schedule['id']), lock=True))
    await db_session.commit()
    assert (await db_session.get(WaitlistEntry, UUID(wait['id']))).status == 'unavailable'
    assert not (await client.get('/api/v1/patients/me/favorite-doctors', headers=patient)).json()['data']


async def test_checkout_failure_audit_is_bound_to_provider_session_and_deduplicated(client, db_session, monkeypatch):
    import hashlib
    import hmac
    import json
    import time
    from unittest.mock import AsyncMock

    from app.models.audit import AuditLog
    from app.models.operations import Payment
    from app.services import billing

    _, _, schedule, _ = await session(client, db_session)
    patient, _ = await register(client, 'patient', 'care-payment-failure')
    booking = await book(client, patient, schedule)
    payment = Payment(appointment_id=UUID(booking['id']), amount=500, currency='bdt', provider='stripe', status='pending', provider_reference='cs_test_bound', is_test=True)
    db_session.add(payment)
    await db_session.commit()
    monkeypatch.setattr(settings, 'STRIPE_WEBHOOK_SECRET', 'whsec_care_test_fixture')
    monkeypatch.setattr(billing, 'stripe', AsyncMock(return_value={'payment_intent': 'pi_test_bound', 'livemode': False, 'metadata': {'payment_id': str(payment.id)}}))

    async def deliver(intent, amount=50000, event_id='evt_care_failed'):
        raw = json.dumps({'id': event_id, 'type': 'payment_intent.payment_failed', 'livemode': False, 'data': {'object': {'id': intent, 'metadata': {'payment_id': str(payment.id)}, 'amount': amount, 'currency': 'bdt'}}}).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
        return await client.post('/api/v1/payments/webhook', content=raw, headers={'stripe-signature': f't={timestamp},v1={signature}'})
    assert (await deliver('pi_wrong')).status_code == 400
    assert (await deliver('pi_test_bound', amount=100)).status_code == 400
    assert (await deliver('pi_test_bound')).status_code == 200
    assert (await deliver('pi_test_bound')).status_code == 200
    failures = list(await db_session.scalars(select(AuditLog).where(AuditLog.action == 'payment.checkout_failed')))
    assert len(failures) == 1
    await db_session.refresh(payment)
    assert payment.status == 'pending'
