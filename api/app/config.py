from typing import Any, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def asyncpg_url(url: str) -> str:
    """Return the database URL in the form asyncpg accepts.

    Hosted Postgres such as Neon hands out libpq URLs:
    `postgresql://…?sslmode=require&channel_binding=require`. The API connects
    through asyncpg, which takes `ssl` rather than `sslmode` and has no
    `channel_binding`, so such a URL is translated here instead of being edited
    by hand on every deploy. A URL for another driver is returned unchanged.
    """
    parsed = make_url(url)
    if parsed.drivername in ("postgres", "postgresql"):
        parsed = parsed.set(drivername="postgresql+asyncpg")
    if parsed.drivername != "postgresql+asyncpg":
        return url
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode is not None:
        query.setdefault("ssl", sslmode)
    return parsed.set(query=query).render_as_string(hide_password=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        # Settings hold secrets (the database password, SECRET_KEY, the Gemini
        # key), so a validation error must not echo the value into the logs.
        hide_input_in_errors=True,
    )

    PROJECT_NAME: str = "PlanStride"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "DEBUG"
    SECRET_KEY: str = ""
    SQLALCHEMY_DATABASE_URI: str = ""
    # Set by Neon's Vercel integration: the direct and the pooled connection.
    # On Vercel they stand in for an unset SQLALCHEMY_DATABASE_URI.
    DATABASE_URL_UNPOOLED: str = ""
    DATABASE_URL: str = ""
    SQLALCHEMY_ECHO: bool = False
    SECURE_COOKIE: bool = True

    CORS_ORIGINS: str = "http://localhost:3000"

    # Set to 1 by Vercel on its deployments, where the API runs as a serverless
    # function (see `pool_options` in app/database.py).
    VERCEL: bool = False

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

    @model_validator(mode="before")
    @classmethod
    def use_neons_vercel_variables(cls, data: Any) -> Any:
        """On Vercel, connect through Neon's own variables when no
        SQLALCHEMY_DATABASE_URI is set, so connecting the project to Neon is
        the whole database setup. The direct connection is preferred. Never
        off Vercel: a local .env holding production credentials must not be
        connected to by accident.
        """
        if not isinstance(data, dict) or data.get("SQLALCHEMY_DATABASE_URI"):
            return data
        if str(data.get("VERCEL", "")).strip().lower() not in ("1", "true"):
            return data
        neon = data.get("DATABASE_URL_UNPOOLED") or data.get("DATABASE_URL")
        return {**data, "SQLALCHEMY_DATABASE_URI": neon} if neon else data

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
                "SQLALCHEMY_DATABASE_URI cannot be empty. Set SQLALCHEMY_DATABASE_URI "
                "environment variable, or on Vercel connect the project to Neon."
            )
        try:
            return asyncpg_url(v.strip())
        except ArgumentError:
            # SQLAlchemy's own message doesn't say which setting is wrong.
            raise ValueError(
                "SQLALCHEMY_DATABASE_URI isn't a database URL, such as "
                "postgresql://user:password@host/database."
            ) from None

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
