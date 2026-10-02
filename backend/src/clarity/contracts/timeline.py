"""Timeline: the evidence a case is decided on (plan §3.1, §16.2).

The Timeline Builder joins the eight log sources into one case file. Everything
a rule reads comes from here, and nothing else counts as evidence - customer
text is a hint, never evidence (deck S7).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import Field, field_validator, model_validator

from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import (
    ClarityModel,
    Completeness,
    EventSource,
    Money,
    ensure_utc,
)

JsonScalar = str | int | bool | None
Attributes = dict[str, Any]


class EventType(StrEnum):
    """Vocabulary rules match on.

    Grouped by the source that produces it. Adding a type is a rule-pack
    concern, so the names are stable and explicit rather than free-form.
    """

    # payments
    PAYMENT_CAPTURED = "payment_captured"
    PAYMENT_SETTLED = "payment_settled"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_REVERSED = "payment_reversed"
    # charging
    BALANCE_CREDITED = "balance_credited"
    BALANCE_ADJUSTED = "balance_adjusted"
    CHARGE_APPLIED = "charge_applied"
    VAS_CHARGE = "vas_charge"
    # vas consent
    CONSENT_OTP_VERIFIED = "consent_otp_verified"
    SECOND_CONFIRMATION = "second_confirmation"
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    VAS_RENEWAL_NOTICE = "vas_renewal_notice"
    SUBSCRIPTION_DEACTIVATED = "subscription_deactivated"
    # catalogue / packs
    PACK_PURCHASED = "pack_purchased"
    PACK_ACTIVATED = "pack_activated"
    PACK_EXPIRED = "pack_expired"
    # usage / FUP
    DATA_SESSION = "data_session"
    USAGE_THRESHOLD_CROSSED = "usage_threshold_crossed"
    FUP_CAP_REACHED = "fup_cap_reached"
    THROTTLE_APPLIED = "throttle_applied"
    NETWORK_OUTAGE = "network_outage"
    # loans
    LOAN_GIVEN = "loan_given"
    LOAN_RECOVERED = "loan_recovered"
    # crm
    TICKET_CREATED = "ticket_created"
    COMPLAINT_RECEIVED = "complaint_received"
    # identity / risk
    SIM_SWAP = "sim_swap"
    OTP_SENT = "otp_sent"


class TimelineEvent(ClarityModel):
    """One normalised fact from a HUTCH system.

    ``attributes`` holds source-specific fields (merchant, subscription,
    offering, bucket). Rules address them by name, so adapters must map
    consistently; the mapping is the adapter's anti-corruption layer (§9.1).
    """

    event_id: str = Field(description="Clarity-assigned id, unique within the case.")
    source: EventSource
    event_type: EventType
    source_event_id: str = Field(description="Id in the originating HUTCH system.")
    occurred_at: datetime
    amount_lkr: Money | None = None
    attributes: Attributes = Field(default_factory=dict)
    adapter_version: str = Field(default="mock-0.1.0")
    ingested_at: datetime | None = None

    @field_validator("occurred_at", "ingested_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @property
    def evidence_hash(self) -> str:
        """Hash of the fields that make this event evidence.

        Excludes ingestion metadata, so re-reading the same source fact twice
        yields the same hash and a decision stays reproducible.
        """
        return hash_payload(
            {
                "source": self.source,
                "event_type": self.event_type,
                "source_event_id": self.source_event_id,
                "occurred_at": self.occurred_at,
                "amount_lkr": self.amount_lkr,
                "attributes": self.attributes,
            }
        )

    def attr(self, name: str, default: Any = None) -> Any:
        """Read an attribute without raising on absence."""
        return self.attributes.get(name, default)


class SourceStatus(ClarityModel):
    """How well one source answered for this case (plan §9.1, §16.3)."""

    source: EventSource
    completeness: Completeness
    event_count: int = 0
    queried_window_days: int | None = None
    note: str | None = Field(
        default=None,
        description="Why a source is partial or missing, shown to staff.",
    )

    @model_validator(mode="after")
    def _missing_has_no_events(self) -> Self:
        if self.completeness is Completeness.MISSING and self.event_count:
            raise ValueError("a MISSING source cannot have returned events")
        return self


class EvidenceSnapshot(ClarityModel):
    """Immutable set of evidence a decision was made on (plan §13.5, §15.2).

    The snapshot hash makes replay exact: re-running a rule version against the
    same snapshot must reproduce the same decision, bit for bit.
    """

    case_id: str
    built_at: datetime
    window_from: datetime
    window_to: datetime
    events: Annotated[list[TimelineEvent], Field(default_factory=list)]
    sources: Annotated[list[SourceStatus], Field(default_factory=list)]

    @field_validator("built_at", "window_from", "window_to")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _events_sorted_and_unique(self) -> Self:
        ids = [e.event_id for e in self.events]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate event_id in snapshot")
        if any(
            a.occurred_at > b.occurred_at
            for a, b in zip(self.events, self.events[1:], strict=False)
        ):
            raise ValueError("snapshot events must be ordered by occurred_at")
        return self

    @property
    def snapshot_hash(self) -> str:
        """Order-independent hash of the evidence in this snapshot."""
        return hash_payload(
            {
                "window_from": self.window_from,
                "window_to": self.window_to,
                "events": sorted(e.evidence_hash for e in self.events),
                "sources": {s.source.value: s.completeness.value for s in self.sources},
            }
        )

    def status_of(self, source: EventSource) -> Completeness:
        """Completeness for one source; ``MISSING`` if never queried."""
        for status in self.sources:
            if status.source is source:
                return status.completeness
        return Completeness.MISSING

    def of_type(self, *types: EventType) -> list[TimelineEvent]:
        """Events of the given types, in chronological order."""
        wanted = set(types)
        return [e for e in self.events if e.event_type in wanted]

    def by_id(self, event_id: str) -> TimelineEvent | None:
        return next((e for e in self.events if e.event_id == event_id), None)
