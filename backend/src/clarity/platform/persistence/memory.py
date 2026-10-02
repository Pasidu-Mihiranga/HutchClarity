"""In-memory persistence driver for the ``demo`` profile (B02, ADR-0014).

The store is the whole database: one dict per collection, each row carrying a
version so a unit of work can tell that someone else changed the row while it
was open. It is the parity reference for the PostgreSQL driver (B05): both
pass ``tests/contract/test_repository_parity.py``.

Simulated: this driver keeps data in the process and loses it on restart. It
exists so a reviewer can run Clarity with no infrastructure.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

from clarity.platform.persistence.errors import ConcurrentUpdate, UnitOfWorkClosed
from clarity.platform.persistence.ports import Repository

_Key = tuple[str, Any]


@dataclass(frozen=True, slots=True)
class _Row:
    """A stored record and the version it is on."""

    value: Any
    version: int


@dataclass(slots=True)
class _Staged:
    """A write waiting for commit. ``deleted`` stages a removal."""

    value: Any = None
    deleted: bool = False


class MemoryStore:
    """Shared backing store. One per process, built by the composition root."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[Any, _Row]] = {}
        self._lock = threading.RLock()

    def row(self, collection: str, key: Any) -> _Row | None:
        with self._lock:
            return self._rows.get(collection, {}).get(key)

    def keys(self, collection: str) -> list[Any]:
        with self._lock:
            return list(self._rows.get(collection, {}))

    def apply(self, staged: dict[_Key, _Staged], baselines: dict[_Key, int]) -> None:
        """Commit one unit of work: check every version, then write.

        The check and the write happen under one lock, so two units of work
        committing at the same moment cannot both pass the check.
        """
        with self._lock:
            for (collection, key), expected in baselines.items():
                current = self._rows.get(collection, {}).get(key)
                found = current.version if current is not None else 0
                if found != expected:
                    raise ConcurrentUpdate(collection, key, expected=expected, found=found)
            for (collection, key), entry in staged.items():
                rows = self._rows.setdefault(collection, {})
                if entry.deleted:
                    rows.pop(key, None)
                    continue
                previous = rows.get(key)
                version = previous.version + 1 if previous is not None else 1
                rows[key] = _Row(value=entry.value, version=version)

    def clear(self) -> None:
        """Drop everything. Used by ``Clarity.reset`` and by tests."""
        with self._lock:
            self._rows.clear()


class MemoryUnitOfWork:
    """A unit of work over a ``MemoryStore``."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store
        self._staged: dict[_Key, _Staged] = {}
        self._baselines: dict[_Key, int] = {}
        self._closed = False

    # -- the UnitOfWork port --------------------------------------------- #

    def repository[K, V](self, collection: str) -> Repository[K, V]:
        return _MemoryRepository[K, V](self, collection)

    def commit(self) -> None:
        self._guard()
        try:
            self._store.apply(self._staged, self._baselines)
        finally:
            self._staged.clear()
            self._baselines.clear()
            self._closed = True

    def rollback(self) -> None:
        self._staged.clear()
        self._baselines.clear()
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # Leaving without an explicit commit discards the work: a half-applied
        # money path is worse than no change at all.
        if not self._closed:
            self.rollback()

    # -- what a repository bound to this unit of work calls --------------- #

    def read(self, collection: str, key: Any) -> Any | None:
        self._guard()
        staged = self._staged.get((collection, key))
        if staged is not None:
            return None if staged.deleted else staged.value
        row = self._store.row(collection, key)
        self._remember(collection, key, row)
        return None if row is None else row.value

    def write(self, collection: str, key: Any, value: Any) -> None:
        self._guard()
        self._remember(collection, key, self._store.row(collection, key))
        self._staged[(collection, key)] = _Staged(value=value)

    def remove(self, collection: str, key: Any) -> None:
        self._guard()
        self._remember(collection, key, self._store.row(collection, key))
        self._staged[(collection, key)] = _Staged(deleted=True)

    def all_keys(self, collection: str) -> list[Any]:
        self._guard()
        committed = self._store.keys(collection)
        staged = [key for (name, key) in self._staged if name == collection]
        ordered = committed + [key for key in staged if key not in set(committed)]
        return [
            key
            for key in ordered
            if not (entry := self._staged.get((collection, key))) or not entry.deleted
        ]

    # -- internals ------------------------------------------------------- #

    def _remember(self, collection: str, key: Any, row: _Row | None) -> None:
        """Record the version first seen for this key; later reads keep it."""
        self._baselines.setdefault((collection, key), 0 if row is None else row.version)

    def _guard(self) -> None:
        if self._closed:
            raise UnitOfWorkClosed("this unit of work has already committed or rolled back")


class _MemoryRepository[K, V]:
    """The ``Repository`` port over one collection of one unit of work."""

    def __init__(self, unit: MemoryUnitOfWork, collection: str) -> None:
        self._unit = unit
        self._collection = collection

    def get(self, key: K) -> V | None:
        value: V | None = self._unit.read(self._collection, key)
        return value

    def put(self, key: K, value: V) -> None:
        self._unit.write(self._collection, key, value)

    def delete(self, key: K) -> None:
        self._unit.remove(self._collection, key)

    def keys(self) -> list[K]:
        found: list[K] = self._unit.all_keys(self._collection)
        return found

    def values(self) -> list[V]:
        return [value for key in self.keys() if (value := self.get(key)) is not None]


class AutocommitRepository[K, V]:
    """A repository that wraps each call in its own unit of work.

    For state a service owns alone and changes one record at a time, which is
    every collection the prototype kept in a dict. It keeps business state in
    the store (so a driver swap is all that B05 needs) without inventing
    transaction boundaries the domain does not have yet: the money path gets
    explicit ones in B04 and M-ACT.
    """

    def __init__(self, store: MemoryStore, collection: str) -> None:
        self._store = store
        self._collection = collection

    def get(self, key: K) -> V | None:
        with MemoryUnitOfWork(self._store) as unit:
            repository: Repository[K, V] = unit.repository(self._collection)
            return repository.get(key)

    def put(self, key: K, value: V) -> None:
        with MemoryUnitOfWork(self._store) as unit:
            repository: Repository[K, V] = unit.repository(self._collection)
            repository.put(key, value)
            unit.commit()

    def delete(self, key: K) -> None:
        with MemoryUnitOfWork(self._store) as unit:
            repository: Repository[K, V] = unit.repository(self._collection)
            repository.delete(key)
            unit.commit()

    def keys(self) -> list[K]:
        with MemoryUnitOfWork(self._store) as unit:
            repository: Repository[K, V] = unit.repository(self._collection)
            return repository.keys()

    def values(self) -> list[V]:
        with MemoryUnitOfWork(self._store) as unit:
            repository: Repository[K, V] = unit.repository(self._collection)
            return repository.values()
