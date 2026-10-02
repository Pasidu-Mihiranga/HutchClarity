"""Typed persistence faults (B02, ADR-0013).

A conflict is a value, not a crash: callers decide whether to retry, refuse or
escalate, so every fault here is a type they can catch.
"""

from __future__ import annotations


class PersistenceError(RuntimeError):
    """Base for every fault raised by a repository or a unit of work."""


class ConcurrentUpdate(PersistenceError):
    """Two units of work changed the same row; the later commit is refused.

    Optimistic concurrency. A unit of work remembers the version it read and
    commit refuses when the stored version has moved on. This is the typed
    conflict the money path needs instead of a silent overwrite: a lost update
    on a plan would mean a second execution of the same remedy.
    """

    def __init__(self, collection: str, key: object, *, expected: int, found: int) -> None:
        super().__init__(
            f"{collection}/{key} changed under this unit of work: "
            f"read version {expected}, found version {found}"
        )
        self.collection = collection
        self.key = key
        self.expected = expected
        self.found = found


class UnitOfWorkClosed(PersistenceError):
    """A unit of work was used after it committed or rolled back."""
