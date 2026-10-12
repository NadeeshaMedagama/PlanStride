"""Migrations build the schema the models describe, from an empty database.

The rest of the suite creates tables straight from the models, so this is the
test that catches a model change without a migration (or a migration edited by
hand into something autogenerate wouldn't produce).
"""

import asyncio
from pathlib import Path

import psycopg2
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.database
from app.models import Base

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture
def empty_database_url(postgres_container):
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    user, password = postgres_container.username, postgres_container.password
    name = "migrations_check"

    admin = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=postgres_container.dbname,
    )
    admin.autocommit = True
    with admin.cursor() as cursor:
        cursor.execute(f"DROP DATABASE IF EXISTS {name}")
        cursor.execute(f"CREATE DATABASE {name}")
    yield f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
    with admin.cursor() as cursor:
        cursor.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    admin.close()


def test_migrations_build_the_models_schema_and_roll_back(
    empty_database_url, monkeypatch
):
    # migrations/env.py runs on `app.database.async_engine`; point it here.
    # NullPool: each alembic command runs in its own event loop.
    engine = create_async_engine(empty_database_url, poolclass=NullPool)
    monkeypatch.setattr(app.database, "async_engine", engine)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))

    async def drift():
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync: compare_metadata(
                    MigrationContext.configure(sync), Base.metadata
                )
            )

    command.upgrade(config, "head")
    assert asyncio.run(drift()) == []

    command.downgrade(config, "base")
    command.upgrade(config, "head")  # and forward again from scratch
