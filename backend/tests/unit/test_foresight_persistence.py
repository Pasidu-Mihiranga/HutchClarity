"""Foresight remembers, and the parts that matter cannot be rewritten (C2/F05).

Before C2 a run was built, returned and discarded. These tests cover the two
things that change about a module when it starts storing: that the records are
owned, scoped and append-only in the way the schema claims, and that the
operations on top of them behave when a caller repeats, polls or fails.

The ones worth reading first are the append-only tests. A scenario version, an
engine output and a recorded launch outcome are claims about the past that a
later reader relies on, and the launches and outcomes are the evidence the plan
02 section 3.4 gate opens on. Those are precisely the rows somebody would have
to rewrite to make an uncalibrated engine look calibrated.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from clarity.app.collections import ALL_COLLECTIONS
from clarity.modules.foresight.backtest import CalibrationStatus, Provenance
from clarity.modules.foresight.catalogue import ChangeType, ForesightCatalogue
from clarity.modules.foresight.records import (
    DetectedSpike,
    RunStatus,
    ScenarioVersion,
    SpikeScope,
)
from clarity.modules.foresight.repository import (
    CALIBRATIONS,
    LAUNCHES,
    OUTCOMES,
    REPORTS,
    RUNS,
    SCENARIOS,
    SPIKES,
    StoredForesightRepository,
)
from clarity.modules.foresight.service import (
    ForesightService,
    RealLaunchNotPermitted,
    RunAlreadyFinished,
    UnknownRun,
    UnknownScenario,
)
from clarity.modules.foresight.simulation import Scenario, VolumeBand
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork
from clarity.platform.persistence.memory import AppendOnlyWrite
from clarity.platform.persistence.schemas import (
    is_append_only,
    is_customer_scoped,
    owner_of,
)
from tests.conftest import POLICY_DIR

_AT = datetime(2027, 1, 1, tzinfo=UTC)
_EFFECTIVE = date(2027, 10, 1)
_ALL = (SCENARIOS, RUNS, REPORTS, LAUNCHES, OUTCOMES, CALIBRATIONS, SPIKES)


def catalogue() -> ForesightCatalogue:
    return ForesightCatalogue(PolicyResolver.from_directory(POLICY_DIR))


def service(clock: datetime = _AT) -> ForesightService:
    store = MemoryStore()
    return ForesightService(
        open_unit=lambda: MemoryUnitOfWork(store),
        catalogue=catalogue(),
        clock=lambda: clock,
    )


def scenario(name: str = "Retire the 10GB pack") -> Scenario:
    return Scenario(name=name, change_type=ChangeType.PACK_RETIRED, effective_date=_EFFECTIVE)


# --------------------------------------------------------------------------- #
# The schema says what the module means
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("collection", _ALL)
def test_every_collection_is_owned_by_foresight(collection: str):
    """An unowned collection is a table with no access rules (I6)."""
    assert owner_of(collection) == "foresight"


@pytest.mark.parametrize("collection", _ALL)
def test_every_collection_is_listed_for_migration(collection: str):
    """A collection the composition root does not list gets no table or grant."""
    assert collection in ALL_COLLECTIONS


@pytest.mark.parametrize(
    "collection", [SCENARIOS, REPORTS, LAUNCHES, OUTCOMES, CALIBRATIONS, SPIKES]
)
def test_six_of_the_seven_collections_are_append_only(collection: str):
    assert is_append_only(collection)


def test_runs_are_the_one_mutable_collection():
    """A run has a lifecycle a caller polls, so its row moves by design."""
    assert not is_append_only(RUNS)


@pytest.mark.parametrize("collection", _ALL)
def test_nothing_foresight_stores_is_customer_scoped(collection: str):
    """Deck S8: aggregates only, so there is no subscriber to bind a row to."""
    assert not is_customer_scoped(collection)


@pytest.mark.parametrize("collection", _ALL)
def test_no_stored_record_carries_a_subscriber_reference(collection: str):
    """The invariant, checked on the records rather than on the intention."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    run, _ = sut.request_run(version.version_id, by="staff:pm", idempotency_key="k")
    sut.execute(run.run_id)
    launch = sut.record_launch(
        scenario_version_id=version.version_id, provenance=Provenance.SYNTHETIC, by="staff:pm"
    )
    sut.record_outcome(
        launch_id=launch.launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="staff:pm",
    )
    sut.backtest(by="staff:pm")
    sut.record_spike(_spike())

    records = _stored_records(sut, collection)
    assert records, f"{collection} should have something to check"
    for record in records:
        assert not hasattr(record, "subscriber_ref")
        assert not hasattr(record, "msisdn")


