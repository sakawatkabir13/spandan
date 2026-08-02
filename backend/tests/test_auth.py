import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_patient_registration_and_login(client: AsyncClient):
    # 1. Register patient
    reg_payload = {
        "email": "testpatient@gmail.com",
        "password": "SecurePassword123!",
        "phone_number": "+8801712345678",
        "full_name": "Test Patient",
        "gender": "Male",
        "address": "Dhaka, Bangladesh",
    }
    response = await client.post("/api/v1/auth/register/patient", json=reg_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user"]["email"] == "testpatient@gmail.com"
    assert data["data"]["role"] == "patient"

    # 2. Login
    login_payload = {
        "email": "testpatient@gmail.com",
        "password": "SecurePassword123!",
    }
    login_response = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["success"] is True
    access_token = login_data["data"]["access_token"]
    assert access_token is not None

    # 3. Get /auth/me
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["data"]["email"] == "testpatient@gmail.com"

    # 4. Get /patients/me
    profile_response = await client.get("/api/v1/patients/me", headers=headers)
    assert profile_response.status_code == 200
    profile_data = profile_response.json()
    assert profile_data["data"]["full_name"] == "Test Patient"
    assert profile_data["data"]["address"] == "Dhaka, Bangladesh"


@pytest.mark.asyncio
async def test_doctor_registration(client: AsyncClient):
    reg_payload = {
        "email": "dr.test@spandan.com.bd",
        "password": "DoctorPassword123!",
        "phone_number": "+8801711223344",
        "full_name": "Dr. Test Cardiologist",
        "medical_registration_number": "BMDC-A-55555",
        "current_workplace": "NICVD Dhaka",
        "years_of_experience": 10,
    }
    response = await client.post("/api/v1/auth/register/doctor", json=reg_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["role"] == "doctor"


@pytest.mark.asyncio
async def test_invalid_login(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@gmail.com", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_CREDENTIALS"
