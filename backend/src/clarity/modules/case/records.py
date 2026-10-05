"""The case record and the faults a case operation can raise.

Separate from the service so the repository protocol can name the record it
stores without importing the service that uses it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from clarity.contracts.case import Case
from clarity.contracts.decision import ActionPlan, Decision, DecisionInput
from clarity.contracts.receipt import TrustReceipt
from clarity.contracts.timeline import EvidenceSnapshot
from clarity.modules.actions.public import ExecutionResult
from clarity.modules.decision.public import PolicyThresholds
from clarity.modules.detection.public import RuleEvaluation


class CaseNotFound(KeyError):
    pass


class CaseNotReady(RuntimeError):
    """An operation was attempted before the case reached the needed state."""


@dataclass(frozen=True)
class HandoffRequest:
    """The customer's conversation asked for a person (`conversation.turn.completed`).

    Queue and reason are stable codes from the conversation module; no message
    text is kept here, the transcript stays with the conversation.
    """

    queue: str
    reason: str | None
    turn_no: int
    requested_at: datetime


@dataclass
class CaseRecord:
    """Everything known about one case, in one place."""

    case: Case
    subscriber_ref: str
    snapshot: EvidenceSnapshot | None = None
    evaluation: RuleEvaluation | None = None
    decision: Decision | None = None
    decision_input: DecisionInput | None = None
    """Kept so the case can be re-decided under a candidate policy (section 19 4.1)."""
    plans: dict[str, ActionPlan] = field(default_factory=dict)
    execution: ExecutionResult | None = None
    receipt: TrustReceipt | None = None
    receipts_by_plan: dict[str, TrustReceipt] = field(default_factory=dict)
    """The one receipt each executed plan produced; replays return it (D1)."""
    thresholds: PolicyThresholds | None = None
    """The thresholds the decision used, so execution enforces the same values (D2)."""
    handoff: HandoffRequest | None = None
    """Set when the conversation handed the case to a person; the desk lists it.
    A class-level default, so records stored before this field read as None."""

    @property
    def case_id(self) -> str:
        return self.case.case_id


__all__ = ["CaseNotFound", "CaseNotReady", "CaseRecord", "HandoffRequest"]