def _stored_records(sut: ForesightService, collection: str) -> list[object]:
    readers = {
        SCENARIOS: lambda: list(sut.scenarios()),
        RUNS: lambda: list(sut.runs()),
        REPORTS: lambda: [sut.report_of_run(r.run_id) for r in sut.runs()],
        LAUNCHES: lambda: list(sut.launches()),
        OUTCOMES: lambda: [o for ln in sut.launches() for o in sut.outcomes_of(ln.launch_id)],
        CALIBRATIONS: lambda: list(sut.calibrations()),
        SPIKES: lambda: list(sut.spikes()),
    }
    return [record for record in readers[collection]() if record is not None]


def _spike() -> DetectedSpike:
    return DetectedSpike(
        spike_id="SPK-1",
        scope=SpikeScope.CHANNEL,
        scope_ref="app",
        window_start=_AT,
        window_end=_AT + timedelta(hours=1),
        observed=40,
        baseline=Decimal("10"),
        detected_at=_AT,
    )


# --------------------------------------------------------------------------- #
# Append-only is enforced, not remembered
# --------------------------------------------------------------------------- #


def test_a_stored_scenario_version_cannot_be_rewritten():
    """Editing version 1 would change what an already-stored run rehearsed."""
    store = MemoryStore()
    version = ScenarioVersion.first(scenario(), at=_AT, by="staff:pm")

    with MemoryUnitOfWork(store) as unit:
        StoredForesightRepository.of(unit).save_version(version)
        unit.commit()

    with MemoryUnitOfWork(store) as unit, pytest.raises(AppendOnlyWrite):
        StoredForesightRepository.of(unit).save_version(
            replace(version, created_by="somebody else")
        )


def test_a_recorded_outcome_cannot_be_rewritten():
    """This is the row somebody would edit to make the gate look open."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    launch = sut.record_launch(
        scenario_version_id=version.version_id, provenance=Provenance.SYNTHETIC, by="staff:pm"
    )
    outcome = sut.record_outcome(
        launch_id=launch.launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="staff:pm",
    )

    store = MemoryStore()
    with MemoryUnitOfWork(store) as unit:
        StoredForesightRepository.of(unit).save_outcome(outcome)
        unit.commit()
    with MemoryUnitOfWork(store) as unit, pytest.raises(AppendOnlyWrite):
        StoredForesightRepository.of(unit).save_outcome(replace(outcome, band=VolumeBand.LOW))


def test_a_run_may_be_rewritten_because_it_has_a_lifecycle():
    """The exception that proves the rule: a poll needs the row to move."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    run, _ = sut.request_run(version.version_id, by="staff:pm", idempotency_key="k")

    sut.execute(run.run_id)

    assert sut.run(run.run_id) is not None
    assert sut.run(run.run_id).status is RunStatus.SUCCEEDED  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# Scenario versions
# --------------------------------------------------------------------------- #


def test_a_draft_is_version_one_and_supersedes_nothing():
    version = service().draft(scenario(), by="staff:pm")

    assert version.version == 1
    assert version.supersedes is None
    assert version.created_by == "staff:pm"


def test_a_revision_keeps_the_family_and_points_at_what_it_replaced():
    sut = service()
    first = sut.draft(scenario(), by="staff:pm")

    second = sut.revise(replace(first.scenario, name="Retire the 10GB pack, phased"), by="staff:cx")

    assert second.scenario_id == first.scenario_id
    assert second.version == 2
    assert second.supersedes == first.version_id
    assert [v.version for v in sut.versions_of(first.scenario_id)] == [1, 2]


def test_both_versions_survive_a_revision():
    """A run citing version 1 must still be able to read version 1."""
    sut = service()
    first = sut.draft(scenario(), by="staff:pm")
    sut.revise(replace(first.scenario, severity=Decimal("2.0")), by="staff:pm")

    assert sut.version(first.version_id) is not None
    assert sut.version(first.version_id).scenario.severity == Decimal("1.0")  # type: ignore[union-attr]


def test_revising_a_scenario_nobody_drafted_is_refused():
    with pytest.raises(UnknownScenario):
        service().revise(scenario(), by="staff:pm")


def test_a_version_cannot_be_grafted_onto_a_different_family():
    sut = service()
    first = sut.draft(scenario("one"), by="staff:pm")

    with pytest.raises(ValueError, match="different scenario"):
        first.next(scenario("two"), at=_AT, by="staff:pm")


def test_scenarios_lists_the_latest_version_of_each_family():
    sut = service()
    first = sut.draft(scenario("one"), by="staff:pm")
    sut.revise(replace(first.scenario, name="one, revised"), by="staff:pm")
    sut.draft(scenario("two"), by="staff:pm")

    latest = sut.scenarios()

    assert len(latest) == 2
    assert {v.scenario.name for v in latest} == {"one, revised", "two"}


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #


