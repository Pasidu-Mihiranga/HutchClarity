"""F02 seeded aggregate persona rehearsal."""

from clarity.modules.foresight.public import ChangeType, Scenario, ScenarioRehearsal


def test_same_seed_and_scenario_reproduce_the_swarm():
    scenario = Scenario("Retire synthetic pack", ChangeType.PACK_RETIRED)
    rehearsal = ScenarioRehearsal()
    assert rehearsal.run(scenario, seed=9) == rehearsal.run(scenario, seed=9)


def test_baseline_and_swarm_are_compared_as_relative_bands():
    report = ScenarioRehearsal().run(Scenario("FUP rehearsal", ChangeType.FUP_TIGHTENED))
    assert report.predictions
    assert report.comparison
    assert report.provenance == "SYNTHETIC"
    assert all(item.baseline.value in {"low", "medium", "high"} for item in report.comparison)
    assert all(item.swarm.value in {"low", "medium", "high"} for item in report.comparison)


def test_swarm_objects_have_no_customer_or_complaint_fields():
    report = ScenarioRehearsal().run(Scenario("Outage", ChangeType.OUTAGE))
    assert not hasattr(report, "customer_id")
    assert not hasattr(report, "complaints")
