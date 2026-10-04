"""Persistence ports: the unit of work and the repository (B02, ADR-0013).

Modules keep their state behind these two protocols, never in an attribute of
a service, so the same domain code runs on the in-memory driver (the ``demo``
profile) and on PostgreSQL (``full``, B05) with no branch anywhere.

The repository is deliberately small. A module that needs a domain-shaped
surface declares its own protocol over its own record type and delegates to
one of these; see ``clarity.modules.case.repository``.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from types import TracebackType
from typing import Protocol, Self, runtime_checkable


@runtime_checkable
class Repository[K, V](Protocol):
    """Typed access to one collection of records.

    Reads inside a unit of work see that unit's own uncommitted writes, so a
    service can save a record and read it back before commit.
    """

    def get(self, key: K) -> V | None:
        """The record, or ``None`` when the collection holds no such key."""
        ...

    def put(self, key: K, value: V) -> None:
        """Insert or replace the record under ``key``."""
        ...

    def delete(self, key: K) -> None:
        """Remove the record. Removing an absent key is not an error."""
        ...

    def keys(self) -> list[K]:
        """Every key, in insertion order."""
        ...

    def values(self) -> list[V]:
        """Every record, in insertion order."""
        ...


@runtime_checkable
class UnitOfWork(Protocol):
    """One atomic span of work over any number of collections.

    Nothing a unit of work writes is visible to anyone else until ``commit``.
    Leaving the context manager without committing rolls back, so a failure
    part way through a money path cannot leave half a change behind.
    """

    def repository[K, V](self, collection: str) -> Repository[K, V]:
        """The repository for ``collection``, bound to this unit of work."""
        ...

    def commit(self) -> None:
        """Apply every staged write, or raise ``ConcurrentUpdate``."""
        ...

    def rollback(self) -> None:
        """Discard every staged write."""
        ...

    def as_custodian(self) -> AbstractContextManager[None]:
        """A span in which an append-only collection may be rewritten.

        Append-only is the ordinary rule and this is the named exception to it,
        for the two operations that legitimately replace audit rows: restoring a
        backup, and sealing records into a segment (ADR-0038, ADR-0039). It is a
        context manager rather than a flag so the privilege is visible at the
        call site and bounded by it, and so a reviewer can grep for every place
        that takes it.

        On PostgreSQL the span assumes ``clarity_audit_custodian`` and puts the
        application role back when it ends. ``DELETE`` on an audit table is
        granted to that role alone, and the application role is not a member of
        it, so a request cannot inherit the privilege. The switch is authorised
        against the session user (the database owner), which is the same reason
        a unit of work can assume the application role in the first place. A
        login that is already the application role cannot enter the span. The
        in-memory driver relaxes its own guard for the same span, so both
        profiles accept a restore and refuse an ordinary rewrite.
        """
        ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Opens a new unit of work. The composition root binds the driver."""

    def __call__(self) -> UnitOfWork: ...
