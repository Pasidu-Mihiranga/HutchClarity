"""Where policy change artefacts live (B02, ADR-0013).

Policy changes are auditable records, not runtime state: they outlive the
process that proposed them, so they sit behind a repository.
"""

from __future__ import annotations

from typing import Protocol

from clarity.modules.governance.artefacts import PolicyChange
from clarity.platform.persistence import Repository

#: Collection name the drivers use. One collection is one table in B05.
CHANGES = "governance.changes"


class PolicyChangeRepository(Protocol):
    """Proposed, approved and active policy changes."""

    def get(self, change_id: str) -> PolicyChange | None: ...

    def save(self, change: PolicyChange) -> None: ...

    def all_changes(self) -> list[PolicyChange]:
        """Every change, in the order they were proposed."""
        ...


class StoredPolicyChangeRepository:
    """``PolicyChangeRepository`` over any persistence driver."""

    def __init__(self, changes: Repository[str, PolicyChange]) -> None:
        self._changes = changes

    def get(self, change_id: str) -> PolicyChange | None:
        return self._changes.get(change_id)

    def save(self, change: PolicyChange) -> None:
        self._changes.put(change.change_id, change)

    def all_changes(self) -> list[PolicyChange]:
        return self._changes.values()


__all__ = [
    "CHANGES",
    "PolicyChangeRepository",
    "StoredPolicyChangeRepository",
]
