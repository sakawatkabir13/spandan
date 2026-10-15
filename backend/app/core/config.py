import json
from typing import List, Literal, Union

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEMO_MODE: bool = False
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
    MFA_ENCRYPTION_KEY: str = ""
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
    GROQ_TOTAL_TIMEOUT_SECONDS: float = 25.0

    AI_PROVIDER: Literal["bedrock", "groq", "disabled"] = "bedrock"
    AI_ENABLED: bool = False
    AWS_REGION: str = "us-east-1"
    AWS_PROFILE: str = ""
    AWS_BEARER_TOKEN_BEDROCK: str = ""
    AWS_USE_INSTANCE_ROLE: bool = False
    BEDROCK_TRIAGE_MODEL: str = "openai.gpt-oss-120b-1:0"
    BEDROCK_CHAT_MODEL: str = "openai.gpt-oss-120b-1:0"
    AI_TIMEOUT_SECONDS: float = 20
    AI_TOTAL_TIMEOUT_SECONDS: float = 25
    CHAT_ENABLED: bool = False
    CHAT_EVALUATION_FILE: str = ""
    CHAT_ENCRYPTION_KEY: str = ""
    CHAT_SIGNING_PRIVATE_KEY: str = ""
    CHAT_MCP_URL: str = ""
    CHAT_MCP_SERVICE_TOKEN: str = ""
    CHAT_TLS_CA: str = ""
    CHAT_TLS_CERT: str = ""
    CHAT_TLS_KEY: str = ""
    CHAT_TURNS_PER_MINUTE: int = Field(10, ge=1, le=10)
    CHAT_TURNS_PER_DAY: int = Field(100, ge=1, le=100)
    CHAT_MAX_TOOL_CALLS: int = Field(6, ge=1, le=6)
    CHAT_MAX_OUTPUT_TOKENS: int = Field(1500, ge=1, le=1500)
    CHAT_DEADLINE_SECONDS: int = Field(60, ge=1, le=60)
    CHAT_INPUT_PRICE_PER_MILLION: float = 0.15
    CHAT_OUTPUT_PRICE_PER_MILLION: float = 0.60

    @property
    def ai_configured(self) -> bool:
        if not self.AI_ENABLED or self.AI_PROVIDER == "disabled":
            return False
        if self.AI_PROVIDER == "groq":
            return bool(self.GROQ_API_KEY)
        return bool(self.AWS_BEARER_TOKEN_BEDROCK or self.AWS_PROFILE or self.AWS_USE_INSTANCE_ROLE)

    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 5
    OPERATOR_NAME: str = "Spandan"
    OPERATOR_EMAIL: str = "community.cuetinsights@gmail.com"
    SYMPTOM_RETENTION_DAYS: int = 30
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "community.cuetinsights@gmail.com"
    SMTP_STARTTLS: bool = True
    SMTP_SSL: bool = False
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM: str = ""
    S3_BUCKET: str = ""
    S3_BACKUP_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = "ap-south-1"
    S3_PUBLIC_URL: str = ""
    STRIPE_MODE: Literal["test"] = "test"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    PAYMENT_CURRENCY: str = "bdt"
    VIDEO_BASE_URL: str = ""
    EMERGENCY_CONTACT_NUMBER: str = "999"

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        return json.loads(value) if isinstance(value, str) else []

    @property
    def email_enabled(self) -> bool:
        if self.SMTP_HOST.lower() == "smtp.gmail.com" and not (self.SMTP_USERNAME and self.SMTP_PASSWORD):
            return False
        return bool(self.SMTP_HOST and (not self.SMTP_USERNAME or self.SMTP_PASSWORD)
                    and (self.SMTP_STARTTLS or self.SMTP_SSL))

    @property
    def online_payments_enabled(self) -> bool:
        return bool(self.STRIPE_SECRET_KEY and self.STRIPE_WEBHOOK_SECRET)

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.STRIPE_SECRET_KEY and not self.STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_")):
            raise ValueError("Only Stripe test keys are allowed; live payments are disabled")
        if self.SMTP_SSL and self.SMTP_STARTTLS:
            raise ValueError("Choose SMTP_SSL or SMTP_STARTTLS, not both")
        if self.APP_ENV.lower() != "production":
            return self
        placeholder_markers = ("replace-with", "change-me", "your_")
        if (
            self.JWT_SECRET_KEY.startswith("spandan-super-secret")
            or len(self.JWT_SECRET_KEY) < 32
            or any(marker in self.JWT_SECRET_KEY.lower() for marker in placeholder_markers)
        ):
            raise ValueError("JWT_SECRET_KEY must be a private value of at least 32 characters")
        if self.AI_ENABLED and not self.ai_configured:
            raise ValueError("Configure credentials for the selected AI provider")
        if self.CHAT_ENABLED:
            if not self.ai_configured or self.AI_PROVIDER != "bedrock":
                raise ValueError("Chat requires configured Amazon Bedrock access")
            if not self.CHAT_MCP_URL.startswith("https://"):
                raise ValueError("Production MCP must use private HTTPS")
            if not all((self.CHAT_ENCRYPTION_KEY, self.CHAT_SIGNING_PRIVATE_KEY,
                        self.CHAT_MCP_SERVICE_TOKEN, self.CHAT_TLS_CA, self.CHAT_TLS_CERT,
                        self.CHAT_TLS_KEY, self.CHAT_EVALUATION_FILE)):
                raise ValueError("Chat encryption, signing, service authentication, mTLS and evaluation are required")
            if len(self.CHAT_ENCRYPTION_KEY) < 32 or len(self.CHAT_MCP_SERVICE_TOKEN) < 32:
                raise ValueError("Use independent private chat secrets of at least 32 characters")
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            if not isinstance(load_pem_private_key(self.CHAT_SIGNING_PRIVATE_KEY.replace("\\n", "\n").encode(), None), Ed25519PrivateKey):
                raise ValueError("Chat delegation requires an Ed25519 signing key")
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
