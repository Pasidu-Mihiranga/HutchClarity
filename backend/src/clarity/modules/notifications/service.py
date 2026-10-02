"""Template-only notification routing, dispatch and delivery tracking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from threading import RLock
from typing import Protocol

from pydantic import Field, model_validator

from clarity.contracts.events import ApprovalRequestedV1, ReceiptIssuedV1, RiskDetectedV1
from clarity.kernel.common import Channel, ClarityModel, Language, utc_now
from clarity.kernel.ids import new_id
from clarity.platform.messaging.envelope import Event, EventType
from clarity.platform.persistence import Repository, UnitOfWorkFactory

NOTIFICATIONS = "notifications.records"
PREFERENCES = "notifications.preferences"


class NotificationRefused(ValueError):
    """A notification violates the approved-template contract."""


class DispatchFailed(RuntimeError):
    """A channel driver could not accept a templated message."""


class Purpose(StrEnum):
    SERVICE = "service"
    MARKETING = "marketing"
    STAFF = "staff"


class DeliveryStatus(StrEnum):
    DEFERRED = "deferred"
    SUPPRESSED = "suppressed"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass(frozen=True)
class TemplateDefinition:
    template_id: str
    purpose: Purpose
    required_params: frozenset[str]
    urgent: bool = False


APPROVED_TEMPLATES: dict[str, TemplateDefinition] = {
    "receipt_issued_v1": TemplateDefinition(
        "receipt_issued_v1", Purpose.SERVICE, frozenset({"receipt_id"})
    ),
    "risk_detected_v1": TemplateDefinition(
        "risk_detected_v1", Purpose.SERVICE, frozenset({"risk_type", "band"})
    ),
    "approval_requested_v1": TemplateDefinition(
        "approval_requested_v1",
        Purpose.STAFF,
        frozenset({"plan_id", "amount_lkr", "approvals_needed"}),
        urgent=True,
    ),
}


class RecipientPreference(ClarityModel):
    recipient: str
    language: Language = Language.EN
    channels: list[Channel] = Field(default_factory=lambda: [Channel.WHATSAPP, Channel.SMS])
    consent: set[Purpose] = Field(default_factory=lambda: {Purpose.SERVICE})
    quiet_start_hour: int | None = Field(default=None, ge=0, le=23)
    quiet_end_hour: int | None = Field(default=None, ge=0, le=23)

    @model_validator(mode="after")
    def _quiet_hours_are_complete(self) -> RecipientPreference:
        if (self.quiet_start_hour is None) != (self.quiet_end_hour is None):
            raise ValueError("quiet hours need both start and end")
        if not self.channels:
            raise ValueError("at least one notification channel is required")
        return self


class NotificationRequest(ClarityModel):
    event_id: str
    recipient: str
    template_id: str | None = None
    params: dict[str, str] = Field(default_factory=dict)
    body: str | None = None


class DispatchAttempt(ClarityModel):
    channel: Channel
    accepted: bool
    adapter_ref: str | None = None
    error: str | None = None


class NotificationRecord(ClarityModel):
    notification_id: str
    idempotency_key: str
    event_id: str
    recipient: str
    template_id: str
    params: dict[str, str]
    language: Language
    purpose: Purpose
    status: DeliveryStatus
    created_at: datetime
    attempts: list[DispatchAttempt] = Field(default_factory=list)


class DispatchPort(Protocol):
    def send(
        self,
        *,
        channel: Channel,
        recipient: str,
        template_id: str,
        language: Language,
        params: dict[str, str],
        idempotency_key: str,
    ) -> str: ...


@dataclass(frozen=True)
class DispatchedTemplate:
    channel: Channel
    recipient: str
    template_id: str
    language: Language
    params: dict[str, str]
    idempotency_key: str
    adapter_ref: str


@dataclass
class MemoryNotificationDispatcher:
    """Labelled simulated channel driver for lite and unit tests."""

    failing_channels: set[Channel] = field(default_factory=set)
    sent: list[DispatchedTemplate] = field(default_factory=list)

    def send(
        self,
        *,
        channel: Channel,
        recipient: str,
        template_id: str,
        language: Language,
        params: dict[str, str],
        idempotency_key: str,
    ) -> str:
        if channel in self.failing_channels:
            raise DispatchFailed(f"simulated {channel.value} channel failure")
        adapter_ref = new_id("MSG")
        self.sent.append(
            DispatchedTemplate(
                channel=channel,
                recipient=recipient,
                template_id=template_id,
                language=language,
                params=dict(params),
                idempotency_key=idempotency_key,
                adapter_ref=adapter_ref,
            )
        )
        return adapter_ref


class NotificationService:
    """Consume facts and dispatch only approved, idempotent templates."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory,
        dispatcher: DispatchPort,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._open_unit = open_unit
        self._dispatcher = dispatcher
        self._clock = clock
        self._lock = RLock()

    def set_preference(self, preference: RecipientPreference) -> None:
        with self._open_unit() as unit:
            preferences: Repository[str, RecipientPreference] = unit.repository(PREFERENCES)
            preferences.put(preference.recipient, preference)
            unit.commit()

    def preference_for(self, recipient: str, *, staff: bool = False) -> RecipientPreference:
        with self._open_unit() as unit:
            preferences: Repository[str, RecipientPreference] = unit.repository(PREFERENCES)
            found = preferences.get(recipient)
        if found is not None:
            return found
        if staff:
            return RecipientPreference(
                recipient=recipient,
                channels=[Channel.APP],
                consent={Purpose.STAFF},
            )
        return RecipientPreference(recipient=recipient)

    def on_event(self, event: Event) -> NotificationRecord:
        payload = event.payload()
        if isinstance(payload, ReceiptIssuedV1):
            request = NotificationRequest(
                event_id=event.id,
                recipient=event.subject,
                template_id="receipt_issued_v1",
                params={"receipt_id": payload.receipt_id},
            )
        elif isinstance(payload, RiskDetectedV1):
            request = NotificationRequest(
                event_id=event.id,
                recipient=event.subject,
                template_id="risk_detected_v1",
                params={"risk_type": payload.risk_type, "band": payload.band},
            )
        elif isinstance(payload, ApprovalRequestedV1):
            request = NotificationRequest(
                event_id=event.id,
                recipient="role:supervisor",
                template_id="approval_requested_v1",
                params={
                    "plan_id": payload.plan_id,
                    "amount_lkr": f"{payload.total_amount_lkr:.2f}",
                    "approvals_needed": str(payload.approvals_needed),
                },
            )
        else:
            raise NotificationRefused(f"{event.type.value} has no approved notification template")
        return self.send(request)

    def consume_event(self, event: Event) -> None:
        """Consumer-framework adapter; the persisted record is the outcome."""
        self.on_event(event)

    def send(self, request: NotificationRequest) -> NotificationRecord:
        with self._lock:
            return self._send(request)

    def _send(self, request: NotificationRequest) -> NotificationRecord:
        if request.body is not None:
            raise NotificationRefused("free-text notification bodies are forbidden")
        if request.template_id is None:
            raise NotificationRefused("an approved template_id is required")
        template = APPROVED_TEMPLATES.get(request.template_id)
        if template is None:
            raise NotificationRefused(f"template {request.template_id!r} is not approved")
        actual = set(request.params)
        if actual != set(template.required_params):
            raise NotificationRefused(
                f"template {template.template_id} needs params {sorted(template.required_params)}"
            )

        key = f"{request.event_id}:{request.recipient}:{template.template_id}"
        with self._open_unit() as unit:
            records: Repository[str, NotificationRecord] = unit.repository(NOTIFICATIONS)
            existing = records.get(key)
        if existing is not None:
            return existing

        staff = template.purpose is Purpose.STAFF
        preference = self.preference_for(request.recipient, staff=staff)
        now = self._clock()
        record = NotificationRecord(
            notification_id=new_id("NTF"),
            idempotency_key=key,
            event_id=request.event_id,
            recipient=request.recipient,
            template_id=template.template_id,
            params=request.params,
            language=preference.language,
            purpose=template.purpose,
            status=DeliveryStatus.FAILED,
            created_at=now,
        )
        if template.purpose not in preference.consent:
            record.status = DeliveryStatus.SUPPRESSED
        elif not template.urgent and self._in_quiet_hours(preference, now):
            record.status = DeliveryStatus.DEFERRED
        else:
            self._dispatch(record, preference)

        with self._open_unit() as unit:
            records = unit.repository(NOTIFICATIONS)
            records.put(key, record)
            unit.commit()
        return record

    def mark_delivery(self, adapter_ref: str, *, delivered: bool) -> NotificationRecord:
        with self._open_unit() as unit:
            records: Repository[str, NotificationRecord] = unit.repository(NOTIFICATIONS)
            record = next(
                (
                    item
                    for item in records.values()
                    if any(attempt.adapter_ref == adapter_ref for attempt in item.attempts)
                ),
                None,
            )
            if record is None:
                raise KeyError(adapter_ref)
            record.status = DeliveryStatus.DELIVERED if delivered else DeliveryStatus.FAILED
            records.put(record.idempotency_key, record)
            unit.commit()
        return record

    def records(self) -> list[NotificationRecord]:
        with self._open_unit() as unit:
            records: Repository[str, NotificationRecord] = unit.repository(NOTIFICATIONS)
            return records.values()

    def _dispatch(self, record: NotificationRecord, preference: RecipientPreference) -> None:
        for channel in preference.channels:
            try:
                adapter_ref = self._dispatcher.send(
                    channel=channel,
                    recipient=record.recipient,
                    template_id=record.template_id,
                    language=record.language,
                    params=record.params,
                    idempotency_key=record.idempotency_key,
                )
            except DispatchFailed as exc:
                record.attempts.append(
                    DispatchAttempt(channel=channel, accepted=False, error=str(exc))
                )
                continue
            record.attempts.append(
                DispatchAttempt(channel=channel, accepted=True, adapter_ref=adapter_ref)
            )
            record.status = DeliveryStatus.SENT
            return
        record.status = DeliveryStatus.FAILED

    @staticmethod
    def _in_quiet_hours(preference: RecipientPreference, now: datetime) -> bool:
        start = preference.quiet_start_hour
        end = preference.quiet_end_hour
        if start is None or end is None or start == end:
            return False
        if start < end:
            return start <= now.hour < end
        return now.hour >= start or now.hour < end


CONSUMED_EVENTS = (
    EventType.RECEIPT_ISSUED,
    EventType.RISK_DETECTED,
    EventType.APPROVAL_REQUESTED,
)


__all__ = [
    "APPROVED_TEMPLATES",
    "CONSUMED_EVENTS",
    "NOTIFICATIONS",
    "PREFERENCES",
    "DeliveryStatus",
    "DispatchAttempt",
    "DispatchFailed",
    "DispatchPort",
    "DispatchedTemplate",
    "MemoryNotificationDispatcher",
    "NotificationRecord",
    "NotificationRefused",
    "NotificationRequest",
    "NotificationService",
    "Purpose",
    "RecipientPreference",
    "TemplateDefinition",
]
