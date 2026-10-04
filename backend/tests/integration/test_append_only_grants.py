"""The database refuses an audit rewrite (audit assurance plan W1, ADR-0034).

`tests/security/test_append_only.py` proves Clarity's own code cannot overwrite
an audit record. This proves the layer underneath: that the writing role does not
hold the privilege, so an attacker who reaches the application, or a future
version of this code that forgets, is refused by PostgreSQL rather than by a
convention.

Skips without a database, so `make check` stays infrastructure-free (ADR-0006)
and a green `make check` never implies these ran.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

from clarity.platform.audit.ledger import AUDIT, AUDIT_HEAD
from clarity.platform.persistence.migrations import append_only_report
from clarity.platform.persistence.schemas import (
    APPEND_ONLY,
    CUSTODIAN_ROLE,
    owner_of,
    role_of,
    schema_of,
    table_of,
)


def qualified(collection: str) -> str:
    return f"{schema_of(collection)}.{table_of(collection)}"


def test_the_writing_role_holds_insert_and_select_only(engine: Engine) -> None:
    """The acceptance test for W1, read back from the database itself.

    Read from `information_schema` rather than from what the migration believes
    it did: a grant that silently did not apply is exactly the failure this is
    for.
    """
    report = append_only_report(engine)

    assert set(report) == set(APPEND_ONLY), "every append-only table is reported"
    for collection, privileges in report.items():
        assert "UPDATE" not in privileges, f"{collection}: the writing role can still UPDATE"
        assert "DELETE" not in privileges, f"{collection}: the writing role can still DELETE"
        assert "INSERT" in privileges, f"{collection}: appending must still work"
        assert "SELECT" in privileges, f"{collection}: reading must still work"


def test_an_ordinary_table_keeps_update_and_delete(engine: Engine) -> None:
    """Append-only is for the trail, not a new rule for every table."""
    role = role_of(owner_of("case.records"))
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT privilege_type FROM information_schema.table_privileges
                WHERE table_schema = :schema AND table_name = :table AND grantee = :role
                """
            ),
            {"schema": schema_of("case.records"), "table": table_of("case.records"), "role": role},
        )
        privileges = {row.privilege_type for row in rows}

    assert {"SELECT", "INSERT", "UPDATE", "DELETE"} <= privileges


def test_the_head_pointer_keeps_update(engine: Engine) -> None:
    """It moves on every append, so revoking UPDATE there would stop the trail."""
    role = role_of(owner_of(AUDIT_HEAD))
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT privilege_type FROM information_schema.table_privileges
                WHERE table_schema = :schema AND table_name = :table AND grantee = :role
                """
            ),
            {"schema": schema_of(AUDIT_HEAD), "table": table_of(AUDIT_HEAD), "role": role},
        )
        privileges = {row.privilege_type for row in rows}

    assert "UPDATE" in privileges


def test_an_update_is_refused_under_the_writing_role(engine: Engine) -> None:
    """Not just absent from a catalogue: actually refused when attempted."""
    role = role_of(owner_of(AUDIT))
    with engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO {qualified(AUDIT)} (key, value, document, version) "
                "VALUES ('k1', '\\x00'::bytea, '{}'::jsonb, 1)"
            )
        )
    with pytest.raises(ProgrammingError, match="permission denied"), engine.begin() as connection:
        connection.execute(text(f"SET LOCAL ROLE {role}"))
        connection.execute(text(f"UPDATE {qualified(AUDIT)} SET version = 2 WHERE key = 'k1'"))


def test_a_delete_is_refused_under_the_writing_role(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO {qualified(AUDIT)} (key, value, document, version) "
                "VALUES ('k2', '\\x00'::bytea, '{}'::jsonb, 1)"
            )
        )
    role = role_of(owner_of(AUDIT))
    with pytest.raises(ProgrammingError, match="permission denied"), engine.begin() as connection:
        connection.execute(text(f"SET LOCAL ROLE {role}"))
        connection.execute(text(f"DELETE FROM {qualified(AUDIT)} WHERE key = 'k2'"))


def test_the_custodian_role_may_delete(engine: Engine) -> None:
    """Restore and archival need it, and they are the only things that do."""
    with engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO {qualified(AUDIT)} (key, value, document, version) "
                "VALUES ('k3', '\\x00'::bytea, '{}'::jsonb, 1)"
            )
        )
    with engine.begin() as connection:
        connection.execute(text(f"SET LOCAL ROLE {CUSTODIAN_ROLE}"))
        connection.execute(text(f"DELETE FROM {qualified(AUDIT)} WHERE key = 'k3'"))


def test_the_application_role_is_not_a_member_of_the_custodian(engine: Engine) -> None:
    """Otherwise the separation is decorative: a request could inherit DELETE."""
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT 1 FROM pg_auth_members m
                JOIN pg_roles granted ON granted.oid = m.roleid
                JOIN pg_roles member ON member.oid = m.member
                WHERE granted.rolname = :custodian AND member.rolname = 'clarity_app'
                """
            ),
            {"custodian": CUSTODIAN_ROLE},
        ).all()

    assert rows == [], "clarity_app must not inherit the custodian's DELETE"
