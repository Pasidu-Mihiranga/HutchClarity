"""The calibration gate, and the four locks that keep it honestly shut (C6/F09).

Plan 02 section 3.4 says no launch decision rests on the baseline until it has
been backtested on at least three real launches. That sentence is only worth
anything if the gate cannot be opened by the people who want it open, so this
file is mostly about the ways it could be and is not:

1. **The threshold is a policy key with a `min: 3` guardrail that bites.** Until
   C6 it did not: policy YAML quotes its numbers so they load as strings, and
   `Guardrail.permits` returned `True` for anything that was not a `Decimal` or
   an `int`. Every guardrail in the repository was declared and none of them
   checked anything.
2. **`CALIBRATED` is computed from `Provenance.REAL` alone.** Synthetic launches
   are counted, reported and excluded.
3. **Recording a `REAL` launch takes two keys**: a capability the composition
   root supplied, and an external reference somebody can go and check.
4. **The history is append-only**, so a recorded outcome cannot be edited into a
   better one.

The last test is the golden one: no sequence of calls available to a caller in
any shipped profile reaches `CALIBRATED`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction

import pytest

from clarity.modules.foresight.backtest import (
    Backtest,
    CalibrationStatus,
    HistoricLaunch,
    ObservedOutcome,
    Provenance,
    _ranks,
    _spearman,
)
from clarity.modules.foresight.catalogue import (
    MIN_REAL_LAUNCHES_KEY,
    ChangeType,
    ForesightCatalogue,
)
from clarity.modules.foresight.service import (
    ForesightService,
    RealLaunchNotPermitted,
)
from clarity.modules.foresight.simulation import Scenario, VolumeBand
from clarity.platform.config.artefacts import Guardrail, PolicyKey, PolicyValue, Tag
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork
from tests.conftest import POLICY_DIR

_AT = datetime(2027, 1, 1, tzinfo=UTC)
_EFFECTIVE = date(2027, 10, 1)


def catalogue() -> ForesightCatalogue:
    return ForesightCatalogue(PolicyResolver.from_directory(POLICY_DIR))


def service(*, real_launches: object | None = None) -> ForesightService:
    store = MemoryStore()
    return ForesightService(
        open_unit=lambda: MemoryUnitOfWork(store),
        catalogue=catalogue(),
        clock=lambda: _AT,
        real_launches=real_launches,  # type: ignore[arg-type]
    )


def scenario(name: str = "Retire the 10GB pack") -> Scenario:
    return Scenario(name=name, change_type=ChangeType.PACK_RETIRED, effective_date=_EFFECTIVE)


class Allowed:
    """A capability that says yes. No shipped profile wires one."""

    def permits(self) -> bool:
        return True

    def describe(self) -> str:
        return "test-capability"


class Withdrawn:
    """A capability that exists but is currently withheld."""

    def permits(self) -> bool:
        return False

    def describe(self) -> str:
        return "withdrawn"


# --------------------------------------------------------------------------- #
# Lock 1: the guardrail actually bites
# --------------------------------------------------------------------------- #


def test_a_quoted_number_is_checked_against_its_guardrail():
    """The bug this closes: policy YAML quotes its numbers, so every value
    reaching `permits` was a `str` and every guardrail passed everything."""
    bounded = Guardrail(min=Decimal("3"))

    assert not bounded.permits("2")
    assert bounded.permits("3")
    assert bounded.permits("4")


def test_a_value_that_is_not_a_number_still_passes():
    """Some keys are genuinely textual, and a bound on those means nothing."""
    assert Guardrail(min=Decimal("3")).permits("80,95")


def test_a_boolean_is_not_treated_as_a_number():
    """`True` is an `int` in Python, and a bounded key must not accept a switch."""
    assert Guardrail(min=Decimal("3")).permits(True)
    assert Guardrail(max=Decimal("0")).permits(True)


def test_lowering_the_gate_below_three_is_refused_at_load():
    """The whole point of lock 1: a published value under three cannot exist."""
    with pytest.raises(ValueError, match="guardrail"):
        PolicyKey(
            key=MIN_REAL_LAUNCHES_KEY,
            kind="number",
            owner_role="risk",
            tags={Tag.REGULATORY},
            guardrail=Guardrail(min=Decimal("3")),
            values=[PolicyValue(value="1", version=1)],
        )


def test_the_shipped_gate_key_carries_the_guardrail_and_the_class():
    key = PolicyResolver.from_directory(POLICY_DIR).key(MIN_REAL_LAUNCHES_KEY)

    assert key.guardrail is not None
    assert key.guardrail.min == Decimal("3")
    assert key.change_class.needs_second_approver, "C4: raising is routine, lowering is not"


# --------------------------------------------------------------------------- #
# Lock 2: only real launches count
# --------------------------------------------------------------------------- #


def real(launch: HistoricLaunch) -> HistoricLaunch:
    """Relabel a simulated launch, to prove the gate opens on real evidence only.

    No real launch record exists in the prototype (REQUIRES HUTCH CONFIRMATION).
    """
    from dataclasses import replace

    return replace(launch, provenance=Provenance.REAL)


def synthetic_launch(index: int) -> HistoricLaunch:
    return HistoricLaunch(
        launch_id=f"SIM-{index}",
        scenario=scenario(f"launch {index}"),
        observed=(
            ObservedOutcome("pack sunset confusion", "students", VolumeBand.HIGH),
            ObservedOutcome("wrong pack after migration", "parents", VolumeBand.MEDIUM),
        ),
    )


@pytest.mark.parametrize("count", [1, 3, 10, 50])
def test_no_number_of_synthetic_launches_reaches_calibrated(count: int):
    """I16: a launch we authored is the predictor's own assumptions played back."""
    launches = tuple(synthetic_launch(index) for index in range(count))

    report = Backtest(catalogue(), clock=lambda: _AT).run(launches)

    assert report.real_launches == 0
    assert report.status is CalibrationStatus.NOT_CALIBRATED
    assert not report.is_calibrated


