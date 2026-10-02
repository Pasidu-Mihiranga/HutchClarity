"""Event envelope and catalogue (plan §18.1-18.2).

Every event Clarity publishes carries the same envelope, so a consumer can
route, deduplicate and trace without knowing the payload. The shape follows
CloudEvents and the TMF688 notification pattern.

Two fields carry most of the operational weight:

``subject``
    The ``subscriber_ref``. It is the partition key, which is what gives
    per-customer ordering - "scales out by phone number" (deck S14).
``causation_id``
    The event that caused this one. Following it backwards reconstructs the
    whole chain from a payment landing to a receipt being issued.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from clarity.kernel.common import ClarityModel, utc_now
from clarity.kernel.ids import new_id


class EventType(StrEnum):
    """The catalogue from plan §18.2.

    Ingest events describe things that happened in a HUTCH system. Core events
    describe what Clarity did about them.
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
    RECEIPT_ISSUED = "receipt.issued"
    RISK_DETECTED = "risk.detected"
    MCP_INVOKED = "mcp.invoked"
    RULE_PUBLISHED = "rule.published"
    RECONCILIATION_MISMATCH = "reconciliation.mismatch"


#: Events that must never be dropped silently: each one either moved money or
#: proves something to a customer. A consumer failure on these pages a human
#: rather than landing quietly in a DLQ (plan §18.4).
CRITICAL_EVENTS: frozenset[EventType] = frozenset(
    {
        EventType.ACTION_COMPLETED,
        EventType.ACTION_FAILED,
        EventType.RECEIPT_ISSUED,
        EventType.RECONCILIATION_MISMATCH,
    }
)


class Event(ClarityModel):
    """One event, ready to publish."""

    id: str = Field(default_factory=lambda: new_id("EVT"))
    type: EventType
    source: str = Field(default="clarity", description="Service that produced it.")
    subject: str = Field(description="subscriber_ref - the partition key.")
    time: datetime = Field(default_factory=utc_now)
    schema_version: str = "1.0"
    correlation_id: str | None = Field(
        default=None, description="Ties every event in one request together."
    )
    causation_id: str | None = Field(default=None, description="The event that caused this one.")
    data: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        return self.type in CRITICAL_EVENTS

    def caused(self, type_: EventType, **data: Any) -> Event:
        """Derive a follow-on event that keeps the trace intact."""
        return Event(
            type=type_,
            subject=self.subject,
            correlation_id=self.correlation_id or self.id,
            causation_id=self.id,
            data=data,
        )
