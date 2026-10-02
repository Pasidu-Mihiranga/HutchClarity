"""Golden tests for VAS_NO_CONSENT@4 (plan §13.5).

Positive, negative, boundary and property cases. This rule can move money and
switch off a paid service, so the negative cases matter as much as the
positive one: a false match would refund a customer who did consent and would
block a merchant who did nothing wrong.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clarity.contracts.timeline import EventType
from clarity.kernel.common import Completeness, EventSource
from clarity.modules.detection.engine import RuleEngine
from tests.conftest import SnapshotBuilder

RULE = "VAS_NO_CONSENT"


def _charge(snap: SnapshotBuilder, **overrides):
    """A LKR 49 VAS charge at 14:06, as in deck S6."""
    params = {
        "subscription_id": "SUB-1",
        "merchant_id": "MER-1",
        "product": "Daily game subscription",
    } | overrides
    return snap.event(
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        snap.at(hours=4),
        amount="49.00",
        **params,
    )


def outcome_for(engine: RuleEngine, snapshot, rule_id: str = RULE):
    for found in engine.evaluate(snapshot).matched:
        if found.assessment.rule_id == rule_id:
            return found
    return None


# --------------------------------------------------------------------------- #
# Positive
# --------------------------------------------------------------------------- #


@pytest.mark.golden
def test_charge_without_any_consent_matches(engine: RuleEngine, snap: SnapshotBuilder):
    found = outcome_for(engine, _charge(snap).build())

    assert found is not None, "a VAS charge with no consent evidence must be detected"
    assert found.assessment.confidence >= Decimal("0.90")
    assert found.assessment.money_effect_lkr == Decimal("49.00")
    assert found.assessment.safeguard is not None, "a safeguard must stop recurrence"


@pytest.mark.golden
def test_money_effect_sums_every_charge_on_the_subscription(
    engine: RuleEngine, snap: SnapshotBuilder
):
    """Three daily charges on one unconsented subscription are all owed back."""
    for days in (1, 2, 3):
        snap.event(
            EventSource.CHARGING,
            EventType.VAS_CHARGE,
            snap.at(days=days),
            amount="49.00",
            subscription_id="SUB-1",
            merchant_id="MER-1",
        )

    found = outcome_for(engine, snap.build())

    assert found is not None
    assert found.assessment.money_effect_lkr == Decimal("147.00")


# --------------------------------------------------------------------------- #
# Negative
# --------------------------------------------------------------------------- #


@pytest.mark.golden
def test_verified_otp_before_the_charge_does_not_match(engine: RuleEngine, snap: SnapshotBuilder):
    _charge(snap).event(
        EventSource.VAS_CONSENT,
        EventType.CONSENT_OTP_VERIFIED,
        snap.at(days=3),
        subscription_id="SUB-1",
    )

    assert outcome_for(engine, snap.build()) is None, "consented charges are not disputes"


@pytest.mark.golden
def test_second_confirmation_is_also_consent(engine: RuleEngine, snap: SnapshotBuilder):
    _charge(snap).event(
        EventSource.VAS_CONSENT,
        EventType.SECOND_CONFIRMATION,
        snap.at(days=1),
        subscription_id="SUB-1",
    )

    assert outcome_for(engine, snap.build()) is None


@pytest.mark.golden
def test_consent_for_a_different_subscription_does_not_count(
    engine: RuleEngine, snap: SnapshotBuilder
):
    """Consent is per subscription; another one's OTP must not excuse this charge."""
    _charge(snap, subscription_id="SUB-1").event(
        EventSource.VAS_CONSENT,
        EventType.CONSENT_OTP_VERIFIED,
        snap.at(days=3),
        subscription_id="SUB-OTHER",
    )

    assert outcome_for(engine, snap.build()) is not None


# --------------------------------------------------------------------------- #
# Boundary
# --------------------------------------------------------------------------- #


@pytest.mark.golden
def test_otp_one_second_after_the_charge_is_not_prior_consent(
    engine: RuleEngine, snap: SnapshotBuilder
):
    """Consent must precede the charge. One second late is still late."""
    charge_at = snap.at(hours=4)
    _charge(snap).event(
        EventSource.VAS_CONSENT,
        EventType.CONSENT_OTP_VERIFIED,
        charge_at + timedelta(seconds=1),
        subscription_id="SUB-1",
    )

    assert outcome_for(engine, snap.build()) is not None


@pytest.mark.golden
def test_partial_consent_log_lowers_confidence(engine: RuleEngine, snap: SnapshotBuilder):
    """Absence is weaker evidence when the log only half-answered.

    The source still answered, so the rule is evaluated - but confidence drops
    by the configured penalty, which pushes the case to staff rather than a fix.
    """
    snapshot = _charge(snap).source(EventSource.VAS_CONSENT, Completeness.PARTIAL).build()

    found = outcome_for(engine, snapshot)

    assert found is None or found.assessment.confidence < Decimal("0.90"), (
        "a partially readable consent log must not support a confident refund"
    )


@pytest.mark.golden
def test_unreadable_consent_log_makes_the_rule_indeterminate(
    engine: RuleEngine, snap: SnapshotBuilder
):
    """Missing log -> a human, never a guess (deck S7)."""
    snapshot = _charge(snap).source(EventSource.VAS_CONSENT, Completeness.MISSING).build()

    evaluation = engine.evaluate(snapshot)

    assert outcome_for(engine, snapshot) is None
    assert RULE in [c.rule_id for c in evaluation.indeterminate]
    assert not evaluation.evidence_complete


# --------------------------------------------------------------------------- #
# Property
# --------------------------------------------------------------------------- #


@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(offset_hours=st.integers(min_value=1, max_value=24 * 365))
def test_never_matches_when_consent_precedes_the_charge(offset_hours: int):
    """For any prior-consent gap, the rule must stay silent."""
    from clarity.modules.detection.pack import load_packs
    from clarity.modules.detection.parameters import PolicyRuleParameters
    from clarity.platform.config.resolver import PolicyResolver
    from tests.conftest import PACKS_DIR, POLICY_DIR

    engine = RuleEngine(load_packs(PACKS_DIR))
    snap = SnapshotBuilder()
    charge_at = snap.at(hours=0)
    snap.event(
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        charge_at,
        amount="49.00",
        subscription_id="SUB-1",
        merchant_id="MER-1",
    ).event(
        EventSource.VAS_CONSENT,
        EventType.CONSENT_OTP_VERIFIED,
        charge_at - timedelta(hours=offset_hours),
        subscription_id="SUB-1",
    )

    snapshot = snap.build()
    parameters = PolicyRuleParameters(
        PolicyResolver.from_directory(POLICY_DIR), as_of=snapshot.built_at
    )
    assert all(
        found.assessment.rule_id != RULE
        for found in engine.evaluate(snapshot, parameters=parameters).matched
    )
