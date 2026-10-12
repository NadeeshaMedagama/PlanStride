import asyncio
import logging
import warnings

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import models
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.ai.provider import get_ai_model
from app.database import get_db
from app.models import Base

# No test may reach a real model provider: with this off, Pydantic AI refuses
# any request that isn't to TestModel/FunctionModel, so `uv run pytest` needs
# neither a Google API key nor network access.
models.ALLOW_MODEL_REQUESTS = False

# Suppress SQLAlchemy pool connection errors during test cleanup
logging.getLogger("sqlalchemy.pool.impl.AsyncAdaptedQueuePool").setLevel(
    logging.CRITICAL
)

# Filter out the specific async warning that occurs during testing
# This is a known issue with async SQLAlchemy connections in tests
warnings.filterwarnings(
    "ignore",
    message="coroutine.*was never awaited",
    category=RuntimeWarning,
    module=".*",
)

# Filter out connection cleanup warnings during test teardown
warnings.filterwarnings(
    "ignore",
    message=".*Event loop is closed.*",
    category=RuntimeWarning,
    module=".*",
)

# Filter out SQLAlchemy pool cleanup errors during testing
warnings.filterwarnings(
    "ignore",
    message=".*Exception terminating connection.*",
    category=Warning,
    module=".*",
)

# Suppress asyncpg connection closure warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncpg.*")

TABLES = ", ".join(table.name for table in Base.metadata.sorted_tables)


@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for tests."""
    with PostgresContainer("postgres:16") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def database_url(postgres_container) -> str:
    return postgres_container.get_connection_url().replace("psycopg2", "asyncpg")


@pytest.fixture
async def test_engine(database_url):
    """Create engine for each test to avoid event loop issues."""
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=False,  # Disable pre-ping to avoid cleanup issues
        pool_recycle=300,
        pool_timeout=10,
        pool_size=2,  # Smaller pool for tests
        max_overflow=5,
        connect_args={"server_settings": {"application_name": "pytest"}},
    )

    # Create tables (no-op after the first test) and start every test empty.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))

    yield engine

    # Graceful engine disposal with error handling
    try:
        # Use a shorter timeout and handle cleanup gracefully
        await asyncio.wait_for(engine.dispose(), timeout=2.0)
    except TimeoutError:
        # If disposal times out, the connections will be forcefully closed
        pass
    except Exception:
        # Ignore other disposal errors during test cleanup
        logging.getLogger(__name__).debug("Engine disposal failed", exc_info=True)


@pytest.fixture
def session_factory(test_engine):
    """Session factory for tests that need direct database access."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def db(session_factory):
    """A session for arranging test data and checking what the API wrote."""
    async with session_factory() as session:
        yield session


@pytest.fixture
def ai_model():
    """The model the AI endpoints run on. None means "no key configured";
    tests swap in TestModel/FunctionModel through `use_model`."""
    return {"model": None}


@pytest.fixture
def use_model(ai_model):
    def _use(model):
        ai_model["model"] = model

    return _use


@pytest.fixture
async def async_client(test_engine, session_factory, ai_model):
    """Create async test client with test database."""

    async def get_test_db():
        async with session_factory() as session:
            yield session

    from app.main import app as fastapi_app
    from app.main import app_api, internal_api

    # The surfaces are mounted sub-applications, each resolving its own
    # dependencies, so overrides are set on each of them.
    for api in (fastapi_app, app_api, internal_api):
        api.dependency_overrides[get_db] = get_test_db
    app_api.dependency_overrides[get_ai_model] = lambda: ai_model["model"]

    # Also override the database engine at the module level to prevent conflicts
    import app.database

    original_engine = app.database.async_engine
    original_session_local = app.database.AsyncSessionLocal

    app.database.async_engine = test_engine
    app.database.AsyncSessionLocal = session_factory

    # HTTPS, as in production: session cookies are `Secure` unless a local
    # .env turns SECURE_COOKIE off, and the client only sends those back over
    # HTTPS. Over HTTP the suite would pass or fail depending on someone's .env.
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="https://localhost"
    ) as ac:
        yield ac

    # Cleanup - ensure proper order and error handling
    for api in (fastapi_app, app_api, internal_api):
        api.dependency_overrides.clear()

    # Restore original database setup
    app.database.async_engine = original_engine
    app.database.AsyncSessionLocal = original_session_local
