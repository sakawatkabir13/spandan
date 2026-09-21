import base64
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import Settings


def test_production_settings_reject_documented_placeholders():
    with pytest.raises(ValueError):
        Settings(
            APP_ENV="production",
            DATABASE_URL=(
                "postgresql+asyncpg://spandan_app:replace-with-password@db:5432/spandan"
            ),
            JWT_SECRET_KEY="replace-with-at-least-32-random-characters",
            GROQ_API_KEY="replace-with-your-groq-secret",
            CORS_ORIGINS=["https://spandan.example.com"],
            _env_file=None,
        )


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

    # 5. Uploads accept real raster formats, return the public URL, and reject spoofed files.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
    )
    photo_response = await client.post(
        "/api/v1/patients/me/photo",
        headers=headers,
        files={"photo": ("avatar.png", png, "image/png")},
    )
    assert photo_response.status_code == 200
    photo_url = photo_response.json()["data"]["profile_photo_url"]
    assert (await client.get(photo_url)).status_code == 200
    invalid_photo = await client.post(
        "/api/v1/patients/me/photo",
        headers=headers,
        files={"photo": ("fake.jpg", b"not an image", "image/jpeg")},
    )
    assert invalid_photo.status_code == 400
    Path(photo_url.removeprefix("/")).unlink(missing_ok=True)

    # 6. Logout revokes both access and refresh tokens server-side.
    logout_response = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login_data["data"]["refresh_token"]}
    )
    assert refresh_response.status_code == 401


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
