"""Request and response bodies for the `/v1` API (plan §17.1).

These are deliberately separate from the domain models. A channel sees a
customer-facing view — cause, evidence, what will happen — and never the
internal plumbing like policy input hashes or adapter references.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from clarity.schemas.common import Channel, Completeness, EventSource, Language, Money
from clarity.schemas.decision import ActionType, Outcome


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #


class OpenCaseRequest(ApiModel):
    msisdn: str = Field(description="Customer number in any Sri Lankan format.")
    channel: Channel = Channel.WEB
    language: Language = Language.EN
    charge_ref: str | None = Field(
        default=None, description="Set when the customer tapped Why? on one charge."
    )
    customer_requested_human: bool = False


class CaseSummary(ApiModel):
    case_id: str
    case_no: str
    state: str
    channel: Channel
    language: Language
    msisdn_masked: str
    money_at_stake_lkr: Money | None = None
    opened_at: datetime


class TimelineEventView(ApiModel):
    event_id: str
    source: EventSource
    event_type: str
    occurred_at: datetime
    amount_lkr: Money | None = None
    attributes: dict[str, object] = Field(default_factory=dict)


class SourceStatusView(ApiModel):
    source: EventSource
    completeness: Completeness
    event_count: int
    note: str | None = None


class TimelineView(ApiModel):
    case_id: str
    window_from: datetime
    window_to: datetime
    snapshot_hash: str
    events: list[TimelineEventView]
    sources: list[SourceStatusView]


# --------------------------------------------------------------------------- #
# Decisions
# --------------------------------------------------------------------------- #


class CauseView(ApiModel):
    rule_id: str
    rule_version: int
    confidence: float
    category: str | None = None
    money_effect_lkr: Money | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class RuledOutView(ApiModel):
    rule_id: str
    reason: str | None = None


class DecisionView(ApiModel):
    """What the customer or agent is told, and why."""

    case_id: str
    decision_id: str
    outcome: Outcome
    amount_lkr: Money | None = None
    cause: CauseView | None = None
    ruled_out: list[RuledOutView] = Field(default_factory=list)
    unknown: list[RuledOutView] = Field(
        default_factory=list,
        description="Rules that could not be evaluated because evidence was missing.",
    )
    allowed_actions: list[ActionType] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    handoff_reason: str | None = None
    policy_version: str
    explanation: str = Field(
        default="",
        description="Customer-facing wording. Verified against the facts before it is sent.",
    )
    explanation_source: str = Field(
        default="template", description="Which tier produced it (deck S14)."
    )
    requires_confirmation: bool
    requires_approval: bool


# --------------------------------------------------------------------------- #
# Plans and execution
# --------------------------------------------------------------------------- #


class ProposeRequest(ApiModel):
    created_by: str = Field(default="channel:web", description="Proposing principal.")
    action_types: list[ActionType] | None = Field(
        default=None, description="Narrow the remedy. It can never be widened."
    )


class PlanView(ApiModel):
    plan_id: str
    case_id: str
    outcome: Outcome
    summary: str
    actions: list[ActionType]
    total_amount_lkr: Money
    status: str


class ApproveRequest(ApiModel):
    """Who approves and whether they stepped up come from the token.

    Neither is accepted here: a caller that could name its own approver could
    satisfy four-eyes alone, and one that could assert its own step-up would
    make the approval audit worthless.
    """

    plan_id: str
    role: str
    """Which of the caller's own roles they are approving in."""


class ConfirmRequest(ApiModel):
    plan_id: str


class ActionView(ApiModel):
    action_id: str
    type: ActionType
    amount_lkr: Money | None = None
    before: dict[str, str] = Field(default_factory=dict)
    after: dict[str, str] = Field(default_factory=dict)
    status: str


class ExecutionView(ApiModel):
    case_id: str
    plan_id: str
    status: str
    confirmed_by: str
    actions: list[ActionView]
    receipt_id: str | None = None
    verify_url: str | None = None


class PendingApprovalView(ApiModel):
    """Returned when one approver is not enough (four-eyes)."""

    case_id: str
    plan_id: str
    status: str = "AWAITING_SECOND_APPROVAL"
    detail: str


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #


class VerificationView(ApiModel):
    receipt_id: str
    status: str
    valid: bool
    reason: str
    key_id: str | None = None
    chain_ok: bool = False
    superseded_by: str | None = None
    issued_at: str | None = None
    number: str | None = None
    corrected_lkr: str | None = None
    safeguard: str | None = None
    recurrence_test: str | None = None


# --------------------------------------------------------------------------- #
# Desk
# --------------------------------------------------------------------------- #


class QueueItem(ApiModel):
    """A case waiting for a person, ordered by money at stake (deck S9)."""

    case_id: str
    case_no: str
    state: str
    outcome: Outcome | None = None
    cause: str | None = None
    money_at_stake_lkr: Money | None = None
    msisdn_masked: str
    channel: Channel
    reason: str | None = None
    plan_id: str | None = None


class DemoSubscriber(ApiModel):
    """Prototype only: the synthetic customers the demo ships with."""

    name: str
    msisdn: str
    masked: str
    language: Language
    balance_lkr: Money
    scenario: str


# --------------------------------------------------------------------------- #
# Sign in
# --------------------------------------------------------------------------- #


class OtpRequest(ApiModel):
    msisdn: str


class OtpVerify(ApiModel):
    challenge_id: str
    code: str
    channel: Channel = Channel.WEB


class StaffSignIn(ApiModel):
    """Development staff sign-in. **Simulated**: production federates HUTCH SSO."""

    user_ref: str
    roles: list[str]
    step_up: bool = Field(
        default=False,
        description="Simulates recent MFA, which approvals above the cap require.",
    )


class SessionView(ApiModel):
    token: str
    expires_at: datetime | None = None
    subject: str
    roles: list[str] = Field(default_factory=list)
    assurance: str
    permissions: list[str] = Field(default_factory=list)