def test_a_requested_run_starts_queued():
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")

    run, fresh = sut.request_run(version.version_id, by="staff:pm", idempotency_key="k")

    assert fresh
    assert run.status is RunStatus.QUEUED
    assert run.scenario_version_id == version.version_id


def test_a_repeated_request_returns_the_original_run():
    """I8. The risk here is not a double charge, it is a double finding."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")

    first, fresh = sut.request_run(version.version_id, by="staff:pm", idempotency_key="same")
    second, again = sut.request_run(version.version_id, by="staff:pm", idempotency_key="same")

    assert fresh and not again
    assert second.run_id == first.run_id
    assert len(sut.runs()) == 1


def test_a_different_key_starts_a_second_run():
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")

    sut.request_run(version.version_id, by="staff:pm", idempotency_key="one")
    sut.request_run(version.version_id, by="staff:pm", idempotency_key="two")

    assert len(sut.runs()) == 2


def test_a_repeat_after_the_run_finished_still_gets_the_original_outcome():
    """A duplicate gets the original outcome, not a fresh queued run (I8, D1)."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    first, _ = sut.request_run(version.version_id, by="staff:pm", idempotency_key="same")
    sut.execute(first.run_id)

    repeat, fresh = sut.request_run(version.version_id, by="staff:pm", idempotency_key="same")

    assert not fresh
    assert repeat.run_id == first.run_id
    assert repeat.status is RunStatus.SUCCEEDED
    assert repeat.report_id is not None


def test_running_a_scenario_version_nobody_drafted_is_refused():
    with pytest.raises(UnknownScenario):
        service().request_run("SCV-nothing", by="staff:pm", idempotency_key="k")


def test_executing_stores_the_report_against_the_run():
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    run, _ = sut.request_run(version.version_id, by="staff:pm", idempotency_key="k")

    stored = sut.execute(run.run_id)

    assert stored.run_id == run.run_id
    assert stored.scenario_version_id == version.version_id
    assert stored.report.predictions
    assert sut.report_of_run(run.run_id) == stored


def test_the_report_id_is_the_engines_own_id_not_the_job_id():
    """Two identifiers, deliberately. Conflating them finds nothing."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    run, _ = sut.request_run(version.version_id, by="staff:pm", idempotency_key="k")

    stored = sut.execute(run.run_id)

    assert stored.report_id == stored.report.run_id
    assert stored.report_id != run.run_id


def test_a_finished_run_cannot_be_executed_again():
    """Its report is append-only, so a second execution would collide."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    run, _ = sut.request_run(version.version_id, by="staff:pm", idempotency_key="k")
    sut.execute(run.run_id)

    with pytest.raises(RunAlreadyFinished):
        sut.execute(run.run_id)


def test_executing_a_run_nobody_requested_is_refused():
    with pytest.raises(UnknownRun):
        service().execute("RUN-nothing")


def test_a_run_that_fails_says_so_rather_than_vanishing():
    """A rehearsal that could not be computed is a thing somebody needs to see."""
    store = MemoryStore()
    broken = ForesightService(
        open_unit=lambda: MemoryUnitOfWork(store),
        catalogue=ForesightCatalogue(PolicyResolver()),  # no keys at all
        clock=lambda: _AT,
    )
    version = broken.draft(scenario(), by="staff:pm")
    run, _ = broken.request_run(version.version_id, by="staff:pm", idempotency_key="k")

    with pytest.raises(Exception):  # noqa: B017 - the resolver's own error type
        broken.execute(run.run_id)

    failed = broken.run(run.run_id)
    assert failed is not None
    assert failed.status is RunStatus.FAILED
    assert failed.failure
    assert broken.report_of_run(run.run_id) is None


# --------------------------------------------------------------------------- #
# Evidence and the gate
# --------------------------------------------------------------------------- #


def test_recording_a_real_launch_is_refused_until_c6_wires_the_locks():
    """An ungated way to write the evidence is worth more than the gate."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")

    with pytest.raises(RealLaunchNotPermitted):
        sut.record_launch(
            scenario_version_id=version.version_id,
            provenance=Provenance.REAL,
            by="staff:pm",
            evidence_ref="JIRA-1",
        )


def test_a_refused_real_launch_is_not_quietly_downgraded_to_synthetic():
    """A caller whose evidence silently did not count finds out at the gate."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")

    with pytest.raises(RealLaunchNotPermitted):
        sut.record_launch(
            scenario_version_id=version.version_id,
            provenance=Provenance.REAL,
            by="staff:pm",
        )

    assert sut.launches() == []


def test_a_launch_against_a_scenario_nobody_drafted_is_refused():
    with pytest.raises(UnknownScenario):
        service().record_launch(
            scenario_version_id="SCV-nothing",
            provenance=Provenance.SYNTHETIC,
            by="staff:pm",
        )


