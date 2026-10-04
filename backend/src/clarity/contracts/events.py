"""Domain event contracts: typed, versioned payloads (ADR-0029, plan 21 §11.3).

Every event Clarity publishes has one payload model per version, owned by the
producing module and shared here so producers and consumers are checked
against the same shape. The rules:

- **Identifiers and minimal facts only.** A payload carries IDs, ``Money``
  strings, hashes and enums. The subscriber is the envelope's ``subject``
  (a pseudonymous ``subscriber_ref``), never a field here. A consumer that
  needs more asks the owning module.
- **No personal data, by construction.** A payload class cannot even be
  defined with a field named like personal data (see ``_FORBIDDEN_SEGMENTS``).
- **Versioned.** A schema is addressed as ``type@vN``. Additive changes stay
  within a version; a breaking change is a new model registered as ``N+1``
  and published alongside the old one until consumers move.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import Field, ValidationError

from clarity.contracts.decision import ActionType, Outcome
from clarity.kernel.common import Channel, ClarityModel, Language, Money


class DomainEventType(StrEnum):
    """The event catalogue (plan 21 §11.3).

    Ingest events describe something that happened in a HUTCH system; core
    events describe what Clarity did about it.
    """

    # Ingest - from HUTCH via adapters
    PAYMENT_RECORDED = "payment.recorded"
    CHARGE_APPLIED = "charge.applied"
    USAGE_THRESHOLD_REACHED = "usage.threshold_reached"
    PACK_EXPIRING = "pack.expiring"
    VAS_RENEWED = "vas.renewed"
    COMPLAINT_CREATED = "complaint.created"

    # Core - Clarity's own outbox
    CASE_CREATED = "case.created"
    CAUSE_DETECTED = "cause.detected"
    DECISION_GENERATED = "decision.generated"
    ACTION_REQUESTED = "action.requested"
    ACTION_COMPLETED = "action.completed"
    ACTION_FAILED = "action.failed"
    APPROVAL_REQUESTED = "approval.requested"
    RECEIPT_ISSUED = "receipt.issued"
    RISK_DETECTED = "risk.detected"
    MCP_INVOKED = "mcp.invoked"
    RULE_PUBLISHED = "rule.published"
    POLICY_PUBLISHED = "policy.published"
    KNOWLEDGE_PUBLISHED = "knowledge.published"
    RECONCILIATION_MISMATCH = "reconciliation.mismatch"
    CONVERSATION_TURN_COMPLETED = "conversation.turn.completed"
    CLUSTER_UPDATED = "cluster.updated"


#: Field-name segments that indicate personal data. Matched on ``_``-separated
#: segments, so ``merchant_id`` is fine and ``merchant_name`` is not.
_FORBIDDEN_SEGMENTS = frozenset(
    {
        "msisdn",
        "phone",
        "mobile",
        "nic",
        "passport",
        "name",
        "email",
        "address",
        "otp",
        "card",
        "cvv",
    }
)


class UnknownEventSchema(LookupError):
    """No payload model is registered for this event type and version."""


class InvalidEventPayload(ValueError):
    """A payload does not match its registered schema."""


class EventPayload(ClarityModel):
    """Base for every event payload. Strict: unknown fields are rejected."""

    event_type: ClassVar[DomainEventType]
    version: ClassVar[int] = 1

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for field_name in cls.__annotations__:
            segments = set(field_name.lower().split("_"))
            if segments & _FORBIDDEN_SEGMENTS:
                raise TypeError(
                    f"{cls.__name__}.{field_name}: event payloads must not carry personal "
                    "data; reference it by ID and let the consumer ask the owning module"
                )

    @classmethod
    def schema_id(cls) -> str:
        return f"{cls.event_type.value}@v{cls.version}"


# --------------------------------------------------------------------------- #
# Ingest events (produced by integration adapters)
# --------------------------------------------------------------------------- #


class PaymentRecordedV1(EventPayload):
    event_type = DomainEventType.PAYMENT_RECORDED
    payment_ref: str
    amount_lkr: Money
    bank_ref_hash: str = Field(description="Hash of the bank reference, never the reference.")
    captured_at: datetime


class ChargeAppliedV1(EventPayload):
    event_type = DomainEventType.CHARGE_APPLIED
    charge_ref: str
    amount_lkr: Money
    merchant_id: str | None = None
    service_id: str | None = None
    rated_at: datetime


class UsageThresholdReachedV1(EventPayload):
    event_type = DomainEventType.USAGE_THRESHOLD_REACHED
    offering_id: str
    bucket: str
    threshold_percent: int = Field(ge=1, le=100)
    reached_at: datetime


class PackExpiringV1(EventPayload):
    event_type = DomainEventType.PACK_EXPIRING
    offering_id: str
    expires_at: datetime


class VasRenewedV1(EventPayload):
    event_type = DomainEventType.VAS_RENEWED
    subscription_id: str
    merchant_id: str
    amount_lkr: Money
    renewed_at: datetime


class ComplaintCreatedV1(EventPayload):
    event_type = DomainEventType.COMPLAINT_CREATED
    complaint_id: str
    channel: Channel
    language: Language
    case_id: str | None = None


# --------------------------------------------------------------------------- #
# Core events (produced by Clarity modules through the outbox)
# --------------------------------------------------------------------------- #


class CaseCreatedV1(EventPayload):
    event_type = DomainEventType.CASE_CREATED
    case_id: str
    case_no: str
    channel: Channel
    trigger: str
    language: Language
    money_at_stake_lkr: Money | None = None


class CauseDetectedV1(EventPayload):
    event_type = DomainEventType.CAUSE_DETECTED
    case_id: str
    rule_id: str
    rule_version: int
    confidence: float = Field(ge=0, le=1)
    snapshot_hash: str
    ruled_out: list[str] = Field(default_factory=list)


class DecisionGeneratedV1(EventPayload):
    event_type = DomainEventType.DECISION_GENERATED
    case_id: str
    decision_id: str
    outcome: Outcome
    amount_lkr: Money | None = None
    policy_version: str
    input_hash: str
    config_snapshot_hash: str | None = None


class ActionRequestedV1(EventPayload):
    event_type = DomainEventType.ACTION_REQUESTED
    case_id: str
    plan_id: str
    action_id: str
    action_type: ActionType
    amount_lkr: Money | None = None
    idempotency_key: str


class ActionStepV1(ClarityModel):
    """One executed step, as reported in ``action.completed``."""

    action_id: str
    action_type: ActionType
    amount_lkr: Money | None = None
    status: str
    idempotency_key: str
    adapter_ref: str | None = None


class ActionCompletedV1(EventPayload):
    event_type = DomainEventType.ACTION_COMPLETED
    case_id: str
    plan_id: str
    decision_id: str
    steps: list[ActionStepV1] = Field(min_length=1)
    confirmed_by: str
    approver_roles: list[str] = Field(default_factory=list)
    total_amount_lkr: Money
    config_snapshot_hash: str | None = None


class ActionFailedV1(EventPayload):
    event_type = DomainEventType.ACTION_FAILED
    case_id: str
    plan_id: str
    failed_step: ActionType
    error_code: str
    compensated: bool
    retryable: bool = False
    """True when nothing was applied, so the same plan can be executed again.

    A failure that applied a step and reversed it is not retryable: that plan is
    compensated and needs a person (M-ACT).
    """
    attempt: int = 1


class ApprovalRequestedV1(EventPayload):
    """A plan is waiting for a staff approval (M-ACT).

    Carries how many approvals are still needed and the threshold that decided
    it, so a notification can say what it is asking for without reading the
    policy itself.
    """

    event_type = DomainEventType.APPROVAL_REQUESTED
    case_id: str
    plan_id: str
    decision_id: str
    total_amount_lkr: Money
    approvals_needed: int = Field(ge=1)
    approvals_held: int = Field(ge=0)
    four_eyes_threshold_lkr: Money
    requested_by: str
    """The maker, who may not also approve (plan section 14.2)."""


class ReceiptIssuedV1(EventPayload):
    event_type = DomainEventType.RECEIPT_ISSUED
    case_id: str
    receipt_id: str
    plan_id: str | None = None
    payload_hash: str
    key_id: str


class RiskDetectedV1(EventPayload):
    event_type = DomainEventType.RISK_DETECTED
    risk_type: str
    band: Literal["low", "medium", "high"]
    score: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)


class McpInvokedV1(EventPayload):
    event_type = DomainEventType.MCP_INVOKED
    invocation_id: str
    tool: str
    profile: str
    allowed: bool
    args_hash: str
    result_hash: str | None = None
    latency_ms: int = Field(ge=0)


class RulePublishedV1(EventPayload):
    event_type = DomainEventType.RULE_PUBLISHED
    rule_id: str
    rule_version: int
    pack_hash: str
    change_class: str


class PolicyPublishedV1(EventPayload):
    event_type = DomainEventType.POLICY_PUBLISHED
    change_id: str
    key: str
    policy_version: int
    change_class: str
    effective_from: datetime | None = None


class KnowledgePublishedV1(EventPayload):
    """A knowledge source version was published (K03, plan 22 section 7).

    Consumers re-index the affected chunks and drop any cached answer that was
    composed from the old corpus. Carries the source's identity and window, not
    its text: an event is a notification that something changed, and copying
    the clause into it would put governed content in the message bus where
    nobody owns its version.

    K01 deliberately did not declare this event, because nothing consumed it
    and an event with no consumer is a contract maintained for nothing. K03
    adds the answer cache, which is the consumer.
    """

    event_type = DomainEventType.KNOWLEDGE_PUBLISHED
    source_id: str
    source_version: int
    kind: str
    owner: str
    audience: str
    language: str
    effective_from: datetime
    effective_to: datetime | None = None
    chunk_count: int = 0
    corpus_version: str = ""
    """The corpus fingerprint after this publication, for cache keying."""


class ReconciliationMismatchV1(EventPayload):
    event_type = DomainEventType.RECONCILIATION_MISMATCH
    plan_id: str
    action_id: str
    expected_lkr: Money
    confirmed_lkr: Money | None = None
    reason: str


class ClusterUpdatedV1(EventPayload):
    """A complaint cluster was drawn or its review status changed (C7, plan 18 section 159).

    Promised by plan 18 section 159 and missing until now, which is why
    foresight had no way to learn what a shipped change actually produced
    without reaching into autopsy's tables (I6 forbids that).

    **Codes and counts only.** No label and no keywords: a cluster's label is
    derived from what customers wrote, so publishing it would put a paraphrase
    of complaint text on the bus, and `autopsy` exists precisely so that text
    stays in one place. A consumer that needs the label asks autopsy for it.

    `size` is how many complaints the cluster holds. It is the only number here,
    and it is a count of records rather than of people: one person complaining
    four times is four.
    """

    event_type = DomainEventType.CLUSTER_UPDATED
    cluster_id: str
    status: str
    """`hypothesis`, `confirmed` or `rejected`, matching `ClusterStatus`."""
    size: int = Field(ge=0)
    suggested_rule_id: str | None = None
    reviewed_by: str | None = None
    """Staff reference of whoever ruled on it, or None while it is a hypothesis."""


class ConversationTurnCompletedV1(EventPayload):
    """One assistant turn finished (C01, plan 22 section 4 step 11).

    Carries what the assistant *did*, never what was said. There is no message
    text here and no reply: the base class forbids personal data by field name,
    and a turn payload that quoted conversations would turn every consumer's
    store into a store of conversations.

    `guard_codes` and `verifier_codes` are stable codes, so insights can count
    held turns and failed verifications without reading any content.
    """

    event_type = DomainEventType.CONVERSATION_TURN_COMPLETED
    case_id: str
    turn_no: int
    channel: Channel
    flow: str
    flow_state: str
    intent: str
    language: Language
    resumed: bool = False
    """Whether this turn continued an existing conversation, possibly on
    another channel. The cross-channel handover is visible here."""
    handoff: bool = False
    refused: bool = False
    guard_codes: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    model_role: str | None = None
    """The model role that composed the reply, or None for a template."""
    verifier_ok: bool = True
    verifier_codes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

_PAYLOADS: tuple[type[EventPayload], ...] = (
    PaymentRecordedV1,
    ChargeAppliedV1,
    UsageThresholdReachedV1,
    PackExpiringV1,
    VasRenewedV1,
    ComplaintCreatedV1,
    CaseCreatedV1,
    CauseDetectedV1,
    DecisionGeneratedV1,
    ActionRequestedV1,
    ActionCompletedV1,
    ActionFailedV1,
    ApprovalRequestedV1,
    ReceiptIssuedV1,
    RiskDetectedV1,
    McpInvokedV1,
    RulePublishedV1,
    PolicyPublishedV1,
    KnowledgePublishedV1,
    ReconciliationMismatchV1,
    ConversationTurnCompletedV1,
    ClusterUpdatedV1,
)

#: (event type, schema version) -> payload model.
REGISTRY: dict[tuple[DomainEventType, int], type[EventPayload]] = {
    (model.event_type, 1): model for model in _PAYLOADS
}


def payload_model(event_type: DomainEventType | str, version: int = 1) -> type[EventPayload]:
    """The payload model for ``event_type@v<version>``."""
    try:
        key = (DomainEventType(event_type), version)
    except ValueError as error:
        raise UnknownEventSchema(f"{event_type}@v{version}: unknown event type") from error
    model = REGISTRY.get(key)
    if model is None:
        raise UnknownEventSchema(f"{key[0].value}@v{version}: no schema registered")
    return model


def validate_payload(
    event_type: DomainEventType | str, data: dict[str, Any], version: int = 1
) -> EventPayload:
    """Check ``data`` against its registered schema, or raise a typed error."""
    model = payload_model(event_type, version)
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise InvalidEventPayload(
            f"{model.schema_id()}: {error.error_count()} problem(s)"
        ) from error


__all__ = [
    "REGISTRY",
    "ActionCompletedV1",
    "ActionFailedV1",
    "ActionRequestedV1",
    "ActionStepV1",
    "ApprovalRequestedV1",
    "CaseCreatedV1",
    "CauseDetectedV1",
    "ChargeAppliedV1",
    "ClusterUpdatedV1",
    "ComplaintCreatedV1",
    "ConversationTurnCompletedV1",
    "DecisionGeneratedV1",
    "DomainEventType",
    "EventPayload",
    "InvalidEventPayload",
    "KnowledgePublishedV1",
    "McpInvokedV1",
    "PackExpiringV1",
    "PaymentRecordedV1",
    "PolicyPublishedV1",
    "ReceiptIssuedV1",
    "ReconciliationMismatchV1",
    "RiskDetectedV1",
    "RulePublishedV1",
    "UnknownEventSchema",
    "UsageThresholdReachedV1",
    "VasRenewedV1",
    "payload_model",
    "validate_payload",
]
