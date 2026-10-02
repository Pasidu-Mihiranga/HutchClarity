"""Causes, decisions and actions - the deterministic half of Clarity.

Nothing in this module may be produced by a language model. Causes come from
versioned rule packs, outcomes from the decision policy, and amounts from the
evidence. The LLM reads these as facts and writes prose about them (deck S7).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import (
    ActionSafetyLevel,
    ClarityModel,
    Money,
    ensure_utc,
    utc_now,
)


class ActionType(StrEnum):
    """Everything Clarity can do to a customer's account.

    Each type carries a fixed safety level (:data:`ACTION_SAFETY`) and a
    reversibility flag used by the decision policy.
    """

    REFUND = "REFUND"
    DEACTIVATE_VAS = "DEACTIVATE_VAS"
    BLOCK_MERCHANT_UNTIL_OPTIN = "BLOCK_MERCHANT_UNTIL_OPTIN"
    SET_SPEND_CAP = "SET_SPEND_CAP"
    ENABLE_DATA_STOP = "ENABLE_DATA_STOP"
    ENABLE_FUP_ALERTS = "ENABLE_FUP_ALERTS"
    CREATE_SUPPORT_CASE = "CREATE_SUPPORT_CASE"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"


#: Safety level per action (plan §10.4). L3 actions move money or change a paid
#: service and are never executed by an LLM.
ACTION_SAFETY: dict[ActionType, ActionSafetyLevel] = {
    ActionType.REFUND: ActionSafetyLevel.L3_FINANCIAL,
    ActionType.DEACTIVATE_VAS: ActionSafetyLevel.L3_FINANCIAL,
    ActionType.BLOCK_MERCHANT_UNTIL_OPTIN: ActionSafetyLevel.L3_FINANCIAL,
    ActionType.SET_SPEND_CAP: ActionSafetyLevel.L2_LOW_RISK,
    ActionType.ENABLE_DATA_STOP: ActionSafetyLevel.L2_LOW_RISK,
    ActionType.ENABLE_FUP_ALERTS: ActionSafetyLevel.L2_LOW_RISK,
    ActionType.CREATE_SUPPORT_CASE: ActionSafetyLevel.L2_LOW_RISK,
    ActionType.SEND_NOTIFICATION: ActionSafetyLevel.L2_LOW_RISK,
}

#: Actions that only return money and change no service. Auto-fix is restricted
#: to these (deck S7: "Money back only").
MONEY_BACK_ONLY: frozenset[ActionType] = frozenset({ActionType.REFUND})


class Outcome(StrEnum):
    """The five outcomes of the decision matrix (deck S7, plan §14.2)."""

    AUTO_FIX = "AUTO_FIX"
    ONE_TAP_FIX = "ONE_TAP_FIX"
    STAFF_APPROVAL = "STAFF_APPROVAL"
    EXPLAIN_ONLY = "EXPLAIN_ONLY"
    HANDOFF = "HANDOFF"


class HandoffReason(StrEnum):
    """Why a case went to a human. Counted, not guessed (deck S10)."""

    EVIDENCE_INCOMPLETE = "evidence_incomplete"
    LOW_CONFIDENCE = "low_confidence"
    FRAUD_RISK = "fraud_risk"
    CUSTOMER_REQUESTED = "customer_requested"
    VERIFIER_FAILED = "verifier_failed"
    NO_CAUSE_FOUND = "no_cause_found"
    CONFLICTING_CAUSES = "conflicting_causes"
    COMPENSATION_REQUIRED = "compensation_required"


class CauseAssessment(ClarityModel):
    """One rule's verdict on a case."""

    rule_id: str
    rule_version: int
    matched: bool
    confidence: Decimal = Field(ge=0, le=1)
    evidence_complete: bool = Field(
        default=True,
        description="False when a source this rule requires could not be read. "
        "Such a rule is indeterminate, not 'did not match', and forces a handoff.",
    )
    category: str | None = None
    money_effect_lkr: Money | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    allowed_actions: list[ActionType] = Field(default_factory=list)
    safeguard: ActionType | None = None
    recurrence_check: str | None = None
    reason: str | None = Field(
        default=None,
        description="Why this rule did not match, shown to the customer as 'ruled out'.",
    )

    @property
    def ref(self) -> str:
        """Stable ``RULE_ID@version`` reference recorded on every decision."""
        return f"{self.rule_id}@{self.rule_version}"


class RiskSignals(ClarityModel):
    """Risk inputs to the decision policy (plan §14.1).

    ``sim_swap_days`` is ``None`` when the identity source could not answer;
    the policy treats an unknown signal conservatively.
    """

    sim_swap_days: int | None = None
    fraud_flag: bool = False
    refunds_last_30d: int = 0
    customer_requested_human: bool = False


class BudgetState(ClarityModel):
    """Remaining refund budget at decision time (plan §14.4)."""

    global_remaining_lkr: Money
    rule_remaining_lkr: Money | None = None

    def allows(self, amount: Decimal) -> bool:
        if self.global_remaining_lkr < amount:
            return False
        return not (self.rule_remaining_lkr is not None and self.rule_remaining_lkr < amount)


