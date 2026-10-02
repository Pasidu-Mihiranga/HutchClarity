"""Notification templates, preferences, idempotency and fallback (N01)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clarity.contracts.events import ReceiptIssuedV1
from clarity.kernel.common import Channel
from clarity.modules.notifications.public import (
    DeliveryStatus,
    MemoryNotificationDispatcher,
    NotificationRefused,
    NotificationRequest,
    NotificationService,
    Purpose,
    RecipientPreference,
)
from clarity.platform.messaging.envelope import Event
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork


def _service(
    dispatcher: MemoryNotificationDispatcher | None = None,
) -> tuple[NotificationService, MemoryNotificationDispatcher]:
    store = MemoryStore()
    driver = dispatcher or MemoryNotificationDispatcher()
    service = NotificationService(
        open_unit=lambda: MemoryUnitOfWork(store),
        dispatcher=driver,
        clock=lambda: datetime(2027, 9, 14, 18, 0, tzinfo=UTC),
    )
    return service, driver


def _receipt_event() -> Event:
    return Event.of(
        ReceiptIssuedV1(
            case_id="CASE-1",
            receipt_id="TR-2027-000001",
            plan_id="PLAN-1",
            payload_hash="sha256:" + "1" * 64,
            key_id="key-1",
        ),
        subject="sub_customer",
    )


def test_duplicate_receipt_event_sends_one_message() -> None:
    service, dispatcher = _service()
    event = _receipt_event()

    first = service.on_event(event)
    second = service.on_event(event)

    assert first.notification_id == second.notification_id
    assert len(dispatcher.sent) == 1


def test_free_text_body_is_refused() -> None:
    service, _ = _service()

    with pytest.raises(NotificationRefused, match="free-text"):
        service.send(
            NotificationRequest(
                event_id="EVT-1",
                recipient="sub_customer",
                body="We promise a refund",
            )
        )


def test_failed_preferred_channel_falls_back() -> None:
    dispatcher = MemoryNotificationDispatcher(failing_channels={Channel.WHATSAPP})
    service, _ = _service(dispatcher)

    record = service.on_event(_receipt_event())

    assert record.status is DeliveryStatus.SENT
    assert [attempt.channel for attempt in record.attempts] == [Channel.WHATSAPP, Channel.SMS]
    assert len(dispatcher.sent) == 1
    assert dispatcher.sent[0].channel is Channel.SMS


def test_consent_and_quiet_hours_are_applied_before_dispatch() -> None:
    service, dispatcher = _service()
    service.set_preference(
        RecipientPreference(
            recipient="sub_customer",
            channels=[Channel.SMS],
            consent={Purpose.SERVICE},
            quiet_start_hour=17,
            quiet_end_hour=7,
        )
    )

    record = service.on_event(_receipt_event())

    assert record.status is DeliveryStatus.DEFERRED
    assert dispatcher.sent == []
