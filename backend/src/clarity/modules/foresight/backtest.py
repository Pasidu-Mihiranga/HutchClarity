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
2. **Below the gate the report says so.** Fewer than
   :data:`MIN_REAL_LAUNCHES` real launches gives
   :attr:`CalibrationStatus.INSUFFICIENT`, in the same shape as an
   ``UNEVALUABLE`` evaluation gate: a number is still reported, and it still
   does not mean the model is calibrated.
3. **Nothing comparable reports no error, not a perfect one.** With zero
   overlapping (theme, segment) pairs the error fields are ``None``. A
   ``0.000`` would read as a flawless model.

The error is measured in **band steps** (LOW=0, MEDIUM=1, HIGH=2), because
that is the only thing the baseline emits. It is never a complaint count.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from clarity.kernel.ids import new_id
from clarity.modules.foresight.simulation import (
    ChangeType,
    Foresight,
    Scenario,
    VolumeBand,
)

#: Plan 02 §3.4 gate. Three is the plan's number, not a statistical claim.
MIN_REAL_LAUNCHES = 3

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
    """Replay historic launches through the baseline and score the bands."""

    def run(
        self,
        launches: tuple[HistoricLaunch, ...],
        *,
        foresight: Foresight | None = None,
    ) -> CalibrationReport:
        engine = foresight or Foresight()

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
            status=self._status(real),
            mean_absolute_band_error=self._mean(abs(m.step_error) for m in misses),
            signed_band_error=self._mean(m.step_error for m in misses),
            exact_band_rate=self._rate(sum(1 for m in misses if m.is_exact), len(misses)),
            top_theme_hit_rate=self._rate(top_hits, top_scored),
            misses=tuple(misses),
            unpredicted=tuple(unpredicted),
            unobserved=tuple(unobserved),
            basis=(
                "Replay of recorded launch outcomes against the statistical "
                "baseline, aggregated per segment. No individual customer data "
                "was read."
            ),
            caveats=self._caveats(launches, real, misses, unpredicted, unobserved),
        )

    # ----------------------------------------------------------------- #

    def _status(self, real: int) -> CalibrationStatus:
        if real == 0:
            return CalibrationStatus.NOT_CALIBRATED
        if real < MIN_REAL_LAUNCHES:
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
        misses: list[BandMiss],
        unpredicted: list[ObservedOutcome],
        unobserved: list[tuple[str, str]],
    ) -> list[str]:
        caveats = [
            "Results are scenarios, not certainties (deck S11). A calibration "
            "error does not turn a prediction into a forecast.",
            "The error is measured in band steps (LOW, MEDIUM, HIGH), not in "
            "complaints. Bands are relative within one run.",
            "Advisory only: a calibration report never authorises an automated action.",
        ]
        synthetic = len(launches) - real
        if synthetic:
            caveats.append(
                f"{synthetic} of {len(launches)} launches are SIMULATED, authored "
                "for the prototype. A synthetic backtest exercises the method and "
                "validates nothing."
            )
        if real < MIN_REAL_LAUNCHES:
            caveats.append(
                f"{real} real launches against the {MIN_REAL_LAUNCHES} the plan "
                "§3.4 gate requires, so this report does not establish calibration."
            )
        if not misses:
            caveats.append(
                "No observed theme matched a predicted one, so no calibration "
                "error could be measured."
            )
        signed = self._mean(m.step_error for m in misses)
        if signed is not None and signed < 0:
            caveats.append(
                "The baseline under-predicted on average, which is the dangerous "
                "direction for CX capacity planning."
            )
        if unpredicted:
            caveats.append(
                "Observed theme-segment outcomes never predicted at all: "
                f"{len(unpredicted)}. They are excluded from the error."
            )
        if unobserved:
            caveats.append(
                "Predicted theme-segment pairs with no recorded outcome: "
                f"{len(unobserved)}. Absence of a record is not a LOW observation."
            )
        return caveats


#: SIMULATED historic launches so the backtest can be run and read today.
#: Outcomes are authored, not measured, and are deliberately not a perfect
#: match for the baseline: a synthetic backtest that scored 100% would be a
#: lie about the method (I16).
DEMO_LAUNCHES: tuple[HistoricLaunch, ...] = (
    HistoricLaunch(
        launch_id="SIM-LAUNCH-1",
        scenario=Scenario(name="Retire the 10GB pack", change_type=ChangeType.PACK_RETIRED),
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
