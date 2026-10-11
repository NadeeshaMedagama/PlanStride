from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    PROJECT_NAME: str = "PlanStride"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "DEBUG"
    SECRET_KEY: str = ""
    SQLALCHEMY_DATABASE_URI: str = ""
    SQLALCHEMY_ECHO: bool = False
    SECURE_COOKIE: bool = True

    CORS_ORIGINS: str = "http://localhost:3000"

    # JWT Token settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_ALGORITHM: str = "HS256"

    # Cloudflare API token for SSL certificates
    CLOUDFLARE_API_TOKEN: str | None = None

    # AI (Pydantic AI + Gemini). The key is read from api/.env only and never
    # leaves the server. Without it the AI endpoints answer "not configured"
    # and the rest of the product works as normal.
    GOOGLE_API_KEY: str | None = None
    AI_MODEL: str = "gemini-3.5-flash-lite"
    # Upper bound for one AI request end to end, so a slow model can't hang
    # the planning screen.
    AI_TIMEOUT_SECONDS: float = 25.0
    # Per-user cap that keeps one member from burning the free-tier quota for
    # the whole organization. Counted from the usage log, so it holds across
    # workers without extra infrastructure.
    AI_REQUESTS_PER_USER_PER_MINUTE: int = 6

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v):
        if not v or not v.strip():
            raise ValueError(
                "SECRET_KEY cannot be empty. Set SECRET_KEY environment variable."
            )
        return v

    @field_validator("SQLALCHEMY_DATABASE_URI")
    @classmethod
    def validate_database_uri(cls, v):
        if not v or not v.strip():
            raise ValueError(
                "SQLALCHEMY_DATABASE_URI cannot be empty. Set SQLALCHEMY_DATABASE_URI environment variable."
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
