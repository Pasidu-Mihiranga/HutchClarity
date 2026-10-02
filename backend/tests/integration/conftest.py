"""Shared setup for the tests that need a real PostgreSQL (issue #6, B05).

These run in the CI `full` lane and locally after `make up-full`. They skip
rather than fail when no database is configured, so `make check` stays
infrastructure-free (ADR-0006) and a green `make check` never implies these ran.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from clarity.app.collections import ALL_COLLECTIONS
from clarity.platform.persistence.migrations import create_schema, drop_schema
from clarity.platform.persistence.postgres import PostgresStore


def database_url() -> str | None:
    return os.environ.get("CLARITY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture
def engine() -> Iterator[Engine]:
    url = database_url()
    if not url:
        pytest.skip("set CLARITY_TEST_DATABASE_URL to run the PostgreSQL integration tests")
    made = create_engine(url, future=True)
    drop_schema(made)
    create_schema(made, ALL_COLLECTIONS)
    try:
        yield made
    finally:
        made.dispose()
        drop_schema(made)
        made.dispose()


@pytest.fixture
def store(engine: Engine) -> PostgresStore:
    return PostgresStore(engine)
