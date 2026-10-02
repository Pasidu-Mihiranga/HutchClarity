"""Trust Receipt: signed, checkable proof of what happened (deck S6, plan §15).

A receipt is split into two parts:

``ReceiptPayload``
    Everything that is signed. Hashing it canonically gives ``payload_hash``.
``TrustReceipt``
    The payload plus its hash, signature and verification URL.

The split exists so verification is unambiguous: a verifier re-canonicalizes
the payload, recomputes the hash, and checks the signature over it. Nothing
outside the payload can change the result.

Receipts are never edited. A correction issues a new receipt carrying
``supersedes``, so the trail of what was believed, and when, stays intact.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from clarity.contracts.decision import ActionStatus, ActionType, Outcome
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import (
    ClarityModel,
    EventSource,
    Language,
    Money,
    ensure_utc,
    utc_now,
)

SCHEMA_VERSION = "1.0"


class RecurrenceResult(StrEnum):
    """Did the safeguard really take effect? (deck S6)

    ``PASSED`` is only ever set after re-reading the system state, never
    inferred from the fact that a command was accepted.
    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNAVAILABLE = "UNAVAILABLE"
    """The check could not be run; the receipt says so rather than claiming pass."""


class ActorType(StrEnum):
    CUSTOMER_CONFIRMED = "customer_confirmed"
    STAFF_APPROVED = "staff_approved"
    SYSTEM_AUTO_FIX = "system_auto_fix"


class ReceiptSubject(ClarityModel):
    """Who the receipt is about, without identifying them in the clear."""

    msisdn_masked: str
    subscriber_ref_hash: str


class ReceiptCause(ClarityModel):
    """What happened, in rule terms."""

    cause_rule: str
    rule_version: int
    summary: str = Field(description="Plain-language statement built from the facts.")


class ReceiptEvidence(ClarityModel):
    """A pointer to evidence, by id and hash - never the raw record."""

    event_id: str
    source: EventSource
    hash: str
    assertion: str | None = Field(
        default=None,
        description="For an absence, e.g. 'no_otp_found'. Absence is evidence too.",
    )


class ReceiptDecision(ClarityModel):
    decision_id: str
    outcome: Outcome
    policy_version: str
    input_hash: str


class ReceiptAction(ClarityModel):
    """What was corrected, with the before and after the customer can check."""

    action_id: str
    type: ActionType
    amount_lkr: Money | None = None
    before: dict[str, str] = Field(default_factory=dict)
    after: dict[str, str] = Field(default_factory=dict)
    status: ActionStatus
    adapter_ref: str | None = None


class ReceiptSafeguard(ClarityModel):
    """What now protects the customer from a repeat."""

    type: ActionType
    status: str


class ReceiptRecurrenceTest(ClarityModel):
    check: str
    result: RecurrenceResult
    checked_at: datetime | None = None

    @field_validator("checked_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)


class ReceiptActor(ClarityModel):
    """Who authorised it. A role, never a named individual."""

    type: ActorType
    approver_role: str | None = None
    system: str


class ReceiptPayload(ClarityModel):
    """The signed content of a receipt."""

    receipt_id: str
    schema_version: str = SCHEMA_VERSION
    case_id: str
    issued_at: datetime = Field(default_factory=utc_now)
    subject: ReceiptSubject
    what_happened: ReceiptCause
    evidence: list[ReceiptEvidence] = Field(default_factory=list)
    decision: ReceiptDecision
    actions: list[ReceiptAction] = Field(default_factory=list)
    safeguard: ReceiptSafeguard | None = None
    recurrence_test: ReceiptRecurrenceTest | None = None
    actor: ReceiptActor
    languages: list[Language] = Field(
        default_factory=lambda: [Language.SI, Language.TA, Language.EN]
    )
    supersedes: str | None = None
    prev_receipt_hash: str | None = Field(
        default=None,
        description="Hash of the previous receipt in the chain; None only for the first.",
    )

    @field_validator("issued_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def total_corrected_lkr(self) -> Money | None:
        amounts = [a.amount_lkr for a in self.actions if a.amount_lkr is not None]
        return sum(amounts[1:], amounts[0]) if amounts else None

    def compute_hash(self) -> str:
        """Canonical hash of this payload. The signature covers exactly this."""
        return hash_payload(self.model_dump(mode="json"))


class ReceiptSignature(ClarityModel):
    alg: str = "Ed25519"
    kid: str
    value: str = Field(description="base64 signature over payload_hash")


class TrustReceipt(ClarityModel):
    """A receipt as issued: payload, its hash, the signature and where to check it."""

    payload: ReceiptPayload
    payload_hash: str
    signature: ReceiptSignature
    verify_url: str

    @property
    def receipt_id(self) -> str:
        return self.payload.receipt_id

    @property
    def case_id(self) -> str:
        return self.payload.case_id
