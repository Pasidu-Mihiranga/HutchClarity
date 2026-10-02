"""Alembic ``env.py`` template for a single module schema.

Copy into ``backend/migrations/<module>/env.py`` and set ``MODULE_SCHEMA``.
Each module owns one Postgres schema and one Alembic history (ADR-0002 /
schema-per-module). Never share a migration tree across modules.

Usage sketch::

    cd backend
    alembic -c migrations/case/alembic.ini upgrade head

The real ``env.py`` should import that module's SQLAlchemy models so
``target_metadata`` includes only tables in ``MODULE_SCHEMA``.
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# --- per-module knobs (edit when copying) ---------------------------------
MODULE_SCHEMA = "case"  # e.g. case | actions | receipts | platform
# from clarity.modules.case.infrastructure.models import Base
# target_metadata = Base.metadata
target_metadata: Any = None
# --------------------------------------------------------------------------

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

db_url = os.getenv("DATABASE_URL", "postgresql+psycopg://clarity:clarity@localhost:5432/clarity")
# Alembic uses sync engines; strip async drivers if present.
sync_url = db_url.replace("+asyncpg", "").replace("+psycopg_async", "+psycopg")
config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=MODULE_SCHEMA,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{MODULE_SCHEMA}"'))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=MODULE_SCHEMA,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
