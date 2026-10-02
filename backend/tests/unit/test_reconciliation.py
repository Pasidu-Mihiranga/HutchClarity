"""T+1 reconciliation of completed actions against adapter confirmations."""

from __future__ import annotations

from datetime import timedelta

from clarity.app.container import Clarity
from clarity.contracts.decision import ActionType
from clarity.contracts.events import ActionCompletedV1, ActionStepV1
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.platform.messaging.envelope import Event, EventType


def test_missing_adapter_confirmation_publishes_a_mismatch() -> None:
    clarity = Clarity(world=build_demo_world())
    completed = Event.of(
        ActionCompletedV1(
            case_id="CASE-REC-1",
            plan_id="PLAN-REC-1",
            decision_id="DEC-REC-1",
            steps=[
                ActionStepV1(
                    action_id="ACT-REC-1",
                    action_type=ActionType.REFUND,
                    amount_lkr="49.00",
                    status="COMPLETED",
                    idempotency_key="missing-adapter-key",
                    adapter_ref=None,
                )
            ],
            confirmed_by="staff_approved",
            total_amount_lkr="49.00",
        ),
        subject="sub_reconciliation_fixture",
    )
    clarity.bus.publish(completed)
    clarity.bus.drain()

    mismatches = clarity.reconciliation.run_daily(day=completed.time.date() + timedelta(days=1))
    clarity.deliver_events()

    assert len(mismatches) == 1
    published = [
        event
        for event in clarity.relay.published_events()
        if event.type is EventType.RECONCILIATION_MISMATCH
    ]
    assert len(published) == 1
    assert published[0].data["action_id"] == "ACT-REC-1"
    assert published[0].data["reason"] == "no adapter confirmation"


def test_daily_match_is_idempotent() -> None:
    clarity = Clarity(world=build_demo_world())
    completed = Event.of(
        ActionCompletedV1(
            case_id="CASE-REC-2",
            plan_id="PLAN-REC-2",
            decision_id="DEC-REC-2",
            steps=[
                ActionStepV1(
                    action_id="ACT-REC-2",
                    action_type=ActionType.REFUND,
                    amount_lkr="10.00",
                    status="COMPLETED",
                    idempotency_key="also-missing",
                )
            ],
            confirmed_by="staff_approved",
            total_amount_lkr="10.00",
        ),
        subject="sub_reconciliation_fixture",
    )
    clarity.bus.publish(completed)
    clarity.bus.drain()
    day = completed.time.date() + timedelta(days=1)

    assert len(clarity.reconciliation.run_daily(day=day)) == 1
    assert clarity.reconciliation.run_daily(day=day) == []
    assert len(clarity.reconciliation.queue()) == 1
