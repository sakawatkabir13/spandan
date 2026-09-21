import json
from typing import List, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_NAME: str = "Spandan"
    APP_VERSION: str = "1.0.0"
    APP_TIMEZONE: str = "Asia/Dhaka"
    LOG_LEVEL: str = "INFO"
    ENABLE_DOCS: bool = True
    FORCE_HTTPS: bool = False
    MAX_REQUEST_SIZE_BYTES: int = 6_291_456
    ALLOWED_HOSTS: Union[List[str], str] = ["localhost", "127.0.0.1", "backend", "test"]

    DATABASE_URL: str = "postgresql+asyncpg://spandan:spandan@localhost:5432/spandan"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30

    JWT_SECRET_KEY: str = "spandan-super-secret-jwt-key-for-development-only-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return json.loads(v) if isinstance(v, str) else []

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT_SECONDS: float = 20.0
    GROQ_MAX_RETRIES: int = 2

    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 5
    EMERGENCY_CONTACT_NUMBER: str = "999"

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        return json.loads(value) if isinstance(value, str) else []

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.APP_ENV.lower() != "production":
            return self
        placeholder_markers = ("replace-with", "change-me", "your_")
        if (
            self.JWT_SECRET_KEY.startswith("spandan-super-secret")
            or len(self.JWT_SECRET_KEY) < 32
            or any(marker in self.JWT_SECRET_KEY.lower() for marker in placeholder_markers)
        ):
            raise ValueError("JWT_SECRET_KEY must be a private value of at least 32 characters")
        if not self.GROQ_API_KEY or any(
            marker in self.GROQ_API_KEY.lower() for marker in placeholder_markers
        ):
            raise ValueError("GROQ_API_KEY is required in production")
        if (
            "localhost" in self.DATABASE_URL
            or "spandan:spandan" in self.DATABASE_URL
            or any(marker in self.DATABASE_URL.lower() for marker in placeholder_markers)
        ):
            raise ValueError("Production DATABASE_URL must not use local or default credentials")
        if "*" in self.CORS_ORIGINS:
            raise ValueError("Wildcard CORS origins are not allowed in production")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
