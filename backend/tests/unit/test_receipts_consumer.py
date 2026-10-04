"""Receipts as a consumer of ``action.completed`` (issue #14, B06; ADR-0029).

The first flow where a side effect is the consequence of a fact rather than a
second call inside the money path. What must hold: delivery is at-least-once,
so the same ``action.completed`` can arrive more than once, and one executed
plan must still have exactly one receipt (D1).
"""

from __future__ import annotations

import threading
from decimal import Decimal

import pytest

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.kernel.common import Channel
from clarity.platform.messaging.envelope import Event, EventType

DILANI = "+94781234567"  # VAS without consent: ONE_TAP_FIX, LKR 49


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


def _executed_plan(clarity: Clarity) -> tuple[str, str]:
    case = clarity.cases.open_case(
        subscriber_ref=ref_for(DILANI), msisdn_masked="077***4567", channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    plan = clarity.cases.propose(case.case_id, created_by="channel:web")
    clarity.cases.confirm_and_execute(case.case_id, plan.plan_id)
    return case.case_id, plan.plan_id


def _completed_events(clarity: Clarity) -> list[Event]:
    return [
        event
        for event in clarity.relay.published_events()
        if event.type is EventType.ACTION_COMPLETED
    ]


def _receipt_events(clarity: Clarity) -> list[Event]:
    return [
        event
        for event in clarity.relay.published_events()
        if event.type is EventType.RECEIPT_ISSUED
    ]


# -- the flow itself ------------------------------------------------------ #


def test_executing_a_plan_publishes_action_completed(clarity: Clarity) -> None:
    _, plan_id = _executed_plan(clarity)

    events = _completed_events(clarity)
    assert len(events) == 1
    payload = events[0].payload()
    assert payload.plan_id == plan_id  # type: ignore[attr-defined]
    assert payload.total_amount_lkr == Decimal("49.00")  # type: ignore[attr-defined]
    # On the wire it is a string, so no JSON float can round the amount (I3).
    assert events[0].data["total_amount_lkr"] == "49.00"


def test_the_event_is_keyed_by_subscriber_so_one_customer_stays_in_order(
    clarity: Clarity,
) -> None:
    _executed_plan(clarity)
    assert _completed_events(clarity)[0].subject == ref_for(DILANI)


def test_the_receipt_is_the_consequence_of_the_event(clarity: Clarity) -> None:
    """The receipt exists because the event was consumed, not because case called."""
    _, plan_id = _executed_plan(clarity)
    assert clarity.receipts.for_plan(plan_id) is not None


def test_issuing_the_receipt_publishes_receipt_issued(clarity: Clarity) -> None:
    case_id, plan_id = _executed_plan(clarity)
    receipt = clarity.receipts.for_plan(plan_id)
    assert receipt is not None

    events = _receipt_events(clarity)
    assert len(events) == 1
    payload = events[0].payload()
    assert payload.case_id == case_id  # type: ignore[attr-defined]
    assert payload.plan_id == plan_id  # type: ignore[attr-defined]
    assert payload.receipt_id == receipt.receipt_id  # type: ignore[attr-defined]
    assert events[0].subject == ref_for(DILANI)


def test_the_event_carries_identifiers_and_amounts_only(clarity: Clarity) -> None:
    """ADR-0029 section 4: identifiers, amounts as Money strings, a hash.

    Pinned as an exact key set rather than a blocklist, so a field added to the
    payload has to be justified here instead of slipping past a keyword check.
    """
    _executed_plan(clarity)
    event = _completed_events(clarity)[0]

    assert set(event.data) == {
        "case_id",
        "plan_id",
        "decision_id",
        "steps",
        "confirmed_by",
        "approver_roles",
        "total_amount_lkr",
        "config_snapshot_hash",
    }
    assert set(event.data["steps"][0]) == {
        "action_id",
        "action_type",
        "amount_lkr",
        "status",
        # Both are system references, not personal data, and reconciliation
        # needs them to match an executed action against the adapter's
        # confirmation (M-REC).
        "adapter_ref",
        "idempotency_key",
    }


def test_the_event_carries_no_raw_number_anywhere(clarity: Clarity) -> None:
    """The subject is the HMAC pseudonym; the MSISDN must appear nowhere (I13)."""
    _executed_plan(clarity)
    event = _completed_events(clarity)[0]

    serialised = event.model_dump_json()
    assert DILANI not in serialised
    assert "781234567" not in serialised
    assert event.subject == ref_for(DILANI)


# -- acceptance 2: delivered twice, one receipt --------------------------- #


def test_action_completed_delivered_twice_issues_one_receipt(clarity: Clarity) -> None:
    _, plan_id = _executed_plan(clarity)
    first = clarity.receipts.for_plan(plan_id)
    assert first is not None
    before = len(clarity.receipts.issued())

    # The relay published and died before recording it, so it publishes again.
    event = _completed_events(clarity)[0]
    clarity.bus.publish(event)
    clarity.bus.drain()

    assert clarity.receipts.for_plan(plan_id) is not None
    assert clarity.receipts.for_plan(plan_id).receipt_id == first.receipt_id  # type: ignore[union-attr]
    assert len(clarity.receipts.issued()) == before, "no second receipt was chained"
    assert clarity.receipts.verify_chain()


def test_a_fresh_delivery_of_the_same_fact_still_issues_one_receipt(
    clarity: Clarity,
) -> None:
    """A different event id for the same plan: dedupe cannot rely on the event id.

    A relay restart republishes the same row, so the event id repeats and
    ``processed_event`` catches it. A re-derived event would not, which is why
    the receipt is keyed by plan id as well.
    """
    _, plan_id = _executed_plan(clarity)
    original = clarity.receipts.for_plan(plan_id)
    assert original is not None
    before = len(clarity.receipts.issued())

    same_fact_new_id = Event.of(_completed_events(clarity)[0].payload(), subject=ref_for(DILANI))
    assert same_fact_new_id.id != _completed_events(clarity)[0].id
    clarity.bus.publish(same_fact_new_id)
    clarity.bus.drain()

    assert len(clarity.receipts.issued()) == before
    assert clarity.receipts.for_plan(plan_id).receipt_id == original.receipt_id  # type: ignore[union-attr]


def test_ten_concurrent_deliveries_issue_one_receipt(clarity: Clarity) -> None:
    _, plan_id = _executed_plan(clarity)
    original = clarity.receipts.for_plan(plan_id)
    assert original is not None
    before = len(clarity.receipts.issued())
    event = _completed_events(clarity)[0]

    errors: list[BaseException] = []

    def deliver() -> None:
        try:
            clarity.bus.publish(event)
            clarity.bus.drain()
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=deliver) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(clarity.receipts.issued()) == before
    assert clarity.receipts.verify_chain()
