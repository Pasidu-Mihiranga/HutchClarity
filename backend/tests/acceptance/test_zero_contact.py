"""P01 zero-contact duplicate reload journey through the event stream."""

from __future__ import annotations

from clarity.app.container import Clarity
from clarity.contracts.case import CaseState, CaseTrigger
from clarity.contracts.decision import Outcome
from clarity.contracts.events import PaymentRecordedV1
from clarity.contracts.timeline import EventType as TimelineEventType
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.kernel.common import EventSource
from clarity.platform.messaging.envelope import Event

NIMAL = "+94772223333"


def test_two_captures_one_credit_are_auto_fixed_without_a_human() -> None:
    world = build_demo_world()
    clarity = Clarity(world=world)
    subscriber = ref_for(NIMAL)
    account = world.account(subscriber)
    assert account is not None
    opening_balance = account.balance_lkr
    captures = [
        item
        for item in account.records[EventSource.PAYMENTS]
        if item.event_type is TimelineEventType.PAYMENT_CAPTURED
    ]
    assert len(captures) == 2

    for capture in captures:
        clarity.bus.publish(
            Event.of(
                PaymentRecordedV1(
                    payment_ref=str(capture.attributes["payment_ref"]),
                    amount_lkr=capture.amount_lkr,
                    bank_ref_hash="sha256:nimal-bank-ref",
                    captured_at=capture.occurred_at,
                ),
                subject=subscriber,
            )
        )
    # Ingest events arrive on the bus, then the worker relays the domain facts
    # its handlers committed to the outbox.
    clarity.bus.drain()
    clarity.deliver_events()

    records = [
        item
        for item in clarity.cases.all_cases()
        if item.subscriber_ref == subscriber and item.case.trigger is CaseTrigger.STREAM
    ]
    assert len(records) == 1
    record = records[0]
    assert record.decision is not None and record.decision.outcome is Outcome.AUTO_FIX
    assert record.case.state is CaseState.RECEIPTED
    assert account.balance_lkr == opening_balance + record.decision.amount_lkr
    assert record.receipts_by_plan
    assert clarity.consumers.stats("proactive-cases").failures == 0
