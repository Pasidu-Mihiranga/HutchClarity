"""Stream detector behavior and risk publication (P01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from clarity.contracts.events import PackExpiringV1, PaymentRecordedV1, UsageThresholdReachedV1
from clarity.modules.proactive.public import ProactiveService
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.messaging.envelope import Event, EventType
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork

POLICY_DIR = Path(__file__).resolve().parents[3] / "config" / "policy"


def _service() -> tuple[ProactiveService, MemoryStore]:
    store = MemoryStore()
    policies = PolicyResolver.from_directory(POLICY_DIR)
    return (
        ProactiveService(open_unit=lambda: MemoryUnitOfWork(store), policies=policies),
        store,
    )


def test_second_matching_capture_publishes_one_duplicate_risk() -> None:
    service, store = _service()
    at = datetime(2027, 9, 14, 14, 0, tzinfo=UTC)
    events = [
        Event.of(
            PaymentRecordedV1(
                payment_ref=f"pay-{index}",
                amount_lkr="3500.00",
                bank_ref_hash="sha256:bank-ref",
                captured_at=at + timedelta(minutes=index),
            ),
            subject="sub_nimal",
        )
        for index in range(2)
    ]

    service.consume_event(events[0])
    service.consume_event(events[1])
    service.consume_event(events[1])

    with MemoryUnitOfWork(store) as unit:
        published = [row.event for row in outbox_in(unit).all_rows()]
    assert [event.type for event in published] == [EventType.RISK_DETECTED]
    assert published[0].data["risk_type"] == "duplicate_reload"


def test_only_policy_configured_fup_thresholds_publish() -> None:
    service, store = _service()
    at = datetime(2027, 9, 14, 14, 0, tzinfo=UTC)
    for percent in (79, 80, 95):
        service.consume_event(
            Event.of(
                UsageThresholdReachedV1(
                    offering_id="PKG-1",
                    bucket="data",
                    threshold_percent=percent,
                    reached_at=at,
                ),
                subject="sub_customer",
            )
        )

    with MemoryUnitOfWork(store) as unit:
        risks = [row.event for row in outbox_in(unit).all_rows()]
    assert [event.data["risk_type"] for event in risks] == ["fup_80", "fup_95"]


def test_pack_expiry_publishes_once_with_source_event_time() -> None:
    service, store = _service()
    at = datetime(2027, 9, 15, 0, 0, tzinfo=UTC)
    source = Event.of(
        PackExpiringV1(offering_id="PKG-1", expires_at=at + timedelta(days=1)),
        subject="sub_customer",
    ).model_copy(update={"time": at})

    service.consume_event(source)
    service.consume_event(source)

    with MemoryUnitOfWork(store) as unit:
        risks = [row.event for row in outbox_in(unit).all_rows()]
    assert len(risks) == 1
    assert risks[0].data["risk_type"] == "pack_expiring"
    assert risks[0].time == source.time
