"""Repository parity suite (issue #5, B02; ADR-0013; plan 21 section 11.6).

One contract for the persistence seam, which every driver must pass. The
in-memory driver is listed today; the PostgreSQL driver (B05) is added to
``DRIVERS`` and must pass the same assertions unchanged. A driver that cannot
is a finding about that driver, found here rather than in production.

The two behaviours the money path depends on are a rollback that leaves no
trace and a conflicting commit that raises instead of overwriting: a lost
update on a plan would mean the same remedy executed twice.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass

import pytest

from clarity.platform.persistence import (
    ConcurrentUpdate,
    MemoryStore,
    MemoryUnitOfWork,
    Repository,
    UnitOfWork,
    UnitOfWorkClosed,
)

# Real collection names: the PostgreSQL driver maps a collection to the schema
# of the module that owns it, so a made-up name would have no table.
CASES = "case.records"
PLANS = "actions.plans"


@dataclass(frozen=True)
class _Case:
    """Stand-in for a case record: the suite tests the seam, not the domain."""

    case_id: str
    state: str


@dataclass(frozen=True)
class _Plan:
    plan_id: str
    status: str


def _memory_driver() -> Iterator[Callable[[], UnitOfWork]]:
    store = MemoryStore()
    yield lambda: MemoryUnitOfWork(store)


def _postgres_driver() -> Iterator[Callable[[], UnitOfWork]]:
    """The ``full`` profile driver (B05). Skipped unless a database is configured."""
    url = os.environ.get("CLARITY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("set CLARITY_TEST_DATABASE_URL to run the suite against PostgreSQL")

    from sqlalchemy import create_engine

    from clarity.app.collections import ALL_COLLECTIONS
    from clarity.platform.persistence.migrations import create_schema, drop_schema
    from clarity.platform.persistence.postgres import PostgresStore, PostgresUnitOfWork

    engine = create_engine(url, future=True)
    # A fresh schema per test, so one test cannot read another's rows or
    # inherit its versions.
    drop_schema(engine)
    create_schema(engine, ALL_COLLECTIONS)
    store = PostgresStore(engine)

    # Several tests in this suite deliberately leave a unit of work open, to
    # show that a write is invisible before commit. On a real connection that
    # leaves a transaction holding locks, and teardown's DROP SCHEMA would wait
    # for it forever. So every unit handed out is tracked and rolled back here.
    opened: list[PostgresUnitOfWork] = []

    def open_tracked(**kwargs: object) -> PostgresUnitOfWork:
        unit = store.unit(**kwargs)  # type: ignore[arg-type]
        opened.append(unit)
        return unit

    try:
        yield open_tracked
    finally:
        for unit in opened:
            with suppress(Exception):
                unit.rollback()
        engine.dispose()
        drop_schema(engine)
        engine.dispose()


#: driver name -> a factory of unit-of-work factories, one fresh store each.
DRIVERS: dict[str, Callable[[], Iterator[Callable[[], UnitOfWork]]]] = {
    "memory": _memory_driver,
    "postgres": _postgres_driver,
}


@pytest.fixture(params=sorted(DRIVERS), ids=sorted(DRIVERS))
def open_unit(request: pytest.FixtureRequest) -> Iterator[Callable[[], UnitOfWork]]:
    yield from DRIVERS[request.param]()


Open = Callable[[], UnitOfWork]


def _cases(unit: UnitOfWork) -> Repository[str, _Case]:
    return unit.repository(CASES)


def _plans(unit: UnitOfWork) -> Repository[str, _Plan]:
    return unit.repository(PLANS)


# -- acceptance 1: a rollback leaves nothing behind ---------------------- #


def test_a_rolled_back_case_does_not_exist(open_unit: Open) -> None:
    with open_unit() as unit:
        _cases(unit).put("CASE-1", _Case("CASE-1", "OPEN"))
        unit.rollback()

    with open_unit() as unit:
        assert _cases(unit).get("CASE-1") is None
        assert _cases(unit).keys() == []


def test_leaving_without_commit_rolls_back(open_unit: Open) -> None:
    """The safe default: an exception part way through writes nothing."""
    with pytest.raises(ValueError, match="halfway"), open_unit() as unit:
        _cases(unit).put("CASE-2", _Case("CASE-2", "OPEN"))
        raise ValueError("halfway through the money path")

    with open_unit() as unit:
        assert _cases(unit).get("CASE-2") is None


def test_a_committed_case_is_readable_afterwards(open_unit: Open) -> None:
    with open_unit() as unit:
        _cases(unit).put("CASE-3", _Case("CASE-3", "RESOLVED"))
        unit.commit()

    with open_unit() as unit:
        stored = _cases(unit).get("CASE-3")
        assert stored is not None
        assert stored.state == "RESOLVED"


# -- acceptance 2: the second writer is refused, never silently overwritten #


def _conflict_between(
    write_loser: Callable[[], None],
    commit_winner: Callable[[], None],
    loser: UnitOfWork,
) -> ConcurrentUpdate:
    """Drive a two-writer race and return the conflict the loser is given.

    The drivers detect a conflict at different moments and both honour the port:

    - in memory, optimistically: the loser's write is staged and the refusal
      comes at its commit, once the winner's commit has moved the version on;
    - in PostgreSQL, pessimistically: the loser's write meets the row lock the
      winner still holds, waits out ``lock_timeout`` and is refused there.

    So this tries the write, then the winner's commit, then the loser's commit,
    and reports whichever refusal arrives. What the port promises is a typed
    conflict instead of a silent overwrite; which statement raises it is a
    driver detail, and pinning that detail would mean two suites instead of one.
    """
    try:
        write_loser()
    except ConcurrentUpdate as at_write:
        commit_winner()
        return at_write

    commit_winner()
    try:
        loser.commit()
    except ConcurrentUpdate as at_commit:
        return at_commit
    raise AssertionError("the losing writer was allowed to overwrite silently")


def test_two_units_of_work_updating_one_plan_conflict(open_unit: Open) -> None:
    with open_unit() as unit:
        _plans(unit).put("PLAN-1", _Plan("PLAN-1", "PENDING_CONFIRMATION"))
        unit.commit()

    first, second = open_unit(), open_unit()
    # Both read the same version, then both try to move the plan on.
    assert _plans(first).get("PLAN-1") is not None
    assert _plans(second).get("PLAN-1") is not None
    _plans(first).put("PLAN-1", _Plan("PLAN-1", "EXECUTED"))

    conflict = _conflict_between(
        lambda: _plans(second).put("PLAN-1", _Plan("PLAN-1", "CANCELLED")),
        first.commit,
        second,
    )
    assert conflict.collection == PLANS
    assert conflict.key == "PLAN-1"

    # The first writer's change stands: no silent overwrite either way.
    with open_unit() as unit:
        stored = _plans(unit).get("PLAN-1")
        assert stored is not None
        assert stored.status == "EXECUTED"


def test_two_units_of_work_inserting_one_key_conflict(open_unit: Open) -> None:
    """Insert against insert is a conflict too, not a last-writer-wins race."""
    first, second = open_unit(), open_unit()
    _plans(first).put("PLAN-2", _Plan("PLAN-2", "EXECUTED"))

    _conflict_between(
        lambda: _plans(second).put("PLAN-2", _Plan("PLAN-2", "CANCELLED")),
        first.commit,
        second,
    )

    with open_unit() as unit:
        stored = _plans(unit).get("PLAN-2")
        assert stored is not None
        assert stored.status == "EXECUTED"


def test_untouched_rows_do_not_conflict(open_unit: Open) -> None:
    """Concurrency is per row: two units of work on different plans both pass."""
    first, second = open_unit(), open_unit()
    _plans(first).put("PLAN-3", _Plan("PLAN-3", "EXECUTED"))
    _plans(second).put("PLAN-4", _Plan("PLAN-4", "EXECUTED"))

    first.commit()
    second.commit()

    with open_unit() as unit:
        assert sorted(_plans(unit).keys()) == ["PLAN-3", "PLAN-4"]


# -- the rest of the contract -------------------------------------------- #


def test_a_unit_of_work_reads_its_own_writes(open_unit: Open) -> None:
    with open_unit() as unit:
        _cases(unit).put("CASE-4", _Case("CASE-4", "OPEN"))
        stored = _cases(unit).get("CASE-4")
        assert stored is not None
        assert stored.state == "OPEN"
        stored_keys = _cases(unit).keys()
        assert "CASE-4" in stored_keys


def test_writes_are_invisible_until_commit(open_unit: Open) -> None:
    writer, reader = open_unit(), open_unit()
    _cases(writer).put("CASE-5", _Case("CASE-5", "OPEN"))
    assert _cases(reader).get("CASE-5") is None
    writer.commit()


def test_keys_and_values_keep_insertion_order(open_unit: Open) -> None:
    """The receipt chain is ordered, so the seam must preserve order."""
    with open_unit() as unit:
        for index in range(5):
            _cases(unit).put(f"CASE-{index}", _Case(f"CASE-{index}", "OPEN"))
        unit.commit()

    with open_unit() as unit:
        assert _cases(unit).keys() == [f"CASE-{index}" for index in range(5)]
        assert [case.case_id for case in _cases(unit).values()] == [
            f"CASE-{index}" for index in range(5)
        ]


def test_delete_removes_the_record(open_unit: Open) -> None:
    with open_unit() as unit:
        _cases(unit).put("CASE-6", _Case("CASE-6", "OPEN"))
        unit.commit()

    with open_unit() as unit:
        _cases(unit).delete("CASE-6")
        assert _cases(unit).get("CASE-6") is None
        unit.commit()

    with open_unit() as unit:
        assert _cases(unit).get("CASE-6") is None
        assert _cases(unit).keys() == []


def test_deleting_an_absent_key_is_not_an_error(open_unit: Open) -> None:
    with open_unit() as unit:
        _cases(unit).delete("CASE-NONE")
        unit.commit()


def test_a_rolled_back_delete_keeps_the_record(open_unit: Open) -> None:
    with open_unit() as unit:
        _cases(unit).put("CASE-7", _Case("CASE-7", "OPEN"))
        unit.commit()

    with open_unit() as unit:
        _cases(unit).delete("CASE-7")
        unit.rollback()

    with open_unit() as unit:
        assert _cases(unit).get("CASE-7") is not None


def test_collections_are_isolated_from_each_other(open_unit: Open) -> None:
    with open_unit() as unit:
        _cases(unit).put("SAME-ID", _Case("SAME-ID", "OPEN"))
        _plans(unit).put("SAME-ID", _Plan("SAME-ID", "EXECUTED"))
        unit.commit()

    with open_unit() as unit:
        case = _cases(unit).get("SAME-ID")
        plan = _plans(unit).get("SAME-ID")
        assert isinstance(case, _Case)
        assert isinstance(plan, _Plan)


def test_a_closed_unit_of_work_refuses_further_use(open_unit: Open) -> None:
    unit = open_unit()
    _cases(unit).put("CASE-8", _Case("CASE-8", "OPEN"))
    unit.commit()
    with pytest.raises(UnitOfWorkClosed):
        _cases(unit).get("CASE-8")
    with pytest.raises(UnitOfWorkClosed):
        unit.commit()


def test_a_refused_unit_of_work_is_closed(open_unit: Open) -> None:
    """A conflict stages nothing: the caller opens a fresh unit and retries."""
    first, second = open_unit(), open_unit()
    _plans(first).put("PLAN-5", _Plan("PLAN-5", "EXECUTED"))

    _conflict_between(
        lambda: _plans(second).put("PLAN-5", _Plan("PLAN-5", "CANCELLED")),
        first.commit,
        second,
    )

    with pytest.raises(UnitOfWorkClosed):
        second.commit()
