import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ai_triage_engine_emergency_rules_and_fallback(client: AsyncClient):
    # 1. Register and login as patient
    await client.post(
        "/api/v1/auth/register/patient",
        json={
            "email": "triage_test@gmail.com",
            "password": "Password123!",
            "phone_number": "+8801710006666",
            "full_name": "Triage Patient",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "triage_test@gmail.com", "password": "Password123!"}
    )
    access_token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Test Emergency Rule-Based Screening (e.g. chest pain)
    emergency_payload = {
        "symptoms_text": "I have sudden severe chest pain radiating to my left arm and slurred speech.",
        "age": 55,
        "gender": "Male",
        "duration_days": 1,
    }
    em_resp = await client.post("/api/v1/ai/symptom-check", json=emergency_payload, headers=headers)
    assert em_resp.status_code == 201
    em_data = em_resp.json()["data"]
    assert em_data["urgency_level"] == "emergency"
    assert em_data["recommended_specialization_name"] == "Emergency Medicine / ER"
    assert em_data["model_identifier"] == "rule-based-emergency-engine"
    assert "DO NOT wait" in em_data["safety_message"] or "Emergency Room" in em_data["safety_message"]

    # 3. Test Fallback Triage (when Groq API key is not set in test environment)
    routine_payload = {
        "symptoms_text": "I have mild fever and sore throat for the past three days without any breathing trouble.",
        "age": 30,
        "gender": "Female",
        "duration_days": 3,
    }
    fb_resp = await client.post("/api/v1/ai/symptom-check", json=routine_payload, headers=headers)
    assert fb_resp.status_code == 201
    fb_data = fb_resp.json()["data"]
    assert fb_data["recommended_specialization_name"] == "General Medicine"
    assert fb_data["urgency_level"] == "soon"
    assert fb_data["model_identifier"] == "fallback-general-medicine"

    # 4. Verify recommendation history
    hist_resp = await client.get("/api/v1/ai/recommendations/me", headers=headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()["data"]
    assert len(hist_data) == 2
    # Ordered desc by created_at, so first item is fallback routine check, second is emergency
    assert hist_data[0]["model_identifier"] == "fallback-general-medicine"
    assert hist_data[1]["model_identifier"] == "rule-based-emergency-engine"