def test_mixing_synthetic_launches_in_does_not_help():
    launches = (real(synthetic_launch(0)), synthetic_launch(1), synthetic_launch(2))

    report = Backtest(catalogue(), clock=lambda: _AT).run(launches)

    assert report.real_launches == 1
    assert report.status is CalibrationStatus.INSUFFICIENT


def test_three_real_launches_open_the_gate():
    """The gate must be wired to evidence, not hard-coded shut."""
    launches = tuple(real(synthetic_launch(index)) for index in range(3))

    report = Backtest(catalogue(), clock=lambda: _AT).run(launches)

    assert report.status is CalibrationStatus.CALIBRATED
    assert report.is_calibrated


# --------------------------------------------------------------------------- #
# Lock 3: two keys to record a real launch
# --------------------------------------------------------------------------- #


def test_without_the_capability_a_real_launch_is_refused():
    sut = service()
    version = sut.draft(scenario(), by="staff:cx")

    with pytest.raises(RealLaunchNotPermitted, match="no real launch records"):
        sut.record_launch(
            scenario_version_id=version.version_id,
            provenance=Provenance.REAL,
            by="staff:cx",
            evidence_ref="HUTCH-LAUNCH-1",
        )


def test_a_withdrawn_capability_is_refused():
    sut = service(real_launches=Withdrawn())
    version = sut.draft(scenario(), by="staff:cx")

    with pytest.raises(RealLaunchNotPermitted):
        sut.record_launch(
            scenario_version_id=version.version_id,
            provenance=Provenance.REAL,
            by="staff:cx",
            evidence_ref="HUTCH-LAUNCH-1",
        )


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_the_capability_alone_is_not_enough_without_evidence(missing: str | None):
    """Without a reference somebody can check, the record is an assertion."""
    sut = service(real_launches=Allowed())
    version = sut.draft(scenario(), by="staff:cx")

    with pytest.raises(RealLaunchNotPermitted, match="evidence reference"):
        sut.record_launch(
            scenario_version_id=version.version_id,
            provenance=Provenance.REAL,
            by="staff:cx",
            evidence_ref=missing,
        )


