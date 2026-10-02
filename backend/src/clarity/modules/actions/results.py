"""What the tool layer returns and records: data, not capability.

These types are safe to share with every other part of the system, including
the AI and MCP layers. Nothing here can mint a confirmation, spend budget or
execute a plan; that lives in ``capability``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from clarity.contracts.decision import Action, Outcome, PlanStatus

#: Outcomes that may ever result in execution. EXPLAIN_ONLY and HANDOFF cannot.
EXECUTABLE_OUTCOMES = frozenset({Outcome.AUTO_FIX, Outcome.ONE_TAP_FIX, Outcome.STAFF_APPROVAL})


class ConfirmedBy(StrEnum):
    """Who authorised execution. Recorded on the receipt as the actor."""

    CUSTOMER = "customer_confirmed"
    STAFF = "staff_approved"
    SYSTEM = "system_auto_fix"
    """Only ever minted for an AUTO_FIX decision (deck S5 zero-contact)."""


@dataclass(frozen=True)
class ConfirmationToken:
    """Opaque, single-use authority to execute exactly one plan."""

    value: str
    plan_id: str
    confirmed_by: ConfirmedBy
    principal_ref: str
    issued_at: datetime
    expires_at: datetime


@dataclass
class ExecutionResult:
    """What happened when a plan ran."""

    plan_id: str
    actions: list[Action]
    status: PlanStatus
    confirmed_by: ConfirmedBy
    replayed: bool = False
    approver_roles: tuple[str, ...] = ()
    """Roles of the staff who approved, in approval order. Empty unless staff approved."""

    @property
    def succeeded(self) -> bool:
        return self.status is PlanStatus.COMPLETED
