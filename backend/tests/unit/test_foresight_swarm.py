"""F02 seeded aggregate persona rehearsal.

C1 moved foresight's parameters into the policy store, so the rehearsal is built
around a catalogue rather than constructing its own engine, and a scenario
carries the effective date its policy resolves at. The behaviour under test is
unchanged: the same seed and scenario reproduce the same swarm, and the report
carries nothing about an individual.
"""

from __future__ import annotations

from datetime import date

from clarity.modules.foresight.public import (
    ChangeType,
    ForesightCatalogue,
    Scenario,
    ScenarioRehearsal,
)
from clarity.platform.config.resolver import PolicyResolver
from tests.conftest import POLICY_DIR

_CATALOGUE = ForesightCatalogue(PolicyResolver.from_directory(POLICY_DIR))
_EFFECTIVE = date(2027, 1, 1)


def scenario(name: str, change_type: ChangeType) -> Scenario:
    return Scenario(name=name, change_type=change_type, effective_date=_EFFECTIVE)


def rehearsal() -> ScenarioRehearsal:
    return ScenarioRehearsal(_CATALOGUE)


def test_same_seed_and_scenario_reproduce_the_swarm():
    rehearsed = scenario("Retire synthetic pack", ChangeType.PACK_RETIRED)
    runner = rehearsal()
    assert runner.run(rehearsed, seed=9) == runner.run(rehearsed, seed=9)


def test_baseline_and_swarm_are_compared_as_relative_bands():
    report = rehearsal().run(scenario("FUP rehearsal", ChangeType.FUP_TIGHTENED))
    assert report.predictions
    assert report.comparison
    assert report.provenance == "SYNTHETIC"
    assert all(item.baseline.value in {"low", "medium", "high"} for item in report.comparison)
    assert all(item.swarm.value in {"low", "medium", "high"} for item in report.comparison)


def test_swarm_objects_have_no_customer_or_complaint_fields():
    report = rehearsal().run(scenario("Outage", ChangeType.OUTAGE))
    assert not hasattr(report, "customer_id")
    assert not hasattr(report, "complaints")
