"""In-memory repositories for tests (issue #5, B02).

A test builds the same seam the composition root builds, so it exercises the
real repository code rather than a dict that no production path uses. Pass a
shared ``MemoryStore`` when two collaborators must see each other's writes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from clarity.integration.ports import CommandPort
from clarity.modules.actions.capability import PLANS, StoredPlanRepository, ToolLayer
from clarity.modules.actions.confirmation import ConfirmationService
from clarity.modules.case.public import CASE_SEQUENCE, CASES, StoredCaseRepository
from clarity.modules.governance.public import CHANGES, StoredPolicyChangeRepository
from clarity.modules.receipts.public import (
    BY_PLAN,
    RECEIPT_SEQUENCE,
    RECEIPTS,
    SUBSCRIBERS,
    SUPERSEDED,
    StoredReceiptRepository,
)
from clarity.platform.persistence import (
    AutocommitRepository,
    MemoryStore,
    MemoryUnitOfWork,
    UnitOfWork,
)


def plan_repository(store: MemoryStore | None = None) -> StoredPlanRepository:
    return StoredPlanRepository(AutocommitRepository(store or MemoryStore(), PLANS))


def case_repository(store: MemoryStore | None = None) -> StoredCaseRepository:
    shared = store or MemoryStore()
    return StoredCaseRepository(
        AutocommitRepository(shared, CASES),
        AutocommitRepository(shared, CASE_SEQUENCE),
    )


def receipt_repository(store: MemoryStore | None = None) -> StoredReceiptRepository:
    shared = store or MemoryStore()
    return StoredReceiptRepository(
        AutocommitRepository(shared, RECEIPTS),
        AutocommitRepository(shared, SUPERSEDED),
        AutocommitRepository(shared, SUBSCRIBERS),
        AutocommitRepository(shared, RECEIPT_SEQUENCE),
        AutocommitRepository(shared, BY_PLAN),
    )


def change_repository(store: MemoryStore | None = None) -> StoredPolicyChangeRepository:
    return StoredPolicyChangeRepository(AutocommitRepository(store or MemoryStore(), CHANGES))


def units(store: MemoryStore) -> Callable[[], UnitOfWork]:
    """A unit-of-work factory over one store, as the composition root builds."""
    return lambda: MemoryUnitOfWork(store)


def confirmations(store: MemoryStore | None = None, **kwargs: Any) -> ConfirmationService:
    """A confirmation service over a store, as the composition root builds one."""
    return ConfirmationService(units(store or MemoryStore()), **kwargs)


def tool_layer(
    command_port: CommandPort, *, store: MemoryStore | None = None, **kwargs: Any
) -> ToolLayer:
    """A tool layer with its persistence wired the way the container wires it.

    Plans and the outbox share one store, which is what makes completing a plan
    and writing its ``action.completed`` event one transaction (B06).
    """
    shared = store or MemoryStore()
    return ToolLayer(command_port, plans=plan_repository(shared), open_unit=units(shared), **kwargs)


__all__ = [
    "case_repository",
    "change_repository",
    "confirmations",
    "plan_repository",
    "receipt_repository",
    "tool_layer",
    "units",
]
