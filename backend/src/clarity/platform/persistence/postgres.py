"""PostgreSQL persistence driver for the ``full`` profile (B05, ADR-0013).

The same ports as the in-memory driver, and it passes the same parity suite
(``tests/contract/test_repository_parity.py``), so a module cannot tell which
one it was given.

What the database does that the in-memory driver only models:

**One transaction per unit of work.** ``commit`` and ``rollback`` are the real
thing, so a half-applied money path is impossible rather than merely avoided.

**Optimistic concurrency across processes.** Every row carries a version. A
commit refuses when the version it read has moved on, which is the same
``ConcurrentUpdate`` the in-memory driver raises, except that it now holds
between two API replicas rather than two threads.

**Ownership the database enforces.** One schema and one role per module, and a
role is granted nothing outside its own schema (I6). Row-level security binds
customer-scoped tables to the subscriber the request is for, so a query that
loses its filter returns nothing instead of another customer's case.

Rows are stored as ``jsonb`` with the Python value pickled alongside. The json
is what makes a row readable in ``psql`` and queryable by an operator; the
pickle is what round-trips a domain object exactly, including ``Decimal``
amounts, which is what I3 requires on a money path.
"""

from __future__ import annotations

import pickle
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Self

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from clarity.platform.persistence.errors import ConcurrentUpdate, UnitOfWorkClosed
from clarity.platform.persistence.ports import Repository
from clarity.platform.persistence.schemas import (
    APP_ROLE,
    OWNERS,
    is_customer_scoped,
    role_of,
    schema_of,
    table_of,
)

#: Set per transaction and read by the row-level security policies.
SUBSCRIBER_SETTING = "clarity.subscriber_ref"

#: How long a statement waits for a row another transaction holds.
#:
#: This is why the driver can pass the same parity suite as the in-memory one.
#: PostgreSQL is pessimistic: a conflicting write takes a row lock and waits,
#: where the in-memory driver is optimistic and refuses at commit. Waiting
#: forever on a money path is the worse failure, so the wait is bounded and a
#: timeout becomes the same ``ConcurrentUpdate`` the other driver raises. The
#: port's promise is a typed conflict rather than a silent overwrite; which
#: statement surfaces it is a driver detail.
DEFAULT_LOCK_TIMEOUT_MS = 250

#: SQLSTATEs that mean "another transaction is changing this row".
_CONFLICT_STATES = frozenset(
    {
        "55P03",  # lock_not_available: the lock_timeout above expired
        "40001",  # serialization_failure
        "40P01",  # deadlock_detected
        "23505",  # unique_violation: two inserts of one key
    }
)


def _qualified(collection: str) -> str:
    return f"{schema_of(collection)}.{table_of(collection)}"