class DecisionInput(ClarityModel):
    """The exact document the policy evaluated.

    Hashing this makes "policy what-if" an exact replay: the same input and a
    candidate policy version reproduce a comparable outcome (deck S9).
    """

    case_id: str
    snapshot_hash: str
    evidence_complete: bool
    top_cause_ref: str | None
    top_confidence: Decimal
    margin: Decimal = Field(
        description="Confidence gap to the runner-up cause; small means conflicting causes."
    )
    amount_lkr: Money
    money_back_only: bool
    rule_auto_whitelisted: bool
    disclosed_to_customer: bool = Field(
        default=False,
        description="True when the cause is a rule the customer saw at purchase (FUP).",
    )
    risk: RiskSignals
    budget: BudgetState
    channel_supports_confirmation: bool = True
    as_of: datetime | None = Field(
        default=None,
        description="When the disputed event happened. Policy is resolved for "
        "this moment, so a customer is judged by the rules that applied then.",
    )

    @property
    def input_hash(self) -> str:
        return hash_payload(self.model_dump(mode="json"))


class Decision(ClarityModel):
    """The policy's verdict, with everything needed to reproduce it."""

    decision_id: str
    case_id: str
    outcome: Outcome
    policy_version: str
    input_hash: str
    allowed_actions: list[ActionType] = Field(default_factory=list)
    amount_lkr: Money | None = None
    top_cause_ref: str | None = None
    ruled_out: list[CauseAssessment] = Field(default_factory=list)
    handoff_reason: HandoffReason | None = None
    config_snapshot_hash: str | None = Field(
        default=None,
        description="Hash of the policy values this decision used, so a replay "
        "can reproduce it under the thresholds that applied at the time.",
    )
    as_of: datetime | None = Field(
        default=None,
        description="The moment policy was evaluated at: the disputed event's "
        "time, not the time the case was opened.",
    )
    rationale: list[str] = Field(
        default_factory=list,
        description="Deterministic reasons for this outcome, for staff and audit.",
    )
    decided_at: datetime = Field(default_factory=utc_now)

    @field_validator("decided_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _handoff_has_reason(self) -> Decision:
        if self.outcome is Outcome.HANDOFF and self.handoff_reason is None:
            raise ValueError("a HANDOFF decision must record a handoff_reason")
        if self.outcome is not Outcome.HANDOFF and self.handoff_reason is not None:
            raise ValueError("handoff_reason is only valid on a HANDOFF decision")
        return self

    @property
    def requires_customer_confirmation(self) -> bool:
        return self.outcome is Outcome.ONE_TAP_FIX

    @property
    def requires_staff_approval(self) -> bool:
        return self.outcome is Outcome.STAFF_APPROVAL


class ActionStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"


class Action(ClarityModel):
    """A executed (or attempted) change, with before/after for the receipt."""

    action_id: str
    decision_id: str
    case_id: str
    type: ActionType
    safety_level: ActionSafetyLevel
    amount_lkr: Money | None = None
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    status: ActionStatus = ActionStatus.PENDING
    adapter_ref: str | None = None
    error_code: str | None = None
    executed_at: datetime | None = None

    @field_validator("executed_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)


class PlanStatus(StrEnum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    COMPENSATED = "COMPENSATED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PlanStep(ClarityModel):
    """One action inside a plan, with its amount already fixed by the decision."""

    action_type: ActionType
    safety_level: ActionSafetyLevel
    amount_lkr: Money | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ActionPlan(ClarityModel):
    """An intent to act - never self-executing (plan §10.5).

    This is the only thing an LLM can produce on the money path. The remedy
    for one cause is a single plan ("refund + switch off + block merchant"),
    so the customer confirms the whole thing in one tap (deck S7), and
    execution needs a confirmation token the model never sees.
    """

    plan_id: str
    case_id: str
    decision_id: str
    outcome: Outcome
    steps: list[PlanStep] = Field(min_length=1)
    status: PlanStatus = PlanStatus.PENDING_CONFIRMATION
    created_by: str = Field(description="Principal that proposed, e.g. 'mcp:customer-assist'.")
    display_summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None

    @field_validator("created_at", "expires_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @property
    def total_amount_lkr(self) -> Decimal:
        """What this plan will move in total. Used for budget and caps."""
        return sum(
            (step.amount_lkr for step in self.steps if step.amount_lkr is not None),
            Decimal("0.00"),
        )

    @property
    def action_types(self) -> list[ActionType]:
        return [step.action_type for step in self.steps]


class Approval(ClarityModel):
    """Staff approval record. The maker can never be the checker (plan §14.4)."""

    approval_id: str
    action_id: str
    approver_ref: str
    role: str
    decision: str = Field(pattern="^(approved|rejected)$")
    mfa_step_up: bool = False
    at: datetime = Field(default_factory=utc_now)

    @field_validator("at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)
