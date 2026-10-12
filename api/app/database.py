from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapper
from sqlalchemy.pool import NullPool

from app.config import settings


def pool_options(serverless: bool) -> dict[str, Any]:
    """Connection pooling for where the API runs.

    On Vercel the API is a serverless function: instances are frozen between
    requests and multiply under load. Pooled connections would sit idle on
    frozen instances, count against the database's connection limit, and be
    cut whenever Neon scales to zero, so there every connection is closed as
    soon as the session using it is done. Everywhere else connections are pooled
    and checked before each use.
    """
    if serverless:
        return {"poolclass": NullPool}
    return {"pool_pre_ping": True}


async_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.SQLALCHEMY_ECHO,
    **pool_options(serverless=settings.VERCEL),
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, expire_on_commit=False
)


class Base(AsyncAttrs, DeclarativeBase):
    """subclasses will be converted to dataclasses"""


@event.listens_for(Mapper, "mapper_configured")
def _default_lazy_raise_on_sql(mapper, _):  # pyright: ignore[reportUnusedFunction]
    # Surface accidental lazy loads as a clear error instead of MissingGreenlet
    # in async contexts. Use selectin/joined eager loading or `awaitable_attrs`.
    for rel in mapper.relationships:
        if rel.lazy == "select":
            rel.lazy = "raise_on_sql"


async def get_db():
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()


DBSession = Annotated[AsyncSession, Depends(get_db)]
