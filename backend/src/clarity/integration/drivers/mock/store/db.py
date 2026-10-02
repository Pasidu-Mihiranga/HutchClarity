"""Database engine and session helpers.

``DATABASE_URL`` selects the backend. Tests and the default DEMO profile stay
in memory. FULL profile uses Postgres (or a file SQLite when Docker is not up).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from clarity.integration.drivers.mock.store.models import Base

_ENGINE: Engine | None = None
_SESSION: sessionmaker[Session] | None = None


def default_database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "sqlite+pysqlite:///./clarity_world.db",
    )


def get_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    global _ENGINE, _SESSION
    chosen = url or default_database_url()
    if _ENGINE is not None and str(_ENGINE.url) == chosen.replace("sqlite+pysqlite", "sqlite"):
        return _ENGINE
    connect_args: dict[str, object] = {}
    if chosen.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    _ENGINE = create_engine(chosen, echo=echo, future=True, connect_args=connect_args)
    if chosen.startswith("sqlite"):

        @event.listens_for(_ENGINE, "connect")
        def _sqlite_fk(dbapi_connection: object, _connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _SESSION = sessionmaker(_ENGINE, expire_on_commit=False, future=True)
    return _ENGINE


def reset_engine() -> None:
    """Drop the process-wide engine (tests / reseeding)."""
    global _ENGINE, _SESSION
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SESSION = None


def create_schema(engine: Engine | None = None) -> None:
    eng = engine or get_engine()
    Base.metadata.create_all(eng)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    factory = _SESSION
    if factory is None:
        get_engine() if engine is None else get_engine(str(engine.url))
        factory = _SESSION
    assert factory is not None
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
