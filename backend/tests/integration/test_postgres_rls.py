"""Row-level security binds a request to its subscriber (issue #6, B05).

The point is what happens when the application is *wrong*. A filter that the
code forgets, or a bug that drops a WHERE clause, must return nothing rather
than another customer's case. That is a guarantee the database makes and the
application cannot undo (plan 11 section 19).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from clarity.platform.persistence.postgres import SUBSCRIBER_SETTING, PostgresStore
from clarity.platform.persistence.schemas import APP_ROLE

CASES = "case.records"
CASE_TABLE = "clarity_case.records"

DILANI = "sub_dilani"
NIMAL = "sub_nimal"


@dataclass(frozen=True)
class _Case:
    """Stands in for a case record. ``subscriber_ref`` is what RLS filters on."""

    case_id: str
    subscriber_ref: str
    state: str = "OPEN"


def _seed(store: PostgresStore) -> None:
    """Two customers' cases, each written under its own subscriber."""
    for subscriber, case_id in ((DILANI, "CASE-D1"), (DILANI, "CASE-D2"), (NIMAL, "CASE-N1")):
        with store.unit(subscriber_ref=subscriber) as unit:
            unit.repository(CASES).put(case_id, _Case(case_id, subscriber))
            unit.commit()


# -- acceptance 2: a lost filter returns nothing, not someone else's rows -- #


def test_a_query_that_loses_its_filter_sees_only_this_subscriber(
    store: PostgresStore, engine: Engine
) -> None:
    _seed(store)

    with engine.begin() as connection:
        # As the application runs: the owner and any superuser bypass RLS, so a
        # test that connected as one would pass with no policy at all.
        connection.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
        connection.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": SUBSCRIBER_SETTING, "value": DILANI},
        )
        # Deliberately unfiltered: this is the bug the policy has to survive.
        rows = connection.execute(text(f"SELECT key FROM {CASE_TABLE}")).all()

    keys = sorted(row.key for row in rows)
    assert keys == ["CASE-D1", "CASE-D2"], "Nimal's case must not be visible to Dilani"


def test_the_repository_sees_only_the_bound_subscriber(store: PostgresStore) -> None:
    """The same guarantee through the port a module actually uses."""
    _seed(store)

    with store.unit(subscriber_ref=NIMAL) as unit:
        assert sorted(unit.repository(CASES).keys()) == ["CASE-N1"]
        assert unit.repository(CASES).get("CASE-D1") is None, "another customer's case"


def test_a_subscriber_cannot_read_another_by_asking_for_the_key(store: PostgresStore) -> None:
    """Knowing the id is not authority: the policy filters by row, not by query."""
    _seed(store)

    with store.unit(subscriber_ref=DILANI) as unit:
        assert unit.repository(CASES).get("CASE-N1") is None


def test_an_unbound_unit_of_work_sees_everything(store: PostgresStore) -> None:
    """Background work (the relay, reconciliation) is not scoped to one customer.

    Deliberate: the policy is a safety net for request-scoped code, not an
    authorisation model. Who may open an unbound unit of work is decided by the
    permission on the route (I9), which is a separate control.
    """
    _seed(store)

    with store.unit() as unit:
        assert sorted(unit.repository(CASES).keys()) == ["CASE-D1", "CASE-D2", "CASE-N1"]


def test_the_binding_does_not_outlive_its_transaction(store: PostgresStore) -> None:
    """Connections are pooled, so a leaked binding would scope the next request."""
    _seed(store)

    with store.unit(subscriber_ref=DILANI) as unit:
        assert sorted(unit.repository(CASES).keys()) == ["CASE-D1", "CASE-D2"]

    # A later unit on a recycled connection must start unbound.
    with store.unit() as unit:
        assert len(unit.repository(CASES).keys()) == 3


def test_a_bound_request_cannot_write_a_row_for_another_subscriber(
    store: PostgresStore,
) -> None:
    """The policy checks writes as well as reads, which is the stronger promise.

    The subscriber is read from the record, not from the caller, so a request
    bound to Nimal that tries to store Dilani's case is refused by the database.
    A request that could write rows it cannot read would be a way to plant data
    under another customer.
    """
    with store.unit(subscriber_ref=NIMAL) as unit, pytest.raises(DBAPIError) as refused:
        unit.repository(CASES).put("CASE-X", _Case("CASE-X", DILANI))

    assert "row-level security" in str(refused.value).lower()

    with store.unit() as unit:
        assert unit.repository(CASES).get("CASE-X") is None, "nothing was written"


def test_an_unbound_request_may_write_any_subscribers_row(store: PostgresStore) -> None:
    """Background work writes on behalf of many customers: the relay, seeding."""
    with store.unit() as unit:
        unit.repository(CASES).put("CASE-Y", _Case("CASE-Y", DILANI))
        unit.commit()

    with store.unit(subscriber_ref=DILANI) as unit:
        assert unit.repository(CASES).get("CASE-Y") is not None
