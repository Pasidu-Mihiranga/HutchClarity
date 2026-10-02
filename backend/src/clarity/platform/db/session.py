"""Async SQLAlchemy + schema-per-module helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def make_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(url, echo=echo, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def ensure_schemas(engine: AsyncEngine, schemas: list[str]) -> None:
    async with engine.begin() as conn:
        for schema in schemas:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


async def set_rls_vars(
    session: AsyncSession,
    *,
    subscriber_ref: str | None = None,
    roles: list[str] | None = None,
    is_staff: bool = False,
) -> None:
    """Set Postgres session variables used by RLS policies."""
    await session.execute(
        text("SELECT set_config('app.subscriber_ref', :v, true)"),
        {"v": subscriber_ref or ""},
    )
    await session.execute(
        text("SELECT set_config('app.roles', :v, true)"),
        {"v": ",".join(roles or [])},
    )
    await session.execute(
        text("SELECT set_config('app.is_staff', :v, true)"),
        {"v": "true" if is_staff else "false"},
    )


async def create_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def schema_table(schema: str, name: str) -> dict[str, Any]:
    return {"schema": schema}