class PostgresStore:
    """The engine and the schema. One per process, built by the composition root."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @property
    def engine(self) -> Engine:
        return self._engine

    def unit(
        self,
        *,
        subscriber_ref: str | None = None,
        lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS,
    ) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(
            self._engine, subscriber_ref=subscriber_ref, lock_timeout_ms=lock_timeout_ms
        )

    def truncate_all(self, collections: Iterable[str]) -> None:
        """Empty the given tables. For tests, never for a deployment."""
        with self._engine.begin() as connection:
            for collection in collections:
                connection.execute(text(f"TRUNCATE {_qualified(collection)}"))


class PostgresUnitOfWork:
    """A unit of work over one database transaction."""

    def __init__(
        self,
        engine: Engine,
        *,
        subscriber_ref: str | None = None,
        lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS,
    ) -> None:
        self._connection: Connection = engine.connect()
        self._transaction = self._connection.begin()
        self._baselines: dict[tuple[str, Any], int] = {}
        #: Keys this unit wrote or deleted. A write to a row that already
        #: existed takes a row lock held until commit, so nobody else can have
        #: changed it. A write to a row that did **not** exist takes no such
        #: lock, so two units can both insert and the later upsert would
        #: silently overwrite the earlier one: those are still version checked.
        self._written: set[tuple[str, Any]] = set()
        self._closed = False
        self._connection.execute(text(f"SET LOCAL lock_timeout = '{lock_timeout_ms}ms'"))
        # Requests run as the application role, never as the database owner: an
        # owner or superuser bypasses row-level security, which would make the
        # policies decorative. LOCAL, so it ends with this transaction.
        self._connection.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
        if subscriber_ref is not None:
            # Bound for this transaction only, so it cannot leak to the next
            # request on a pooled connection.
            self._connection.execute(
                text("SELECT set_config(:name, :value, true)"),
                {"name": SUBSCRIBER_SETTING, "value": subscriber_ref},
            )

    # -- the UnitOfWork port ---------------------------------------------- #

    def repository[K, V](self, collection: str) -> Repository[K, V]:
        return _PostgresRepository[K, V](self, collection)

    def commit(self) -> None:
        self._guard()
        try:
            self._verify_versions()
            self._transaction.commit()
        except Exception:
            self._transaction.rollback()
            raise
        finally:
            self._close()

    def rollback(self) -> None:
        if self._closed:
            return
        self._transaction.rollback()
        self._close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self._closed:
            self.rollback()

    # -- what a repository bound to this unit of work calls ---------------- #

    def read(self, collection: str, key: Any) -> Any | None:
        self._guard()
        row = self._connection.execute(
            text(f"SELECT value, version FROM {_qualified(collection)} WHERE key = :key"),
            {"key": str(key)},
        ).one_or_none()
        self._remember(collection, key, None if row is None else int(row.version))
        return None if row is None else pickle.loads(row.value)

    def write(self, collection: str, key: Any, value: Any) -> None:
        self._guard()
        self._remember_current(collection, key)
        with self._conflicts_are_typed(collection, key):
            self._write(collection, key, value)
        self._written.add((collection, key))

    def _write(self, collection: str, key: Any, value: Any) -> None:
        self._connection.execute(
            text(
                f"""
                INSERT INTO {_qualified(collection)} (key, value, document, version, subscriber_ref)
                VALUES (:key, :value, :document, 1, :subscriber_ref)
                ON CONFLICT (key) DO UPDATE
                   SET value = :value,
                       document = :document,
                       version = {_qualified(collection)}.version + 1,
                       updated_at = now()
                """
            ),
            {
                "key": str(key),
                "value": pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL),
                "document": _readable(value),
                "subscriber_ref": self._subscriber_of(collection, value),
            },
        )

    def remove(self, collection: str, key: Any) -> None:
        self._guard()
        self._remember_current(collection, key)
        with self._conflicts_are_typed(collection, key):
            self._connection.execute(
                text(f"DELETE FROM {_qualified(collection)} WHERE key = :key"), {"key": str(key)}
            )
        self._written.add((collection, key))

    @contextmanager
    def _conflicts_are_typed(self, collection: str, key: Any) -> Iterator[None]:
        """Turn the database's way of saying "someone else has this row" into
        the port's ``ConcurrentUpdate``, and close the unit of work.

        A failed statement aborts the whole PostgreSQL transaction, so there is
        nothing left to commit: closing here means a caller sees the same
        "retry in a fresh unit of work" shape it gets from the other driver.
        """
        try:
            yield
        except DBAPIError as error:
            state = getattr(error.orig, "sqlstate", None)
            if state not in _CONFLICT_STATES:
                raise
            self._transaction.rollback()
            self._close()
            raise ConcurrentUpdate(collection, key, expected=0, found=0) from error

    def all_keys(self, collection: str) -> list[Any]:
        self._guard()
        rows = self._connection.execute(
            text(f"SELECT key FROM {_qualified(collection)} ORDER BY sequence")
        )
        return [row.key for row in rows]

    # -- internals -------------------------------------------------------- #

    def _subscriber_of(self, collection: str, value: Any) -> str | None:
        """The subscriber a customer-scoped row belongs to.

        Read from the value rather than taken from the caller, so a row cannot
        be filed under a subscriber the record does not belong to.
        """
        if not is_customer_scoped(collection):
            return None
        for attribute in ("subscriber_ref", "subject"):
            found = getattr(value, attribute, None)
            if isinstance(found, str) and found:
                return found
        nested = getattr(value, "event", None)
        subject = getattr(nested, "subject", None)
        return subject if isinstance(subject, str) and subject else None

    def _remember(self, collection: str, key: Any, version: int | None) -> None:
        self._baselines.setdefault((collection, key), version or 0)

    def _remember_current(self, collection: str, key: Any) -> None:
        if (collection, key) in self._baselines:
            return
        row = self._connection.execute(
            text(f"SELECT version FROM {_qualified(collection)} WHERE key = :key"),
            {"key": str(key)},
        ).one_or_none()
        self._remember(collection, key, None if row is None else int(row.version))

    def _verify_versions(self) -> None:
        """Refuse the commit if a row this unit decided on has moved under it.

        Three cases, and only one of them needs no check:

        **Read, not written.** The classic read-then-decide: this unit read a
        value, decided from it, and another transaction changed it meanwhile.
        PostgreSQL will not catch that at this isolation level, so the version
        has to match what was read.

        **Written over a row that existed.** Skipped. The write took a row lock
        held until commit, so no other transaction could change it; a competing
        writer met that lock and was already refused.

        **Written where no row existed.** Checked, and this is the one that
        matters most. There is no row to lock, so two units can each find the
        key absent and both insert. Whichever commits second would have its
        upsert quietly overwrite the first, which for a claim ("execute this
        plan only if nobody has") means the plan runs twice. So the inserter
        must find the version at exactly 1: its own. A 2 means somebody else
        inserted first and this unit overwrote them.
        """
        for (collection, key), baseline in self._baselines.items():
            written = (collection, key) in self._written
            if written and baseline > 0:
                continue
            expected = 1 if written else baseline
            row = self._connection.execute(
                text(f"SELECT version FROM {_qualified(collection)} WHERE key = :key"),
                {"key": str(key)},
            ).one_or_none()
            found = 0 if row is None else int(row.version)
            if written and found == 0:
                # This unit deleted a key that never existed. Nothing happened.
                continue
            if found != expected:
                raise ConcurrentUpdate(collection, key, expected=expected, found=found)

    def _close(self) -> None:
        self._baselines.clear()
        self._written.clear()
        self._closed = True
        self._connection.close()

    def _guard(self) -> None:
        if self._closed:
            raise UnitOfWorkClosed("this unit of work has already committed or rolled back")


def _readable(value: Any) -> str:
    """A json rendering for an operator reading the table, best effort.

    Never used to reconstruct the value: the pickle is authoritative, so a type
    that does not serialise cleanly costs legibility, not correctness.
    """
    import json

    dump = getattr(value, "model_dump_json", None)
    if callable(dump):
        rendered: str = dump()
        return rendered
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps({"repr": repr(value)})


class _PostgresRepository[K, V]:
    """The ``Repository`` port over one table."""

    def __init__(self, unit: PostgresUnitOfWork, collection: str) -> None:
        self._unit = unit
        self._collection = collection

    def get(self, key: K) -> V | None:
        found: V | None = self._unit.read(self._collection, key)
        return found

    def put(self, key: K, value: V) -> None:
        self._unit.write(self._collection, key, value)

    def delete(self, key: K) -> None:
        self._unit.remove(self._collection, key)

    def keys(self) -> list[K]:
        found: list[K] = self._unit.all_keys(self._collection)
        return found

    def values(self) -> list[V]:
        return [value for key in self.keys() if (value := self.get(key)) is not None]


class PostgresAutocommitRepository[K, V]:
    """A repository that wraps each call in its own transaction.

    The counterpart of the in-memory ``AutocommitRepository``, for the state a
    service changes one record at a time.
    """

    def __init__(self, store: PostgresStore, collection: str) -> None:
        self._store = store
        self._collection = collection

    @contextmanager
    def _repository(self) -> Iterator[tuple[PostgresUnitOfWork, Repository[K, V]]]:
        with self._store.unit() as unit:
            yield unit, unit.repository(self._collection)

    def get(self, key: K) -> V | None:
        with self._repository() as (_, repository):
            return repository.get(key)

    def put(self, key: K, value: V) -> None:
        with self._repository() as (unit, repository):
            repository.put(key, value)
            unit.commit()

    def delete(self, key: K) -> None:
        with self._repository() as (unit, repository):
            repository.delete(key)
            unit.commit()

    def keys(self) -> list[K]:
        with self._repository() as (_, repository):
            return repository.keys()

    def values(self) -> list[V]:
        with self._repository() as (_, repository):
            return repository.values()


__all__ = [
    "OWNERS",
    "SUBSCRIBER_SETTING",
    "PostgresAutocommitRepository",
    "PostgresStore",
    "PostgresUnitOfWork",
    "role_of",
]
