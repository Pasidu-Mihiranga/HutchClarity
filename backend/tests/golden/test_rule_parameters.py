"""Effective-dated detection parameters (M-DET acceptance case 1)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from clarity.contracts.timeline import EventType
from clarity.kernel.common import EventSource
from clarity.modules.detection.parameters import PolicyRuleParameters
from clarity.modules.detection.public import RuleEngine, load_packs
from clarity.platform.config.artefacts import PolicyValue
from clarity.platform.config.resolver import PolicyResolver
from tests.conftest import DEMO_NOW, PACKS_DIR, POLICY_DIR, SnapshotBuilder
from tests.golden.test_vas_no_consent import outcome_for


def test_tomorrows_confidence_override_does_not_change_todays_charge():
    policies = PolicyResolver.from_directory(POLICY_DIR)
    future = DEMO_NOW + timedelta(days=1)
    policies = policies.with_override(
        "detection.vas_renewal_unnotified.confidence_base",
        PolicyValue(value="0.99", effective_from=future, version=2),
    )
    snap = SnapshotBuilder(now=DEMO_NOW)
    renewal = snap.at(hours=1)
    snapshot = (
        snap.event(
            EventSource.VAS_CONSENT,
            EventType.SUBSCRIPTION_RENEWED,
            renewal,
            subscription_id="SUB-R1",
        )
        .event(
            EventSource.CHARGING,
            EventType.VAS_CHARGE,
            renewal + timedelta(minutes=1),
            amount="99.00",
            subscription_id="SUB-R1",
        )
        .build()
    )

    engine = RuleEngine(load_packs(PACKS_DIR))
    found = outcome_for(
        RuleEngine(
            engine.packs,
            parameters=PolicyRuleParameters(policies, as_of=renewal),
        ),
        snapshot,
        "VAS_RENEWAL_UNNOTIFIED",
    )

    assert found is not None
    assert found.assessment.confidence == Decimal("0.90")
