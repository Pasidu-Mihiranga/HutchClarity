"""Backtest the foresight baseline and report how wrong it is (plan 02 §3.4).

The module docstring in :mod:`clarity.modules.foresight.simulation` sets the
gate: until the baseline has been backtested on at least three real launches,
no launch decision may rest on it. This file is the machinery that gate needs,
and it is deliberately built so that running it cannot *create* the evidence
the gate asks for:

1. **A synthetic launch never moves the status.** The prototype ships
   :data:`DEMO_LAUNCHES` so the report can be produced and read today, but a
   launch authored by us is the predictor's own assumptions played back. It
   exercises the method; it validates nothing (I16).
2. **Below the gate the report says so.** Fewer real launches than
   ``foresight.calibration.min_real_launches`` gives
   :attr:`CalibrationStatus.INSUFFICIENT`, in the same shape as an
   ``UNEVALUABLE`` evaluation gate: a number is still reported, and it still
   does not mean the model is calibrated.
3. **Nothing comparable reports no error, not a perfect one.** With zero
   overlapping (theme, segment) pairs the error fields are ``None``. A
   ``0.000`` would read as a flawless model.

The error is measured in **band steps** (LOW=0, MEDIUM=1, HIGH=2), because
that is the only thing the baseline emits. It is never a complaint count.

**C1 note.** The gate itself is no longer a Python constant. It resolves from
``foresight.calibration.min_real_launches``, tagged regulatory so lowering it
needs a second approver, with a guardrail that refuses a value under three
whatever the approval says. The constant is gone rather than kept as a fallback:
a default here would be a number shadowing a policy value, which is exactly what
D2 forbids.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from clarity.kernel.ids import new_id
from clarity.modules.foresight.catalogue import ChangeType, ForesightCatalogue
from clarity.modules.foresight.simulation import (
    Foresight,
    Scenario,
    VolumeBand,
)
from clarity.platform.content import foresight as wording

_BAND_STEP: dict[VolumeBand, int] = {
    VolumeBand.LOW: 0,
    VolumeBand.MEDIUM: 1,
    VolumeBand.HIGH: 2,
}

_RATIO = Decimal("0.001")


class Provenance(StrEnum):
    """Where a historic launch came from. Drives the whole honesty story."""

    SYNTHETIC = "synthetic"
    """Authored for the prototype. Labelled everywhere it appears (I16)."""
    REAL = "real"
    """A real HUTCH launch with recorded complaint outcomes.

    REQUIRES HUTCH CONFIRMATION: no such record exists in the prototype.
    """


class CalibrationStatus(StrEnum):
    NOT_CALIBRATED = "not_calibrated"
    """No real launch evidence at all."""
    INSUFFICIENT = "insufficient"
    """Some real launches, below the plan §3.4 gate."""
    CALIBRATED = "calibrated"
    """At or above the gate. Only reachable from real launches."""


@dataclass(frozen=True)
class ObservedOutcome:
    """What a launch actually produced for one theme in one segment."""

    theme: str
    segment: str
    band: VolumeBand


@dataclass(frozen=True)
class HistoricLaunch:
    """A past change plus the complaint bands it actually produced."""

    launch_id: str
    scenario: Scenario
    observed: tuple[ObservedOutcome, ...]
    provenance: Provenance = Provenance.SYNTHETIC

    @property
    def is_real(self) -> bool:
        return self.provenance is Provenance.REAL


@dataclass(frozen=True)
class BandMiss:
    """One compared pair. ``step_error`` is signed: above zero over-predicts."""

    launch_id: str
    theme: str
    segment: str
    predicted: VolumeBand
    observed: VolumeBand

    @property
    def step_error(self) -> int:
        return _BAND_STEP[self.predicted] - _BAND_STEP[self.observed]

    @property
    def is_exact(self) -> bool:
        return self.predicted is self.observed


@dataclass
class CalibrationReport:
    """How wrong the baseline was, and whether that number means anything."""

    run_id: str
    launches: int
    real_launches: int
    compared: int
    status: CalibrationStatus
    mean_absolute_band_error: Decimal | None
    """Mean |predicted - observed| in band steps. ``None`` if nothing compared."""
    signed_band_error: Decimal | None
    """Mean signed error. Below zero means the model under-predicted."""
    exact_band_rate: Decimal | None
    """Share of compared pairs where the band was exactly right."""
    top_theme_hit_rate: Decimal | None
    """Share of launches whose worst observed theme the model ranked first."""
    misses: tuple[BandMiss, ...] = ()
    unpredicted: tuple[ObservedOutcome, ...] = ()
    """Observed themes the model never predicted. The dangerous direction."""
    unobserved: tuple[tuple[str, str], ...] = ()
    """(theme, segment) the model predicted with no record either way."""
    basis: str = ""
    caveats: list[str] = field(default_factory=list)

    @property
    def is_calibrated(self) -> bool:
        return self.status is CalibrationStatus.CALIBRATED

    def summary(self) -> str:
        """One line a product manager can read without misreading it."""
        if self.mean_absolute_band_error is None:
            error = "calibration error: not measurable, no comparable pairs"
        else:
            error = (
                f"calibration error: {self.mean_absolute_band_error} band steps "
                f"mean absolute over {self.compared} compared pairs"
            )
        return (
            f"{error}; status {self.status.value} "
            f"({self.real_launches} real of {self.launches} launches). "
            "Results are scenarios, not certainties."
        )


class Backtest:
    """Replay historic launches through the baseline and score the bands.

    The gate is resolved ``as_of`` the moment the backtest runs, not as of any
    launch: the question a calibration report answers is "may we rely on this
    engine now", and the answer is governed by the rule in force now.
    """

    def __init__(
        self,
        catalogue: ForesightCatalogue,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalogue = catalogue
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    def run(
        self,
        launches: tuple[HistoricLaunch, ...],
        *,
        foresight: Foresight | None = None,
    ) -> CalibrationReport:
        engine = foresight or Foresight(self._catalogue, clock=self._clock)
        required = self._catalogue.min_real_launches(self._clock())

        misses: list[BandMiss] = []
        unpredicted: list[ObservedOutcome] = []
        unobserved: list[tuple[str, str]] = []
        top_hits = 0
        top_scored = 0

        for launch in launches:
            predicted = engine.run(launch.scenario)
            by_key = {(p.theme, p.segment): p for p in predicted.predictions}
            seen: set[tuple[str, str]] = set()

            for outcome in launch.observed:
                key = (outcome.theme, outcome.segment)
                prediction = by_key.get(key)
                if prediction is None:
                    unpredicted.append(outcome)
                    continue
                seen.add(key)
                misses.append(
                    BandMiss(
                        launch_id=launch.launch_id,
                        theme=outcome.theme,
                        segment=outcome.segment,
                        predicted=prediction.band,
                        observed=outcome.band,
                    )
                )

            unobserved.extend(sorted(set(by_key) - seen))

            worst = self._worst_observed_themes(launch)
            if worst and predicted.top_themes:
                top_scored += 1
                if predicted.top_themes[0] in worst:
                    top_hits += 1

        real = sum(1 for launch in launches if launch.is_real)
        return CalibrationReport(
            run_id=new_id("CAL"),
            launches=len(launches),
            real_launches=real,
            compared=len(misses),
            status=self._status(real, required),
            mean_absolute_band_error=self._mean(abs(m.step_error) for m in misses),
            signed_band_error=self._mean(m.step_error for m in misses),
            exact_band_rate=self._rate(sum(1 for m in misses if m.is_exact), len(misses)),
            top_theme_hit_rate=self._rate(top_hits, top_scored),
            misses=tuple(misses),
            unpredicted=tuple(unpredicted),
            unobserved=tuple(unobserved),
            basis=wording.BACKTEST_BASIS,
            caveats=self._caveats(launches, real, required, misses, unpredicted, unobserved),
        )

    # ----------------------------------------------------------------- #

    def _status(self, real: int, required: int) -> CalibrationStatus:
        if real == 0:
            return CalibrationStatus.NOT_CALIBRATED
        if real < required:
            return CalibrationStatus.INSUFFICIENT
        return CalibrationStatus.CALIBRATED

    def _mean(self, values: Iterable[int]) -> Decimal | None:
        collected = list(values)
        if not collected:
            return None
        total = sum((Decimal(v) for v in collected), Decimal(0))
        return (total / Decimal(len(collected))).quantize(_RATIO)

    def _rate(self, hits: int, total: int) -> Decimal | None:
        if total == 0:
            return None
        return (Decimal(hits) / Decimal(total)).quantize(_RATIO)

    def _worst_observed_themes(self, launch: HistoricLaunch) -> set[str]:
        if not launch.observed:
            return set()
        worst = max(_BAND_STEP[o.band] for o in launch.observed)
        return {o.theme for o in launch.observed if _BAND_STEP[o.band] == worst}

    def _caveats(
        self,
        launches: tuple[HistoricLaunch, ...],
        real: int,
        required: int,
        misses: list[BandMiss],
        unpredicted: list[ObservedOutcome],
        unobserved: list[tuple[str, str]],
    ) -> list[str]:
        caveats = [
            wording.BACKTEST_CAVEATS["error_is_not_a_forecast"],
            wording.BACKTEST_CAVEATS["band_steps_not_complaints"],
            wording.BACKTEST_CAVEATS["advisory_only"],
        ]
        synthetic = len(launches) - real
        if synthetic:
            caveats.append(wording.synthetic_launches_caveat(synthetic, len(launches)))
        if real < required:
            caveats.append(wording.below_gate_caveat(real, required))
        if not misses:
            caveats.append(wording.BACKTEST_CAVEATS["nothing_comparable"])
        signed = self._mean(m.step_error for m in misses)
        if signed is not None and signed < 0:
            caveats.append(wording.BACKTEST_CAVEATS["under_predicted"])
        if unpredicted:
            caveats.append(wording.unpredicted_caveat(len(unpredicted)))
        if unobserved:
            caveats.append(wording.unobserved_caveat(len(unobserved)))
        return caveats


#: SIMULATED historic launches so the backtest can be run and read today.
#: Outcomes are authored, not measured, and are deliberately not a perfect
#: match for the baseline: a synthetic backtest that scored 100% would be a
#: lie about the method (I16).
DEMO_LAUNCHES: tuple[HistoricLaunch, ...] = (
    HistoricLaunch(
        launch_id="SIM-LAUNCH-1",
        scenario=Scenario(
            name="Retire the 10GB pack",
            change_type=ChangeType.PACK_RETIRED,
            effective_date=date(2026, 3, 1),
        ),
        observed=(
            ObservedOutcome("pack sunset confusion", "students", VolumeBand.HIGH),
            ObservedOutcome("pack sunset confusion", "low-usage prepaid", VolumeBand.MEDIUM),
            ObservedOutcome("wrong pack after migration", "students", VolumeBand.MEDIUM),
            ObservedOutcome("wrong pack after migration", "parents", VolumeBand.MEDIUM),
            ObservedOutcome("balance burn after pack ends", "dual-SIM users", VolumeBand.LOW),
        ),
    ),
    HistoricLaunch(
        launch_id="SIM-LAUNCH-2",
        scenario=Scenario(
            name="Tighten the FUP on the unlimited plan",
            change_type=ChangeType.FUP_TIGHTENED,
            effective_date=date(2026, 5, 1),
            severity=Decimal("1.4"),
        ),
        observed=(
            ObservedOutcome("data stopped at cap", "students", VolumeBand.HIGH),
            ObservedOutcome("data stopped at cap", "parents", VolumeBand.HIGH),
            ObservedOutcome("unlimited not unlimited", "students", VolumeBand.HIGH),
            ObservedOutcome("unlimited not unlimited", "tourists", VolumeBand.LOW),
        ),
    ),
    HistoricLaunch(
        launch_id="SIM-LAUNCH-3",
        scenario=Scenario(
            name="Raise the per-MB out-of-bundle rate",
            change_type=ChangeType.PRICE_INCREASE,
            effective_date=date(2026, 7, 1),
            affected_share=Decimal("0.6"),
        ),
        observed=(
            ObservedOutcome("unexpected charge amount", "students", VolumeBand.MEDIUM),
            ObservedOutcome("unexpected charge amount", "low-usage prepaid", VolumeBand.MEDIUM),
            ObservedOutcome("balance disappeared faster", "parents", VolumeBand.MEDIUM),
            ObservedOutcome("roaming bill shock", "tourists", VolumeBand.HIGH),
        ),
    ),
)
