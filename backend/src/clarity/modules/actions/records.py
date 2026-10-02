"""The plan record the tool layer stores.

Separate from the layer so the repository protocol can name the record it
stores without importing the capability code that executes plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from clarity.contracts.decision import ActionPlan, Approval, Decision
from clarity.kernel.common import money
from clarity.modules.actions.budget import Reservation
from clarity.modules.actions.results import ExecutionResult

#: Above this, one approver is not enough (plan section 14.2 four-eyes).
#: PROPOSED TARGET - REQUIRES HUTCH VALIDATION.
FOUR_EYES_THRESHOLD_LKR = money("25000.00")


@dataclass
class PlanRecord:
    """A proposed plan, its approvals, its budget reservation and its outcome."""

    plan: ActionPlan
    decision: Decision
    rule_id: str | None
    approvals: list[Approval] = field(default_factory=list)
    reservation: Reservation | None = None
    result: ExecutionResult | None = None
    idempotency_key: str | None = None
    four_eyes_threshold_lkr: Decimal = FOUR_EYES_THRESHOLD_LKR
    """Resolved from the decision's policy snapshot, so a policy change is enforced here too."""

    @property
    def plan_id(self) -> str:
        return self.plan.plan_id


__all__ = ["FOUR_EYES_THRESHOLD_LKR", "PlanRecord"]
