"""Request and response bodies for the `/v1` API (plan §17.1).

These are deliberately separate from the domain models. A channel sees a
customer-facing view - cause, evidence, what will happen - and never the
internal plumbing like policy input hashes or adapter references.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clarity.contracts.decision import ActionType, Outcome
from clarity.kernel.common import Channel, Completeness, EventSource, Language, Money


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
    audit_anchor_seq: int | None = Field(
        default=None,
        description=(
            "The audit checkpoint this receipt witnesses (ADR-0035). None on a "
            "schema 1.0 receipt, or one issued before any checkpoint was signed."
        ),
    )
    audit_anchor_ok: bool | None = Field(
        default=None,
        description=(
            "Whether that checkpoint's signature verifies. None when the receipt "
            "carries no anchor, which is not the same as an anchor that failed."
        ),
    )


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
    """Development staff sign-in. **Simulated**: production federates HUTCH SSO.

    Closed with 404 once ``CLARITY_STAFF_DIRECTORY`` is set. The browser must
    not choose a role.
    """

    user_ref: str
    roles: list[str]
    step_up: bool = Field(
        default=False,
        description="Simulates recent MFA, which approvals above the cap require.",
    )


class StaffLogin(ApiModel):
    """Username and password. The directory assigns the role. **Simulated** staff."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)
    step_up_code: str = Field(
        default="",
        max_length=64,
        description="Empty signs in at ordinary MFA. A code raises assurance to recent MFA.",
    )


class ReloadRequest(ApiModel):
    amount_lkr: str


class SafeguardRequest(ApiModel):
    kind: str
    value: str


class FamilyRequest(ApiModel):
    msisdn: str


class PreferencesRequest(ApiModel):
    language: Language
    notify: str = "important"
    large_text: bool = False


class SessionView(ApiModel):
    token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    subject: str
    roles: list[str] = Field(default_factory=list)
    assurance: str
    permissions: list[str] = Field(default_factory=list)


class RefreshRequest(ApiModel):
    refresh_token: str = Field(min_length=20)


class SwitchFlipRequest(ApiModel):
    """Flip a kill switch. Requires ``flags:kill_switch``."""

    key: str
    enabled: bool
    reason: str = Field(min_length=1)


class PolicyDraftRequest(ApiModel):
    key: str
    value: Any
    scope: dict[str, str] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    reason: str = Field(min_length=1)


class PolicyReviewRequest(ApiModel):
    cases_evaluated: int = Field(ge=0)
    candidate_summary: str = ""


class PolicyScheduleRequest(ApiModel):
    effective_from: datetime


class PolicyRollbackRequest(ApiModel):
    reason: str = Field(min_length=1)


class MerchantSuspendRequest(ApiModel):
    """Demo merchant block for VAS ops / compliance. Simulated world only."""

    merchant_id: str
    reason: str = Field(min_length=1)
    subscriber_msisdn: str | None = None


# --------------------------------------------------------------------------- #
# Audit access (audit assurance plan Phase 3)
# --------------------------------------------------------------------------- #


class AuditGrantRequest(ApiModel):
    """Ask for an audit duty for someone else. A second person approves it."""

    subject_kind: str = Field(description="user | role")
    subject_ref: str = Field(description="A staff user_ref, or a role name.")
    permission: str = Field(description="audit:read | audit:export | alert:dispose")
    reason: str
    duration: str = Field(description="ISO 8601 duration, e.g. P30D. At most the policy maximum.")


class AuditGrantRevoke(ApiModel):
    reason: str


class BreakGlassRequest(ApiModel):
    """An admin's immediate, short, self-granted audit duty. Always recorded."""

    permission: str
    reason: str


class AlertDisposal(ApiModel):
    """Close an alert. A reason is always required."""

    disposition: str = Field(description="confirmed | false_positive | accepted_risk")
    reason: str


# --------------------------------------------------------------------------- #
# Foresight (C4, F06)
# --------------------------------------------------------------------------- #


class ScenarioDraftRequest(ApiModel):
    """A change to rehearse.

    ``effective_date`` is required because the whole run resolves policy as of
    it: a rehearsal is about a change that lands on a day, so the parameters it
    uses are the ones in force on that day (C1).
    """

    name: str = Field(min_length=1, max_length=200)
    change_type: str = Field(description="One of the ChangeType values, e.g. pack_retired.")
    effective_date: date
    affected_share: Decimal = Field(default=Decimal("1.0"), ge=0, le=1)
    severity: Decimal = Field(default=Decimal("1.0"), gt=0, le=10)
    affected_products: list[str] = Field(default_factory=list, max_length=50)
    business_context: str = Field(default="", max_length=2000)


class ScenarioReviseRequest(ScenarioDraftRequest):
    """The next version of an existing scenario family.

    The whole scenario, not a patch: a version is a complete statement of what
    is being rehearsed, and a partial update would leave a reader of version 2
    reconstructing it from version 1.
    """


class ForesightRunRequest(ApiModel):
    """Ask for a rehearsal of one scenario version."""

    scenario_version_id: str = Field(min_length=1)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)


class LaunchRecordRequest(ApiModel):
    """Record that a rehearsed change shipped."""

    scenario_version_id: str = Field(min_length=1)
    provenance: str = Field(
        default="synthetic",
        description=(
            "synthetic or real. Recording a real launch is refused until the "
            "capability and evidence checks land (C6)."
        ),
    )
    evidence_ref: str | None = Field(default=None, max_length=200)
    note: str = Field(default="", max_length=2000)


class OutcomeRecordRequest(ApiModel):
    """One observed theme-segment band for a launch."""

    theme: str = Field(min_length=1, max_length=200)
    segment: str = Field(min_length=1, max_length=200)
    band: str = Field(description="low, medium or high.")


class CandidateConfirmRequest(ApiModel):
    """What a person decides a cluster means (C7).

    The theme, the segment and the band all come from the caller. A cluster
    says complaints look like one cause; it does not say which rehearsed theme
    that is, and the system filling these in would be deciding what its own
    evidence means.
    """

    launch_id: str = Field(min_length=1)
    theme: str = Field(min_length=1, max_length=200)
    segment: str = Field(min_length=1, max_length=200)
    band: str = Field(description="low, medium or high.")
