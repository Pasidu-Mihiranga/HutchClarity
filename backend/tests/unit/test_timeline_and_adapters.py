"""Timeline builder and adapter framework tests (plan §3.1, §9.1).

The timeline is where "fragmented logs" becomes "one case file" (deck S2, S7),
so these tests focus on the join, on honest completeness reporting, and on the
boundary that keeps HUTCH writes behind the tool layer.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from clarity.contracts.decision import ActionType
from clarity.integration.drivers.mock.world import DEMO_NOW, SyntheticWorld, ref_for
from clarity.integration.ports import Command, DriverMode
from clarity.integration.registry import AdapterRegistry, NotYetIntegrated
from clarity.kernel.common import Completeness, EventSource
from clarity.modules.timeline.builder import TimelineBuilder, TimelineRequest

DILANI = "+94771234567"


def test_timeline_joins_every_source_into_one_ordered_file(builder: TimelineBuilder):
    snapshot = builder.build(TimelineRequest.for_case("C", ref_for(DILANI), now=DEMO_NOW))

    assert snapshot.events, "the case file must contain evidence"
    assert snapshot.events == sorted(snapshot.events, key=lambda e: e.occurred_at)
    assert len(snapshot.sources) == len(EventSource), "all eight sources are reported on"


def test_events_outside_the_window_are_excluded(builder: TimelineBuilder):
    narrow = TimelineRequest(
        case_id="C",
        subscriber_ref=ref_for(DILANI),
        window_from=DEMO_NOW - timedelta(minutes=1),
        window_to=DEMO_NOW,
    )

    assert builder.build(narrow).events == []


def test_an_unreadable_source_is_missing_not_empty(builder: TimelineBuilder, world: SyntheticWorld):
    """The distinction that stops a confident wrong answer (deck S7)."""
    world.unavailable.add(EventSource.VAS_CONSENT)

    snapshot = builder.build(TimelineRequest.for_case("C", ref_for(DILANI), now=DEMO_NOW))

    status = next(s for s in snapshot.sources if s.source is EventSource.VAS_CONSENT)
    assert status.completeness is Completeness.MISSING
    assert status.note, "staff must be told why a source is missing"


def test_a_source_that_answers_with_nothing_is_complete(builder: TimelineBuilder):
    """ "Looked, found nothing" is complete evidence, not a gap."""
    snapshot = builder.build(TimelineRequest.for_case("C", ref_for(DILANI), now=DEMO_NOW))

    loans = next(s for s in snapshot.sources if s.source is EventSource.LOANS)
    assert loans.completeness is Completeness.COMPLETE
    assert loans.event_count == 0


def test_unknown_subscriber_yields_missing_sources(builder: TimelineBuilder):
    snapshot = builder.build(TimelineRequest.for_case("C", "sub_does_not_exist", now=DEMO_NOW))

    assert snapshot.events == []
    assert all(s.completeness is Completeness.MISSING for s in snapshot.sources)


def test_snapshot_hash_is_stable_across_rebuilds(builder: TimelineBuilder):
    request = TimelineRequest.for_case("C", ref_for(DILANI), now=DEMO_NOW)

    assert builder.build(request).snapshot_hash == builder.build(request).snapshot_hash


# --------------------------------------------------------------------------- #
# Adapter boundary
# --------------------------------------------------------------------------- #


def test_only_mock_drivers_exist_and_others_say_so_plainly():
    """Nothing here may pretend a HUTCH interface exists (Guidelines §4)."""
    with pytest.raises(NotYetIntegrated, match="not confirmed"):
        AdapterRegistry(mode=DriverMode.PRODUCTION)


def test_commands_are_idempotent(registry: AdapterRegistry, world: SyntheticWorld):
    """Replaying a key must never move money twice (NFR-COR-01)."""
    port = registry.command_port
    command = Command(
        action_type=ActionType.REFUND,
        subscriber_ref=ref_for(DILANI),
        idempotency_key="idem-1",
        amount_lkr="49.00",
    )
    opening = world.account(ref_for(DILANI)).balance_lkr

    first = port.execute(command)
    second = port.execute(command)

    assert first.accepted and second.accepted
    assert second.replayed, "the second call must be recognised as a replay"
    assert world.account(ref_for(DILANI)).balance_lkr == opening + Decimal("49.00")


def test_refund_reports_before_and_after_for_the_receipt(
    registry: AdapterRegistry, world: SyntheticWorld
):
    result = registry.command_port.execute(
        Command(
            action_type=ActionType.REFUND,
            subscriber_ref=ref_for(DILANI),
            idempotency_key="idem-2",
            amount_lkr="49.00",
        )
    )

    assert result.before_state == {"balance_lkr": "451.00"}
    assert result.after_state == {"balance_lkr": "500.00"}


def test_status_can_be_queried_instead_of_blindly_retrying(registry: AdapterRegistry):
    """Plan §18.4: ambiguous results are resolved by asking, not re-sending."""
    port = registry.command_port
    assert port.status_of("never-sent") is None

    port.execute(
        Command(
            action_type=ActionType.SET_SPEND_CAP,
            subscriber_ref=ref_for(DILANI),
            idempotency_key="idem-3",
            params={"cap_lkr": "100.00"},
        )
    )

    assert port.status_of("idem-3") is not None


def test_blocking_a_merchant_is_readable_afterwards(
    registry: AdapterRegistry, world: SyntheticWorld
):
    """The recurrence test is only honest if the block is really in place (deck S6)."""
    ref = ref_for(DILANI)
    assert not world.is_merchant_blocked(ref, "MER-GAMEHUB")

    registry.command_port.execute(
        Command(
            action_type=ActionType.BLOCK_MERCHANT_UNTIL_OPTIN,
            subscriber_ref=ref,
            idempotency_key="idem-4",
            params={"merchant_id": "MER-GAMEHUB"},
        )
    )

    assert world.is_merchant_blocked(ref, "MER-GAMEHUB")


def test_deactivating_a_subscription_stops_it(registry: AdapterRegistry, world: SyntheticWorld):
    ref = ref_for(DILANI)

    registry.command_port.execute(
        Command(
            action_type=ActionType.DEACTIVATE_VAS,
            subscriber_ref=ref,
            idempotency_key="idem-5",
            params={"subscription_id": "SUB-GAME-1"},
        )
    )

    subscription = world.account(ref).subscriptions[0]
    assert not subscription.active


def test_unsupported_action_is_refused_not_faked(registry: AdapterRegistry):
    result = registry.command_port.execute(
        Command(
            action_type=ActionType.SEND_NOTIFICATION,
            subscriber_ref=ref_for(DILANI),
            idempotency_key="idem-6",
        )
    )

    assert not result.accepted
    assert result.error_code == "ACTION_NOT_SUPPORTED_BY_ADAPTER"


def test_refund_of_zero_is_refused(registry: AdapterRegistry):
    result = registry.command_port.execute(
        Command(
            action_type=ActionType.REFUND,
            subscriber_ref=ref_for(DILANI),
            idempotency_key="idem-7",
            amount_lkr="0",
        )
    )

    assert not result.accepted
    assert result.error_code == "INVALID_AMOUNT"
