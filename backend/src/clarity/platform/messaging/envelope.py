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
from typing import Any

from pydantic import Field

from clarity.contracts.events import DomainEventType, EventPayload, validate_payload
from clarity.kernel.common import ClarityModel, utc_now
from clarity.kernel.ids import new_id

#: The catalogue lives in ``clarity.contracts.events`` (shared vocabulary, L0).
#: This alias keeps existing imports working.
EventType = DomainEventType


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
    schema_version: int = Field(default=1, ge=1, description="Payload schema: type@vN.")
    correlation_id: str | None = Field(
        default=None, description="Ties every event in one request together."
    )
    causation_id: str | None = Field(default=None, description="The event that caused this one.")
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def of(
        cls,
        payload: EventPayload,
        *,
        subject: str,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        source: str = "clarity",
    ) -> Event:
        """Build an event from a typed payload, so type and version cannot disagree."""
        return cls(
            type=payload.event_type,
            schema_version=payload.version,
            subject=subject,
            correlation_id=correlation_id,
            causation_id=causation_id,
            source=source,
            data=payload.model_dump(mode="json"),
        )

    @property
    def schema_id(self) -> str:
        """The payload schema this event claims, as ``type@vN``."""
        return f"{self.type.value}@v{self.schema_version}"

    @property
    def is_critical(self) -> bool:
        return self.type in CRITICAL_EVENTS

    def payload(self) -> EventPayload:
        """The typed payload. Raises ``InvalidEventPayload`` if ``data`` does not match."""
        return validate_payload(self.type, self.data, self.schema_version)

    def caused(self, payload: EventPayload) -> Event:
        """Derive a follow-on event that keeps the trace intact."""
        return Event.of(
            payload,
            subject=self.subject,
            correlation_id=self.correlation_id or self.id,
            causation_id=self.id,
        )
