"""Golden tests for the payment and pack rules.

DUPLICATE_RELOAD is the only rule in the prototype whitelisted for auto-fix,
so its negative cases guard the one path where money moves with no human in
the loop at all.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from clarity.core.rules.engine import RuleEngine
from clarity.schemas.common import Completeness, EventSource
from clarity.schemas.timeline import EventType
from tests.conftest import SnapshotBuilder
from tests.golden.test_vas_no_consent import outcome_for


def _two_captures(
    snap: SnapshotBuilder, *, gap: timedelta, amount: str = "3500.00", second_ref: str = "BANKREF-1"
) -> SnapshotBuilder:
    first_at = snap.at(minutes=40)
    snap.event(
        EventSource.PAYMENTS,
        EventType.PAYMENT_CAPTURED,
        first_at,
        amount=amount,
        bank_ref="BANKREF-1",
        status="captured",
    )
    snap.event(
        EventSource.PAYMENTS,
        EventType.PAYMENT_CAPTURED,
        first_at + gap,
        amount=amount,
        bank_ref=second_ref,
        status="captured",
    )
    return snap


def _credit_once(snap: SnapshotBuilder, amount: str = "3500.00") -> SnapshotBuilder:
    return snap.event(
        EventSource.CHARGING,
        EventType.BALANCE_CREDITED,
        snap.at(minutes=39),
        amount=amount,
        bank_ref="BANKREF-1",
        reason="reload",
    )


# --------------------------------------------------------------------------- #
# DUPLICATE_RELOAD
# --------------------------------------------------------------------------- #


@pytest.mark.golden
def test_two_captures_one_credit_matches(engine: RuleEngine, snap: SnapshotBuilder):
    snapshot = _credit_once(_two_captures(snap, gap=timedelta(minutes=3))).build()

    found = outcome_for(engine, snapshot, "DUPLICATE_RELOAD")

    assert found is not None
    assert found.assessment.money_effect_lkr == Decimal("3500.00")
    assert found.pack.auto_fix_whitelisted, "the zero-contact refund depends on this"


@pytest.mark.golden
def test_two_credits_for_two_captures_is_not_a_duplicate(engine: RuleEngine, snap: SnapshotBuilder):
    """Both captures were honoured, so the customer is not owed anything."""
    _two_captures(snap, gap=timedelta(minutes=3))
    _credit_once(snap)
    snap.event(
        EventSource.CHARGING,
        EventType.BALANCE_CREDITED,
        snap.at(minutes=36),
        amount="3500.00",
        bank_ref="BANKREF-1",
        reason="reload",
    )

    assert outcome_for(engine, snap.build(), "DUPLICATE_RELOAD") is None


@pytest.mark.golden
def test_different_bank_references_are_separate_payments(engine: RuleEngine, snap: SnapshotBuilder):
    """Two deliberate reloads of the same amount must not look like a duplicate."""
    snapshot = _credit_once(
        _two_captures(snap, gap=timedelta(minutes=3), second_ref="BANKREF-2")
    ).build()

    assert outcome_for(engine, snapshot, "DUPLICATE_RELOAD") is None


@pytest.mark.golden
def test_captures_far_apart_are_not_a_duplicate(engine: RuleEngine, snap: SnapshotBuilder):
    """Boundary: the rule's window is 30 minutes."""
    snapshot = _credit_once(_two_captures(snap, gap=timedelta(minutes=31))).build()

    assert outcome_for(engine, snapshot, "DUPLICATE_RELOAD") is None


@pytest.mark.golden
def test_already_reversed_duplicate_does_not_match(engine: RuleEngine, snap: SnapshotBuilder):
    """Never refund twice what has already been put right."""
    _credit_once(_two_captures(snap, gap=timedelta(minutes=3)))
    snap.event(
        EventSource.PAYMENTS,
        EventType.PAYMENT_REVERSED,
        snap.at(minutes=10),
        amount="3500.00",
        bank_ref="BANKREF-1",
    )

    assert outcome_for(engine, snap.build(), "DUPLICATE_RELOAD") is None


@pytest.mark.golden
def test_unreadable_payments_make_duplicate_detection_indeterminate(
    engine: RuleEngine, snap: SnapshotBuilder
):
    snapshot = (
        _credit_once(_two_captures(snap, gap=timedelta(minutes=3)))
        .source(EventSource.PAYMENTS, Completeness.MISSING)
        .build()
    )

    evaluation = engine.evaluate(snapshot)

    assert "DUPLICATE_RELOAD" in [c.rule_id for c in evaluation.indeterminate]


