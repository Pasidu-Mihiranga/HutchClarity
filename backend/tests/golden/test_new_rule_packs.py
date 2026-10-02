"""Golden coverage for the four M-DET rule packs (issue #35)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clarity.contracts.timeline import EventType
from clarity.kernel.common import EventSource
from clarity.modules.detection.public import RuleEngine
from tests.conftest import SnapshotBuilder
from tests.golden.test_vas_no_consent import outcome_for


def _renewal(snap: SnapshotBuilder, *, notice_days: int | None = None) -> SnapshotBuilder:
    renewed = snap.at(days=1)
    snap.event(
        EventSource.VAS_CONSENT,
        EventType.SUBSCRIPTION_RENEWED,
        renewed,
        subscription_id="SUB-R1",
    ).event(
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        renewed + timedelta(minutes=1),
        amount="99.00",
        subscription_id="SUB-R1",
    )
    if notice_days is not None:
        snap.event(
            EventSource.VAS_CONSENT,
            EventType.VAS_RENEWAL_NOTICE,
            renewed - timedelta(days=notice_days),
            subscription_id="SUB-R1",
        )
    return snap


@pytest.mark.golden
def test_unnotified_vas_renewal_matches(engine: RuleEngine, snap: SnapshotBuilder):
    found = outcome_for(engine, _renewal(snap).build(), "VAS_RENEWAL_UNNOTIFIED")
    assert found is not None
    assert str(found.assessment.money_effect_lkr) == "99.00"


@pytest.mark.golden
def test_notified_vas_renewal_does_not_match(engine: RuleEngine, snap: SnapshotBuilder):
    assert (
        outcome_for(engine, _renewal(snap, notice_days=2).build(), "VAS_RENEWAL_UNNOTIFIED") is None
    )


@pytest.mark.golden
def test_notice_at_policy_boundary_counts(engine: RuleEngine, snap: SnapshotBuilder):
    assert (
        outcome_for(engine, _renewal(snap, notice_days=7).build(), "VAS_RENEWAL_UNNOTIFIED") is None
    )


@pytest.mark.property
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(days=st.integers(min_value=1, max_value=7))
def test_any_notice_inside_policy_window_prevents_match(engine: RuleEngine, days: int):
    snap = SnapshotBuilder()
    assert (
        outcome_for(engine, _renewal(snap, notice_days=days).build(), "VAS_RENEWAL_UNNOTIFIED")
        is None
    )


def _packs(
    snap: SnapshotBuilder, *, purchased: str, activated: str, gap_minutes: int = 5
) -> SnapshotBuilder:
    at = snap.at(hours=3)
    return snap.event(
        EventSource.CATALOGUE,
        EventType.PACK_PURCHASED,
        at,
        amount="749.00",
        order_id="ORDER-1",
        offering_id=purchased,
    ).event(
        EventSource.CHARGING,
        EventType.PACK_ACTIVATED,
        at + timedelta(minutes=gap_minutes),
        order_id="ORDER-1",
        offering_id=activated,
    )


@pytest.mark.golden
def test_pack_mismatch_matches(engine: RuleEngine, snap: SnapshotBuilder):
    found = outcome_for(
        engine, _packs(snap, purchased="PACK-A", activated="PACK-B").build(), "PACK_MISMATCH"
    )
    assert found is not None
    assert str(found.assessment.money_effect_lkr) == "749.00"


@pytest.mark.golden
def test_correct_pack_does_not_match(engine: RuleEngine, snap: SnapshotBuilder):
    assert (
        outcome_for(
            engine, _packs(snap, purchased="PACK-A", activated="PACK-A").build(), "PACK_MISMATCH"
        )
        is None
    )


@pytest.mark.golden
def test_pack_activation_at_window_boundary_matches(engine: RuleEngine, snap: SnapshotBuilder):
    assert (
        outcome_for(
            engine,
            _packs(snap, purchased="PACK-A", activated="PACK-B", gap_minutes=60).build(),
            "PACK_MISMATCH",
        )
        is not None
    )


@pytest.mark.property
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(offering=st.sampled_from(["PACK-A", "PACK-B", "PACK-C"]))
def test_identical_purchased_and_activated_pack_never_matches(engine: RuleEngine, offering: str):
    snap = SnapshotBuilder()
    assert (
        outcome_for(
            engine, _packs(snap, purchased=offering, activated=offering).build(), "PACK_MISMATCH"
        )
        is None
    )


def _loan(
    snap: SnapshotBuilder,
    *,
    loan_id: str = "LOAN-1",
    recovered_id: str = "LOAN-1",
    days: int = 5,
    recovered: str = "100.00",
) -> SnapshotBuilder:
    at = snap.at(days=100)
    return snap.event(
        EventSource.LOANS,
        EventType.LOAN_GIVEN,
        at,
        amount="100.00",
        loan_id=loan_id,
    ).event(
        EventSource.LOANS,
        EventType.LOAN_RECOVERED,
        at + timedelta(days=days),
        amount=recovered,
        loan_id=recovered_id,
    )


@pytest.mark.golden
def test_loan_recovery_matches_and_explains(engine: RuleEngine, snap: SnapshotBuilder):
    found = outcome_for(engine, _loan(snap).build(), "LOAN_RECOVERY")
    assert found is not None
    assert found.pack.disclosed_to_customer
    assert found.assessment.money_effect_lkr is None


@pytest.mark.golden
def test_unrelated_loan_recovery_does_not_match(engine: RuleEngine, snap: SnapshotBuilder):
    assert outcome_for(engine, _loan(snap, recovered_id="LOAN-2").build(), "LOAN_RECOVERY") is None


@pytest.mark.golden
def test_loan_recovery_at_window_boundary_matches(engine: RuleEngine, snap: SnapshotBuilder):
    assert outcome_for(engine, _loan(snap, days=90).build(), "LOAN_RECOVERY") is not None


@pytest.mark.property
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(recovered=st.integers(min_value=101, max_value=5000))
def test_recovery_above_loan_amount_never_matches(engine: RuleEngine, recovered: int):
    snap = SnapshotBuilder()
    assert (
        outcome_for(engine, _loan(snap, recovered=f"{recovered}.00").build(), "LOAN_RECOVERY")
        is None
    )


def _outage(
    snap: SnapshotBuilder,
    *,
    pack_region: str = "west",
    outage_region: str = "west",
    days: int = 2,
    expire_before: bool = False,
) -> SnapshotBuilder:
    activated = snap.at(days=40)
    snap.event(
        EventSource.CATALOGUE,
        EventType.PACK_ACTIVATED,
        activated,
        amount="1499.00",
        offering_id="PACK-30",
        region=pack_region,
    )
    outage = activated + timedelta(days=days)
    if expire_before:
        snap.event(
            EventSource.CATALOGUE,
            EventType.PACK_EXPIRED,
            outage - timedelta(seconds=1),
            offering_id="PACK-30",
        )
    return snap.event(
        EventSource.USAGE_FUP,
        EventType.NETWORK_OUTAGE,
        outage,
        region=outage_region,
        incident_id="INC-1",
    )


@pytest.mark.golden
def test_outage_during_active_pack_matches(engine: RuleEngine, snap: SnapshotBuilder):
    found = outcome_for(engine, _outage(snap).build(), "OUTAGE_DURING_PACK")
    assert found is not None
    assert str(found.assessment.money_effect_lkr) == "1499.00"


@pytest.mark.golden
def test_outage_in_another_region_does_not_match(engine: RuleEngine, snap: SnapshotBuilder):
    assert (
        outcome_for(engine, _outage(snap, outage_region="south").build(), "OUTAGE_DURING_PACK")
        is None
    )


@pytest.mark.golden
def test_outage_at_pack_window_boundary_matches(engine: RuleEngine, snap: SnapshotBuilder):
    assert outcome_for(engine, _outage(snap, days=30).build(), "OUTAGE_DURING_PACK") is not None


@pytest.mark.property
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(days=st.integers(min_value=1, max_value=30))
def test_expired_pack_never_matches_outage(engine: RuleEngine, days: int):
    snap = SnapshotBuilder()
    assert (
        outcome_for(
            engine, _outage(snap, days=days, expire_before=True).build(), "OUTAGE_DURING_PACK"
        )
        is None
    )
