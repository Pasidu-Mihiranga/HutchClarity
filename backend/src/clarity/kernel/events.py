"""CloudEvents-style event envelope and catalogue."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from clarity.kernel.common import ClarityModel, utc_now
from clarity.kernel.ids import new_id


class EventType(StrEnum):
    PAYMENT_RECORDED = "payment.recorded"
    CHARGE_APPLIED = "charge.applied"
    USAGE_THRESHOLD_REACHED = "usage.threshold_reached"
    PACK_EXPIRING = "pack.expiring"
    VAS_RENEWED = "vas.renewed"
    COMPLAINT_CREATED = "complaint.created"
    CASE_CREATED = "case.created"
    CASE_UPDATED = "case.updated"
    CASE_HANDOFF = "case.handoff"
    CAUSE_DETECTED = "cause.detected"
    DECISION_GENERATED = "decision.generated"
    ACTION_REQUESTED = "action.requested"
    ACTION_COMPLETED = "action.completed"
    ACTION_FAILED = "action.failed"
    RECEIPT_ISSUED = "receipt.issued"
    RISK_DETECTED = "risk.detected"
    MCP_INVOKED = "mcp.invoked"
    RULE_PUBLISHED = "rule.published"
    CONFIG_PUBLISHED = "config.published"
    RECONCILIATION_MISMATCH = "reconciliation.mismatch"
    SAFEGUARD_CHANGED = "safeguard.changed"
    NOTIFICATION_SENT = "notification.sent"
    MESSAGE_RECEIVED = "message.received"
    CLUSTER_UPDATED = "cluster.updated"
    FORECAST_READY = "forecast.ready"
    SPIKE_DETECTED = "spike.detected"


CRITICAL_EVENTS: frozenset[EventType] = frozenset(
    {
        EventType.ACTION_COMPLETED,
        EventType.ACTION_FAILED,
        EventType.RECEIPT_ISSUED,
        EventType.RECONCILIATION_MISMATCH,
    }
)


class Event(ClarityModel):
    id: str = Field(default_factory=lambda: new_id("EVT"))
    type: EventType
    source: str = "clarity"
    subject: str
    time: datetime = Field(default_factory=utc_now)
    schema_version: str = "1.0"
    correlation_id: str | None = None
    causation_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
