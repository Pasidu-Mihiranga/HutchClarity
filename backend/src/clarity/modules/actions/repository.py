"""Where plan state lives (B02, ADR-0013).

The tool layer owns no dict of plans: they sit behind this protocol, so the
money path can be moved to PostgreSQL with row locks (B05, M-ACT) without the
layer changing.
"""

from __future__ import annotations

from typing import Protocol

from clarity.modules.actions.records import PlanRecord
from clarity.platform.persistence import Repository

#: Collection name the drivers use. One collection is one table in B05.
PLANS = "actions.plans"


class PlanRepository(Protocol):
    """Plans and their approvals, reservations and outcomes."""

    def get(self, plan_id: str) -> PlanRecord | None:
        """The record, or ``None`` when no plan has that id."""
        ...

    def save(self, record: PlanRecord) -> None:
        """Insert or replace the record."""
        ...

    def all_records(self) -> list[PlanRecord]:
        """Every plan, in the order the plans were proposed."""
        ...


class StoredPlanRepository:
    """``PlanRepository`` over any persistence driver."""

    def __init__(self, plans: Repository[str, PlanRecord]) -> None:
        self._plans = plans

    def get(self, plan_id: str) -> PlanRecord | None:
        return self._plans.get(plan_id)

    def save(self, record: PlanRecord) -> None:
        self._plans.put(record.plan_id, record)

    def all_records(self) -> list[PlanRecord]:
        return self._plans.values()


__all__ = ["PLANS", "PlanRepository", "StoredPlanRepository"]
