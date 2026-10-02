"""Schema, roles and row-level security for the ``full`` profile (B05).

Written as explicit SQL rather than generated, because what matters here is not
the columns but the guarantees: a role that cannot read another module's schema,
and a policy that filters a customer's rows even when the query forgets to.
Those are the two things the acceptance tests check, and they have to be
readable to be reviewed.

Alembic owns the migration history for the modules' own tables once they have
their own models (ADR-0013). This module creates the generic row store every
repository from B02 shares, which is one table shape per collection.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from clarity.platform.persistence.postgres import SUBSCRIBER_SETTING
from clarity.platform.persistence.schemas import (
    APP_ROLE,
    OWNERS,
    is_customer_scoped,
    owner_of,
    role_of,
    schema_of,
    table_of,
)


def _create_row_table(connection: Connection, collection: str) -> None:
    """One table per collection: the generic row store the repositories use.

    ``sequence`` gives insertion order, which the receipt chain depends on.
    ``version`` is the optimistic concurrency token. ``document`` is the json an
    operator reads; ``value`` is what the repository reconstructs from.
    """
    qualified = f"{schema_of(collection)}.{table_of(collection)}"
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {qualified} (
                key             text PRIMARY KEY,
                value           bytea NOT NULL,
                document        jsonb NOT NULL DEFAULT '{{}}'::jsonb,
                version         integer NOT NULL DEFAULT 1,
                subscriber_ref  text,
                sequence        bigserial NOT NULL,
                created_at      timestamptz NOT NULL DEFAULT now(),
                updated_at      timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS {table_of(collection)}_sequence_idx "
            f"ON {qualified} (sequence)"
        )
    )
    if is_customer_scoped(collection):
        connection.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {table_of(collection)}_subscriber_idx "
                f"ON {qualified} (subscriber_ref)"
            )
        )


def _apply_row_level_security(connection: Connection, collection: str) -> None:
    """Bind a customer-scoped table to the subscriber the request is for.

    ``FORCE`` matters: without it the table owner bypasses its own policy, and
    the application connects as the owner. With it, a query that lost its WHERE
    clause returns nothing rather than every customer's cases (plan 11 §19).

    A row with no subscriber is readable by anyone, which is deliberate: those
    are the sequences and indexes that are not about a person.
    """
    qualified = f"{schema_of(collection)}.{table_of(collection)}"
    connection.execute(text(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY"))
    connection.execute(text(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY"))
    connection.execute(text(f"DROP POLICY IF EXISTS subscriber_isolation ON {qualified}"))
    connection.execute(
        text(
            f"""
            CREATE POLICY subscriber_isolation ON {qualified}
            USING (
                subscriber_ref IS NULL
                OR subscriber_ref = current_setting('{SUBSCRIBER_SETTING}', true)
                OR coalesce(current_setting('{SUBSCRIBER_SETTING}', true), '') = ''
            )
            """
        )
    )


def create_schema(engine: Engine, collections: Iterable[str]) -> None:
    """Create every schema, role, table and policy. Idempotent.

    ``collections`` comes from the composition root (``app.collections``): the
    platform layer provides the seam but must not know which modules exist.
    """
    with engine.begin() as connection:
        for module in sorted(set(OWNERS.values())):
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS clarity_{module}"))
            _create_role(connection, module)

        for collection in collections:
            _create_row_table(connection, collection)
            if is_customer_scoped(collection):
                _apply_row_level_security(connection, collection)

        _grant_each_role_its_own_schema_only(connection)
        _create_application_role(connection)


def _create_role(connection: Connection, module: str) -> None:
    role = role_of(module)
    connection.execute(
        text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    CREATE ROLE {role} NOLOGIN;
                END IF;
            END $$
            """
        )
    )


def _create_application_role(connection: Connection) -> None:
    """The role requests run as: not the owner, so policies apply to it.

    ``NOBYPASSRLS`` is the point. It is a member of every module role, so what
    it can reach is exactly the union of the per-module grants: adding a schema
    the application should not see means not granting it to any module role.
    """
    connection.execute(
        text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    CREATE ROLE {APP_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS INHERIT;
                END IF;
            END $$
            """
        )
    )
    for module in sorted(set(OWNERS.values())):
        connection.execute(text(f"GRANT {role_of(module)} TO {APP_ROLE}"))


def _grant_each_role_its_own_schema_only(connection: Connection) -> None:
    """Each module's role reaches its own schema and nothing else (I6).

    Revoked first, so running this again after a module moves does not leave a
    grant behind that nobody remembers giving.
    """
    for module in sorted(set(OWNERS.values())):
        role = role_of(module)
        for other in sorted(set(OWNERS.values())):
            schema = f"clarity_{other}"
            if other == module:
                connection.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {role}"))
                connection.execute(
                    text(
                        f"GRANT SELECT, INSERT, UPDATE, DELETE "
                        f"ON ALL TABLES IN SCHEMA {schema} TO {role}"
                    )
                )
                connection.execute(
                    text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {role}")
                )
            else:
                connection.execute(text(f"REVOKE ALL ON SCHEMA {schema} FROM {role}"))
                connection.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {role}"))


def drop_schema(engine: Engine) -> None:
    """Remove everything this module created. For tests and local resets."""
    with engine.begin() as connection:
        for module in sorted(set(OWNERS.values())):
            connection.execute(text(f"DROP SCHEMA IF EXISTS clarity_{module} CASCADE"))


def schema_report(engine: Engine) -> dict[str, list[str]]:
    """Which tables exist in which schema. Used by the isolation test."""
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema LIKE 'clarity_%'
                ORDER BY table_schema, table_name
                """
            )
        )
        report: dict[str, list[str]] = {}
        for row in rows:
            report.setdefault(row.table_schema, []).append(row.table_name)
        return report


__all__ = ["create_schema", "drop_schema", "owner_of", "schema_report"]
