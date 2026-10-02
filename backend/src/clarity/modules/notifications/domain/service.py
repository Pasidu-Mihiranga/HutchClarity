"""Template-only notification dispatch domain."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from enum import StrEnum
from typing import Any


class DeliveryStatus(StrEnum):
    QUEUED = "queued"
    DEFERRED_QUIET_HOURS = "deferred_quiet_hours"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    REJECTED = "rejected"


# Approved templates only — free text is never accepted as body.
TEMPLATES: dict[str, dict[str, str]] = {
    "why_charge_en": {
        "en": "Your charge of LKR {amount_lkr} was caused by {cause}. Case {case_id}.",
        "si": "LKR {amount_lkr} අයකිරීම {cause} නිසා සිදු විය. Case {case_id}.",
        "ta": "LKR {amount_lkr} கட்டணம் {cause} காரணமாக. Case {case_id}.",
    },
    "action_proposed_en": {
        "en": "We proposed {action_type} for case {case_id}. Confirm in the app.",
        "si": "Case {case_id} සඳහා {action_type} යෝජනා කෙරිණි.",
        "ta": "Case {case_id} க்கு {action_type} முன்மொழியப்பட்டது.",
    },
    "receipt_ready": {
        "en": "Your trust receipt {receipt_id} is ready.",
        "si": "ඔබේ receipt {receipt_id} සූදානම්.",
        "ta": "உங்கள் receipt {receipt_id} தயார்.",
    },
}


@dataclass
class Preferences:
    language: str = "en"
    channel_order: list[str] = field(default_factory=lambda: ["app", "sms", "whatsapp"])
    quiet_hours_start: time = time(21, 0)
    quiet_hours_end: time = time(7, 0)
    enabled: bool = True


@dataclass
class NotificationRecord:
    id: str
    template_id: str
    channel: str
    msisdn: str | None
    case_id: str | None
    language: str
    params: dict[str, str]
    body: str
    status: DeliveryStatus
    created_at: datetime
    updated_at: datetime
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "channel": self.channel,
            "msisdn": self.msisdn,
            "case_id": self.case_id,
            "language": self.language,
            "params": self.params,
            "body": self.body,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error": self.error,
        }


def _in_quiet_hours(now: datetime, prefs: Preferences) -> bool:
    current = now.timetz().replace(tzinfo=None) if now.tzinfo else now.time()
    start, end = prefs.quiet_hours_start, prefs.quiet_hours_end
    if start <= end:
        return start <= current < end
    # wraps midnight
    return current >= start or current < end


def render_template(template_id: str, language: str, params: dict[str, str]) -> str:
    bundle = TEMPLATES.get(template_id)
    if bundle is None:
        raise ValueError(f"unknown template_id: {template_id}")
    text = bundle.get(language) or bundle.get("en")
    if text is None:
        raise ValueError(f"template {template_id} has no en fallback")
    try:
        return text.format(**params)
    except KeyError as exc:
        raise ValueError(f"missing template param: {exc}") from exc


class NotificationService:
    """Template-only dispatch with preferences, quiet hours, and status tracking."""

    def __init__(self) -> None:
        self._prefs: dict[str, Preferences] = {}
        self._records: dict[str, NotificationRecord] = {}

    def set_preferences(self, subscriber_ref: str, prefs: Preferences) -> None:
        self._prefs[subscriber_ref] = prefs

    def get_preferences(self, subscriber_ref: str) -> Preferences:
        return self._prefs.get(subscriber_ref, Preferences())

    def send(
        self,
        *,
        template_id: str,
        params: dict[str, str],
        channel: str | None = None,
        language: str | None = None,
        msisdn: str | None = None,
        case_id: str | None = None,
        subscriber_ref: str | None = None,
        ignore_quiet_hours: bool = False,
    ) -> NotificationRecord:
        prefs = self.get_preferences(subscriber_ref or msisdn or "default")
        if not prefs.enabled:
            raise ValueError("notifications disabled by preference")
        lang = language or prefs.language
        body = render_template(template_id, lang, params)
        chosen = channel or (prefs.channel_order[0] if prefs.channel_order else "app")
        now = datetime.now(UTC)
        status = DeliveryStatus.SENT
        if not ignore_quiet_hours and _in_quiet_hours(now, prefs):
            status = DeliveryStatus.DEFERRED_QUIET_HOURS
        record = NotificationRecord(
            id=f"NTF-{uuid.uuid4().hex[:10].upper()}",
            template_id=template_id,
            channel=chosen,
            msisdn=msisdn,
            case_id=case_id,
            language=lang,
            params=dict(params),
            body=body,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self._records[record.id] = record
        return record

    def status(self, notification_id: str) -> NotificationRecord | None:
        return self._records.get(notification_id)

    def mark(self, notification_id: str, status: DeliveryStatus, *, error: str | None = None) -> NotificationRecord:
        record = self._records.get(notification_id)
        if record is None:
            raise KeyError(notification_id)
        record.status = status
        record.error = error
        record.updated_at = datetime.now(UTC)
        return record


_SERVICE: NotificationService | None = None


def get_notifications() -> NotificationService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = NotificationService()
    return _SERVICE