def test_both_keys_together_record_the_launch_and_what_permitted_it():
    sut = service(real_launches=Allowed())
    version = sut.draft(scenario(), by="staff:cx")

    launch = sut.record_launch(
        scenario_version_id=version.version_id,
        provenance=Provenance.REAL,
        by="staff:cx",
        evidence_ref="HUTCH-LAUNCH-1",
    )

    assert launch.is_real
    assert launch.evidence_ref == "HUTCH-LAUNCH-1"
    assert launch.authority == "test-capability", "a report can say what let it"


def test_a_refusal_writes_nothing():
    """Checked before anything is stored, so there is no half-counting row."""
    sut = service(real_launches=Allowed())
    version = sut.draft(scenario(), by="staff:cx")

    with pytest.raises(RealLaunchNotPermitted):
        sut.record_launch(
            scenario_version_id=version.version_id,
            provenance=Provenance.REAL,
            by="staff:cx",
        )

    assert sut.launches() == []


def test_a_synthetic_launch_carries_no_authority():
    sut = service(real_launches=Allowed())
    version = sut.draft(scenario(), by="staff:cx")

    launch = sut.record_launch(
        scenario_version_id=version.version_id,
        provenance=Provenance.SYNTHETIC,
        by="staff:cx",
    )

    assert launch.authority == ""


# --------------------------------------------------------------------------- #
# The golden test: the gate stays shut for everything a caller can do
# --------------------------------------------------------------------------- #


def test_no_sequence_available_in_a_shipped_profile_reaches_calibrated():
    """The one that would have to fail before any of this could be bypassed.

    Every lever a caller has in a shipped profile: draft as many scenarios as
    they like, record as many launches as they like, record as many outcomes as
    they like, backtest as often as they like. The capability is absent in every
    profile, so every launch is synthetic, so the gate stays shut.
    """
    sut = service()  # no capability, as every shipped profile builds it

    for index in range(10):
        version = sut.draft(scenario(f"scenario {index}"), by="staff:pm")
        with pytest.raises(RealLaunchNotPermitted):
            sut.record_launch(
                scenario_version_id=version.version_id,
                provenance=Provenance.REAL,
                by="staff:cx",
                evidence_ref=f"made-up-{index}",
            )
        launch = sut.record_launch(
            scenario_version_id=version.version_id,
            provenance=Provenance.SYNTHETIC,
            by="staff:cx",
        )
        for theme in ("pack sunset confusion", "wrong pack after migration"):
            sut.record_outcome(
                launch_id=launch.launch_id,
                theme=theme,
                segment="students",
                band=VolumeBand.HIGH,
                by="staff:cx",
            )
        stored = sut.backtest(by="staff:risk")
        assert stored.report.status is CalibrationStatus.NOT_CALIBRATED
        assert not stored.report.is_calibrated

    assert all(not launch.is_real for launch in sut.launches())
    assert len(sut.calibrations()) == 10, "lock 4: every backtest is kept"


def test_the_container_wires_no_real_launch_capability():
    """Lock 3, checked on the composition root rather than on the intention."""
    from clarity.app.container import Clarity

    clarity = Clarity()

    assert clarity.foresight_service._real_launches is None


# --------------------------------------------------------------------------- #
# Plan 08 section 12.9's two metrics
# --------------------------------------------------------------------------- #


def test_theme_recall_counts_the_themes_the_model_never_predicted():
    """The dangerous direction. Without recall the band error improves as the
    model predicts less, because what it never predicted is excluded from it."""
    launch = HistoricLaunch(
        launch_id="SIM-1",
        scenario=scenario(),
        observed=(
            ObservedOutcome("pack sunset confusion", "students", VolumeBand.HIGH),
            ObservedOutcome("roaming bill shock", "tourists", VolumeBand.HIGH),
        ),
    )

    report = Backtest(catalogue(), clock=lambda: _AT).run((launch,))

    assert report.theme_recall == Decimal("0.500"), "one of two themes was anticipated"
    assert any(o.theme == "roaming bill shock" for o in report.unpredicted)


