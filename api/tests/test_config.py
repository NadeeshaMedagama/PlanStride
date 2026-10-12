"""Settings and the database engine as a hosted deploy needs them: a Neon
connection string pasted as-is, and no idle connections on Vercel."""

import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, asyncpg_url
from app.database import pool_options

# The shape of the connection string Neon's dashboard hands out.
NEON_URL = (
    "postgresql://neondb_owner:npg_s3cret@ep-cool-name-a1b2c3d4.us-east-1.aws"
    ".neon.tech/neondb?sslmode=require&channel_binding=require"
)


def test_a_neon_connection_string_is_translated_for_asyncpg():
    assert asyncpg_url(NEON_URL) == (
        "postgresql+asyncpg://neondb_owner:npg_s3cret@ep-cool-name-a1b2c3d4"
        ".us-east-1.aws.neon.tech/neondb?ssl=require"
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param(
            "postgres://user:pw@db.example.com:5433/app?sslmode=require",
            "postgresql+asyncpg://user:pw@db.example.com:5433/app?ssl=require",
            id="postgres scheme",
        ),
        pytest.param(
            "postgresql+asyncpg://user:pw@db.example.com/app?sslmode=verify-full",
            "postgresql+asyncpg://user:pw@db.example.com/app?ssl=verify-full",
            id="asyncpg URL with sslmode",
        ),
        pytest.param(
            "postgresql+asyncpg://user:pw@db.example.com/app?ssl=require",
            "postgresql+asyncpg://user:pw@db.example.com/app?ssl=require",
            id="already translated",
        ),
        pytest.param(
            "postgresql+asyncpg://user:pw@db.example.com/app?ssl=disable&sslmode=require",
            "postgresql+asyncpg://user:pw@db.example.com/app?ssl=disable",
            id="explicit ssl wins",
        ),
        pytest.param(
            "postgresql://user:p%40ss%25word@db.example.com/app",
            "postgresql+asyncpg://user:p%40ss%25word@db.example.com/app",
            id="percent-encoded password",
        ),
        pytest.param(
            "postgresql+asyncpg://postgres:postgres@localhost:5432/planstride",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/planstride",
            id="local default",
        ),
        pytest.param(
            "postgresql+psycopg://user:pw@db.example.com/app?sslmode=require",
            "postgresql+psycopg://user:pw@db.example.com/app?sslmode=require",
            id="another driver",
        ),
    ],
)
def test_database_urls_end_up_in_asyncpg_form(url, expected):
    assert asyncpg_url(url) == expected


def test_settings_translate_a_pasted_connection_string():
    settings = Settings(SQLALCHEMY_DATABASE_URI=f" {NEON_URL}\n", SECRET_KEY="test")

    assert settings.SQLALCHEMY_DATABASE_URI == asyncpg_url(NEON_URL)


# Short, because pydantic elides the middle of a long value it echoes, which
# could hide a leak rather than prevent it.
@pytest.mark.parametrize(
    "url",
    [
        pytest.param("'postgresql://u:hunter2@db/app'", id="quoted"),
        pytest.param("postgresql://u:hunter2@db:port/app", id="port"),
    ],
)
def test_a_bad_database_url_is_reported_without_its_password(url):
    with pytest.raises(ValidationError) as error:
        Settings(SQLALCHEMY_DATABASE_URI=url, SECRET_KEY="test")

    assert "SQLALCHEMY_DATABASE_URI" in str(error.value)
    assert "hunter2" not in str(error.value)


def test_the_vercel_flag_comes_from_vercels_own_variable(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")

    assert Settings(SQLALCHEMY_DATABASE_URI=NEON_URL, SECRET_KEY="test").VERCEL


async def test_a_libpq_connection_string_connects_once_translated(postgres_container):
    # What a pasted Neon URL becomes, against a real server. The test server
    # has no TLS, so the same parameters ask for none.
    container = postgres_container
    url = (
        f"postgresql://{container.username}:{container.password}"
        f"@{container.get_container_host_ip()}:{container.get_exposed_port(5432)}"
        f"/{container.dbname}?sslmode=disable&channel_binding=disable"
    )
    engine = create_async_engine(asyncpg_url(url), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT 1")) == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("serverless", "left_open"),
    [pytest.param(True, 0, id="on Vercel"), pytest.param(False, 1, id="elsewhere")],
)
async def test_on_vercel_no_connection_outlives_its_session(
    database_url, serverless, left_open
):
    name = f"pool-check-{serverless}"
    engine = create_async_engine(
        database_url,
        connect_args={"server_settings": {"application_name": name}},
        **pool_options(serverless=serverless),
    )
    observer = create_async_engine(database_url, poolclass=NullPool)

    async def open_connections() -> int:
        async with observer.connect() as connection:
            count = await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE application_name = :name"
                ),
                {"name": name},
            )
        return count or 0

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        # A closed connection's server process takes a moment to exit.
        for _ in range(40):
            if await open_connections() == left_open:
                break
            await asyncio.sleep(0.05)
        assert await open_connections() == left_open
    finally:
        await engine.dispose()
        await observer.dispose()
