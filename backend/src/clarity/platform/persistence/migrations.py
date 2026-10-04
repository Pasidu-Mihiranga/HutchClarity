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
    APPEND_ONLY,
    CUSTODIAN_ROLE,
    OWNERS,
    is_append_only,
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
        _make_append_only_tables_append_only(connection, collections)


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


def _make_append_only_tables_append_only(
    connection: Connection, collections: Iterable[str]
) -> None:
    """Take UPDATE and DELETE away from the writing role on the audit tables (W1).

    This is the part a hash chain cannot do. The chain makes an edit *visible*
    afterwards; this makes it fail at the moment it is attempted, by the database,
    under the role requests actually run as. An attacker who reaches the
    application still cannot rewrite a record, and does not get the chance to
    recompute a chain around it.

    Two things make it possible now and not before.

    The write path for these collections no longer upserts (``is_append_only`` in
    the PostgreSQL driver). A statement carrying ``ON CONFLICT DO UPDATE`` needs
    the ``UPDATE`` privilege whether or not it ever updates anything, so revoking
    it would have broken every append rather than only a rewrite. That is exactly
    why this step sat blocked.

    And the operations that *do* legitimately remove audit rows, restoring a
    backup and sealing a segment, get a role of their own. ``CUSTODIAN_ROLE``
    holds ``DELETE``; the application role is deliberately **not** a member of it.
    ``as_custodian`` assumes that role with ``SET LOCAL ROLE`` for the span and
    puts the application role back afterwards. ``SET ROLE`` is checked against
    the session user, so the database owner can assume it and a connection that
    logged in as ``clarity_app`` cannot. The custodian also receives the
    sequences those inserts use, and ``SELECT``, ``INSERT``, ``UPDATE`` and
    ``DELETE`` on the two pointer tables, because a restore rewrites the head
    and archival rewrites the floor inside the same span. The pointers hold no
    history. The plan's wording is precise and worth keeping: revoke from the
    *writing* role.
    """
    connection.execute(
        text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{CUSTODIAN_ROLE}') THEN
                    CREATE ROLE {CUSTODIAN_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS INHERIT;
                END IF;
            END $$
            """
        )
    )
    for collection in collections:
        if not is_append_only(collection):
            continue
        table = f"{schema_of(collection)}.{table_of(collection)}"
        role = role_of(owner_of(collection))
        connection.execute(text(f"REVOKE UPDATE, DELETE ON {table} FROM {role}"))
        # Granted explicitly rather than left to the schema-wide grant above,
        # which this has just narrowed.
        connection.execute(text(f"GRANT SELECT, INSERT ON {table} TO {role}"))
        connection.execute(
            text(f"GRANT USAGE ON SCHEMA {schema_of(collection)} TO {CUSTODIAN_ROLE}")
        )
        connection.execute(text(f"GRANT SELECT, INSERT, DELETE ON {table} TO {CUSTODIAN_ROLE}"))
        _grant_sequence(connection, table)

    # Head and floor are pointers. Restore and archival rewrite them while the
    # transaction is the custodian, so the application role's grants are not in
    # force for those statements. They are not append-only and hold no history.
    present = set(collections)
    for collection in ("platform.audit_head", "platform.audit_floor"):
        if collection not in present:
            continue
        table = f"{schema_of(collection)}.{table_of(collection)}"
        connection.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {CUSTODIAN_ROLE}")
        )
        _grant_sequence(connection, table)


def _grant_sequence(connection: Connection, table: str) -> None:
    """Let the custodian insert into ``table``.

    A ``bigserial`` column draws its default from a sequence owned by the table
    owner. ``INSERT`` without naming that column calls ``nextval``, which the
    custodian cannot do until it holds ``USAGE``.
    """
    sequence = connection.execute(
        text("SELECT pg_get_serial_sequence(:table, 'sequence')"),
        {"table": table},
    ).scalar_one()
    connection.execute(text(f"GRANT USAGE, SELECT ON SEQUENCE {sequence} TO {CUSTODIAN_ROLE}"))


def append_only_report(engine: Engine) -> dict[str, set[str]]:
    """Which privileges the writing role actually holds on each append-only table.

    Read back from ``information_schema`` rather than from what the migration
    believes it did: a grant that silently did not apply is the failure this is
    for, and the integration test asserts on this.
    """
    report: dict[str, set[str]] = {}
    with engine.begin() as connection:
        for collection in sorted(APPEND_ONLY):
            role = role_of(owner_of(collection))
            rows = connection.execute(
                text(
                    """
                    SELECT privilege_type FROM information_schema.table_privileges
                    WHERE table_schema = :schema AND table_name = :table AND grantee = :role
                    """
                ),
                {
                    "schema": schema_of(collection),
                    "table": table_of(collection),
                    "role": role,
                },
            )
            report[collection] = {row.privilege_type for row in rows}
    return report


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