def test_theme_recall_is_one_when_every_observed_theme_was_predicted():
    launch = HistoricLaunch(
        launch_id="SIM-1",
        scenario=scenario(),
        observed=(ObservedOutcome("pack sunset confusion", "students", VolumeBand.HIGH),),
    )

    report = Backtest(catalogue(), clock=lambda: _AT).run((launch,))

    assert report.theme_recall == Decimal("1.000")


def test_theme_recall_is_none_when_nothing_was_observed():
    launch = HistoricLaunch(launch_id="SIM-1", scenario=scenario(), observed=())

    report = Backtest(catalogue(), clock=lambda: _AT).run((launch,))

    assert report.theme_recall is None


def test_a_theme_observed_in_four_segments_is_one_theme():
    """A theme is something the model did or did not anticipate, once."""
    launch = HistoricLaunch(
        launch_id="SIM-1",
        scenario=scenario(),
        observed=tuple(
            ObservedOutcome("pack sunset confusion", segment, VolumeBand.HIGH)
            for segment in ("students", "parents", "tourists", "dual-SIM users")
        ),
    )

    report = Backtest(catalogue(), clock=lambda: _AT).run((launch,))

    assert report.theme_recall == Decimal("1.000")


def test_the_rank_correlation_is_exact_and_needs_no_dependency():
    """Plan 08 section 12.9 asks for the metric, not for scipy."""
    descending = [Decimal(3), Decimal(2), Decimal(1)]
    ascending = [Decimal(1), Decimal(2), Decimal(3)]
    tied = [Decimal(3), Decimal(1), Decimal(1)]

    assert _spearman(descending, descending) == 1
    assert _spearman(descending, ascending) == -1
    assert isinstance(_spearman(descending, tied), Fraction)


def test_an_entirely_tied_observation_has_no_ranking():
    """One band for every segment is not an ordering, and scoring it as
    agreement or disagreement would invent one nobody observed."""
    assert _spearman([Decimal(3), Decimal(2)], [Decimal(1), Decimal(1)]) is None
    assert _ranks([Decimal(1), Decimal(1), Decimal(1)]) is None


def test_a_single_segment_cannot_be_ranked():
    assert _spearman([Decimal(1)], [Decimal(1)]) is None


def test_tied_ranks_are_averaged_rather_than_ordered_arbitrarily():
    ranks = _ranks([Decimal(5), Decimal(3), Decimal(3), Decimal(1)])

    assert ranks is not None
    assert ranks[1] == ranks[2] == Fraction(5, 2), "the second and third places, shared"


def test_the_rank_correlation_is_none_when_no_launch_can_be_ranked():
    launch = HistoricLaunch(
        launch_id="SIM-1",
        scenario=scenario(),
        observed=(ObservedOutcome("pack sunset confusion", "students", VolumeBand.HIGH),),
    )

    report = Backtest(catalogue(), clock=lambda: _AT).run((launch,))

    assert report.segment_rank_correlation is None


def test_the_rank_correlation_is_reported_when_segments_can_be_ordered():
    launch = HistoricLaunch(
        launch_id="SIM-1",
        scenario=scenario(),
        observed=(
            ObservedOutcome("pack sunset confusion", "students", VolumeBand.HIGH),
            ObservedOutcome("pack sunset confusion", "tourists", VolumeBand.LOW),
            ObservedOutcome("pack sunset confusion", "parents", VolumeBand.MEDIUM),
        ),
    )

    report = Backtest(catalogue(), clock=lambda: _AT).run((launch,))

    assert report.segment_rank_correlation is not None
    assert Decimal("-1") <= report.segment_rank_correlation <= Decimal("1")


def test_the_band_step_metrics_are_still_reported_beside_the_new_ones():
    """Plan 08 section 12.9 asked for both; the code had only band-step error."""
    report = Backtest(catalogue(), clock=lambda: _AT).run((synthetic_launch(0),))

    assert report.mean_absolute_band_error is not None
    assert report.exact_band_rate is not None
    assert report.theme_recall is not None
