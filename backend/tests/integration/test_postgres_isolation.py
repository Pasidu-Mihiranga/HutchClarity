"""Each module's role reaches its own schema only (issue #6, B05; I6).

Data ownership has to be something the database refuses, not something the code
remembers. A module that reads another module's tables is a hidden coupling that
survives every refactor and breaks the moment the modules are deployed apart.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

from clarity.platform.persistence.migrations import schema_report
from clarity.platform.persistence.schemas import OWNERS, role_of, schema_of

CASE_TABLE = "clarity_case.records"
RECEIPT_TABLE = "clarity_receipts.chain"


def test_every_module_owns_a_schema(engine: Engine) -> None:
    report = schema_report(engine)
    for module in sorted(set(OWNERS.values())):
        assert f"clarity_{module}" in report, f"{module} has no schema"


def test_collections_land_in_their_owner_schema() -> None:
    assert schema_of("case.records") == "clarity_case"
    assert schema_of("actions.plans") == "clarity_actions"
    assert schema_of("receipts.chain") == "clarity_receipts"
    assert schema_of("platform.outbox") == "clarity_platform"


# -- acceptance 1: the database refuses a cross-schema read ---------------- #


def test_a_module_role_cannot_read_another_modules_schema(engine: Engine) -> None:
    """The case role queries the receipts schema and is refused."""
    with engine.begin() as connection:
        # Become the case module's role, as a per-module connection would.
        connection.execute(text(f"SET LOCAL ROLE {role_of('case')}"))

        # Its own schema is readable.
        connection.execute(text(f"SELECT count(*) FROM {CASE_TABLE}"))

        with pytest.raises(ProgrammingError) as refused:
            connection.execute(text(f"SELECT count(*) FROM {RECEIPT_TABLE}"))

    message = str(refused.value).lower()
    assert "permission denied" in message, f"expected a permission error, got: {message}"


def test_a_module_role_cannot_write_another_modules_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"SET LOCAL ROLE {role_of('receipts')}"))
        with pytest.raises(ProgrammingError, match=r"(?i)permission denied"):
            connection.execute(text(f"DELETE FROM {CASE_TABLE}"))


def test_no_role_is_granted_a_schema_it_does_not_own(engine: Engine) -> None:
    """Checked as a grant, not as a query, so an unused grant is still caught."""
    leaks: list[str] = []
    with engine.connect() as connection:
        for module in sorted(set(OWNERS.values())):
            role = role_of(module)
            for other in sorted(set(OWNERS.values())):
                if other == module:
                    continue
                granted = connection.execute(
                    text("SELECT has_schema_privilege(:role, :schema, 'USAGE')"),
                    {"role": role, "schema": f"clarity_{other}"},
                ).scalar()
                if granted:
                    leaks.append(f"{role} has USAGE on clarity_{other}")
    assert leaks == [], "a module role reaches a schema it does not own"