def test_outcomes_are_separate_rows_so_a_late_one_is_an_insert():
    """An append-only launch could not take a rewrite to add an observation."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    launch = sut.record_launch(
        scenario_version_id=version.version_id, provenance=Provenance.SYNTHETIC, by="staff:pm"
    )

    sut.record_outcome(
        launch_id=launch.launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="staff:cx",
    )
    sut.record_outcome(
        launch_id=launch.launch_id,
        theme="wrong pack after migration",
        segment="parents",
        band=VolumeBand.MEDIUM,
        by="staff:cx",
    )

    assert len(sut.outcomes_of(launch.launch_id)) == 2


def test_an_outcome_for_a_launch_nobody_recorded_is_refused():
    with pytest.raises(KeyError):
        service().record_outcome(
            launch_id="LNC-nothing",
            theme="t",
            segment="s",
            band=VolumeBand.LOW,
            by="staff:cx",
        )


def test_a_backtest_assembles_its_launches_from_the_stored_outcomes():
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    launch = sut.record_launch(
        scenario_version_id=version.version_id, provenance=Provenance.SYNTHETIC, by="staff:pm"
    )
    sut.record_outcome(
        launch_id=launch.launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="staff:cx",
    )

    stored = sut.backtest(by="staff:risk")

    assert stored.launch_ids == (launch.launch_id,)
    assert stored.report.compared == 1
    assert stored.computed_by == "staff:risk"


def test_a_synthetic_backtest_still_reports_not_calibrated_once_stored():
    """I16, now with the evidence in a table rather than in a literal."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    launch = sut.record_launch(
        scenario_version_id=version.version_id, provenance=Provenance.SYNTHETIC, by="staff:pm"
    )
    sut.record_outcome(
        launch_id=launch.launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="staff:cx",
    )

    stored = sut.backtest(by="staff:risk")

    assert stored.report.status is CalibrationStatus.NOT_CALIBRATED
    assert not stored.report.is_calibrated


def test_the_latest_calibration_is_the_most_recently_computed_one():
    store = MemoryStore()
    moments = iter([_AT, _AT, _AT, _AT + timedelta(days=1), _AT + timedelta(days=1)])
    current = {"now": _AT}

    def clock() -> datetime:
        current["now"] = next(moments, current["now"])
        return current["now"]

    sut = ForesightService(
        open_unit=lambda: MemoryUnitOfWork(store), catalogue=catalogue(), clock=clock
    )
    first = sut.backtest(by="staff:risk")
    second = sut.backtest(by="staff:risk")

    assert {c.calibration_id for c in sut.calibrations()} == {
        first.calibration_id,
        second.calibration_id,
    }
    latest = sut.latest_calibration()
    assert latest is not None
    assert latest.computed_at == max(c.computed_at for c in sut.calibrations())


def test_a_report_rests_on_the_stored_calibration_rather_than_one_it_chose():
    """A report that picked its own backtest could be handed a friendlier one."""
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    sut.backtest(by="staff:risk")
    run, _ = sut.request_run(version.version_id, by="staff:pm", idempotency_key="k")

    stored = sut.execute(run.run_id)

    assert stored.report.calibration is not None
    assert not stored.report.is_decision_ready


def test_a_run_with_no_calibration_yet_says_it_is_not_backtested():
    sut = service()
    version = sut.draft(scenario(), by="staff:pm")
    run, _ = sut.request_run(version.version_id, by="staff:pm", idempotency_key="k")

    stored = sut.execute(run.run_id)

    assert stored.report.calibration is None
    assert not stored.report.is_decision_ready
    assert any("not backtested" in c.lower() for c in stored.report.caveats)


# --------------------------------------------------------------------------- #
# Radar storage (C5 supplies the detector)
# --------------------------------------------------------------------------- #


def test_a_detected_spike_is_kept():
    sut = service()

    sut.record_spike(_spike())

    assert [s.spike_id for s in sut.spikes()] == ["SPK-1"]


def test_a_spike_scope_is_a_code_not_a_name():
    """`_FORBIDDEN_SEGMENTS` rejects a `name` field on the event this becomes."""
    spike = _spike()

    assert not hasattr(spike, "channel_name")
    assert not hasattr(spike, "scope_name")
    assert spike.scope_ref == "app"


def test_a_spike_against_no_baseline_reports_no_ratio_rather_than_a_huge_one():
    """A window with nothing to compare against is not "infinitely bad"."""
    spike = replace(_spike(), baseline=Decimal("0"))

    assert spike.ratio is None


def test_a_spike_ratio_is_exact():
    assert _spike().ratio == Decimal("4")