# --------------------------------------------------------------------------- #
# RELOAD_NOT_CREDITED
# --------------------------------------------------------------------------- #


@pytest.mark.golden
def test_capture_with_no_credit_matches(engine: RuleEngine, snap: SnapshotBuilder):
    snap.event(
        EventSource.PAYMENTS,
        EventType.PAYMENT_CAPTURED,
        snap.at(hours=3),
        amount="12000.00",
        bank_ref="BANKREF-9",
        status="captured",
    )

    found = outcome_for(engine, snap.build(), "RELOAD_NOT_CREDITED")

    assert found is not None
    assert found.assessment.money_effect_lkr == Decimal("12000.00")
    assert not found.pack.auto_fix_whitelisted, "a missing credit may just be settlement lag"


@pytest.mark.golden
def test_failed_payment_is_not_a_missing_credit(engine: RuleEngine, snap: SnapshotBuilder):
    """The bank declined, so there is nothing to credit and nothing to refund."""
    snap.event(
        EventSource.PAYMENTS,
        EventType.PAYMENT_CAPTURED,
        snap.at(hours=3),
        amount="12000.00",
        bank_ref="BANKREF-9",
    ).event(
        EventSource.PAYMENTS,
        EventType.PAYMENT_FAILED,
        snap.at(hours=2),
        amount="12000.00",
        bank_ref="BANKREF-9",
    )

    assert outcome_for(engine, snap.build(), "RELOAD_NOT_CREDITED") is None


# --------------------------------------------------------------------------- #
# FUP_CAP_REACHED
# --------------------------------------------------------------------------- #


@pytest.mark.golden
def test_disclosed_fup_cap_matches_and_is_explain_only(engine: RuleEngine, snap: SnapshotBuilder):
    snap.event(
        EventSource.CATALOGUE,
        EventType.PACK_PURCHASED,
        snap.at(days=26),
        amount="1499.00",
        offering_id="PKG-UNLTD",
        fup_disclosed=True,
        fup_cap_gb="50.00",
    ).event(
        EventSource.USAGE_FUP,
        EventType.FUP_CAP_REACHED,
        snap.at(hours=4),
        bucket="PKG-UNLTD",
        cap_gb="50.00",
    )

    found = outcome_for(engine, snap.build(), "FUP_CAP_REACHED")

    assert found is not None
    assert found.pack.disclosed_to_customer, "a disclosed term is explained, not refunded"
    assert found.assessment.money_effect_lkr is None, "nothing was wrongly charged"


@pytest.mark.golden
def test_undisclosed_cap_does_not_match_this_rule(engine: RuleEngine, snap: SnapshotBuilder):
    """If the cap was never shown at purchase, this is not the 'you saw it' case.

    It must fall to another rule or a human, never be explained away.
    """
    snap.event(
        EventSource.CATALOGUE,
        EventType.PACK_PURCHASED,
        snap.at(days=26),
        amount="1499.00",
        offering_id="PKG-UNLTD",
        fup_disclosed=False,
    ).event(
        EventSource.USAGE_FUP,
        EventType.FUP_CAP_REACHED,
        snap.at(hours=4),
        bucket="PKG-UNLTD",
    )

    assert outcome_for(engine, snap.build(), "FUP_CAP_REACHED") is None


# --------------------------------------------------------------------------- #
# DUPLICATE_VAS_CHARGE
# --------------------------------------------------------------------------- #


@pytest.mark.golden
def test_same_subscription_charged_twice_in_a_day(engine: RuleEngine, snap: SnapshotBuilder):
    first = snap.at(hours=20)
    snap.event(
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        first,
        amount="49.00",
        subscription_id="SUB-1",
        merchant_id="MER-1",
    ).event(
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        first + timedelta(hours=2),
        amount="49.00",
        subscription_id="SUB-1",
        merchant_id="MER-1",
    )

    found = outcome_for(engine, snap.build(), "DUPLICATE_VAS_CHARGE")

    assert found is not None
    assert found.assessment.money_effect_lkr == Decimal("49.00"), "only the extra charge"


@pytest.mark.golden
def test_charges_on_consecutive_days_are_normal_for_a_daily_product(
    engine: RuleEngine, snap: SnapshotBuilder
):
    first = snap.at(days=3)
    snap.event(
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        first,
        amount="49.00",
        subscription_id="SUB-1",
        merchant_id="MER-1",
    ).event(
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        first + timedelta(days=1),
        amount="49.00",
        subscription_id="SUB-1",
        merchant_id="MER-1",
    )

    assert outcome_for(engine, snap.build(), "DUPLICATE_VAS_CHARGE") is None
