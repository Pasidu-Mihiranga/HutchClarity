"""Foresight: rehearse a change before it ships (deck S11).

Seed a change - a new pack, a price, a policy, an outage - build a world of
aggregated personas, and see which complaints it would produce. The output
becomes migration cards, scripts and flows *before* launch.

Three constraints are built in rather than documented, because they are what
separates a planning aid from a liability:

1. **Aggregates only.** Personas are segment statistics. No individual
   customer's data is read, ever (deck S8: "Foresight on aggregates only").
2. **Scenarios, not certainties.** Output is themes and relative volume bands
   with an uncertainty note - never an absolute forecast. The deck's own
   footnote is the rule here.
3. **Advisory only.** Nothing here can trigger a customer action. It returns a
   report; a product manager decides what to do with it.

**Prototype note.** Plan section 3.4 uses MiroFish/OASIS swarm simulation. This
is the statistical baseline that plan section 12.9 requires *alongside* it:
historic complaint rates per segment, scaled by how much the change affects each
one. The baseline is what a simulation would be calibrated against, and it
carries no licensing or maturity risk. Until it is backtested on at least three
real launches (plan section 3.4 gate), neither should be used to make a launch
decision.

**What C1 changed and why.** Every tunable here used to be a Python constant and
every sentence a literal. Both now come from outside the engine: numbers from
the policy store (I10) and wording from ``platform/content/foresight.py``. Two
consequences are deliberate and load-bearing:

- :class:`Scenario` carries a required ``effective_date``, and the whole run
  resolves policy ``as_of`` that date. A rehearsal is about a change that lands
  on a day, so the parameters it uses are the ones in force on that day. Before
  C1 the field was an optional free-text string that nothing read.
- :class:`Scenario` is frozen and its ``scenario_id`` is a real field. It used
  to be a ``@property`` calling ``new_id``, so every read returned a different
  id: a scenario could not be stored, compared or cited, which is also why
  nothing stored one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from clarity.kernel.common import money
from clarity.kernel.ids import new_id
from clarity.modules.foresight.catalogue import (
    Bands,
    ChangeType,
    ForesightCatalogue,
    Segment,
    ThemeCatalogue,
)
from clarity.modules.foresight.personas import Propensity, StatisticalBaseline
from clarity.platform.content import foresight as wording

if TYPE_CHECKING:  # the backtest imports this module, so only for typing
    from clarity.modules.foresight.backtest import CalibrationReport


class VolumeBand(StrEnum):
    """Relative, never absolute. An exact count would imply a precision we do not have."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def score_of(propensity: Decimal, share_of_base: Decimal) -> Decimal:
    """A per-segment propensity weighted by how big the segment is.

    The number the volume bands are read against. Separating it from the
    propensity is what lets two methods be compared: a cohort simulation and a
    rate model both answer "what share of this segment complains", and how much
    of the base that segment is belongs to the reporting step rather than to
    either method (C3).
    """
    return propensity * share_of_base


def as_of_for(effective_date: date) -> datetime:
    """The moment a scenario's policy is resolved at.

    Midnight UTC on the day the change takes effect. A change is announced for a
    date rather than an instant, and resolving at the start of that day is the
    reading that includes a value whose window opens on it.
    """
    return datetime.combine(effective_date, time.min, tzinfo=UTC)


@dataclass(frozen=True)
class Scenario:
    """A change to rehearse.

    Frozen, because a run cites the scenario it rehearsed and a scenario that
    could change afterwards would make the citation meaningless.
    """

    name: str
    change_type: ChangeType
    effective_date: date
    """When the change takes effect. Drives policy resolution for the whole run."""
    affected_share: Decimal = Decimal("1.0")
    """Fraction of the base the change touches."""
    severity: Decimal = Decimal("1.0")
    """How big the change is, relative to a typical one of its type."""
    segments: tuple[Segment, ...] | None = None
    """Explicit segments, or ``None`` for the policy catalogue at ``effective_date``."""
    affected_products: tuple[str, ...] = ()
    business_context: str = ""
    scenario_id: str = field(default_factory=lambda: new_id("SIM"))

    @property
    def as_of(self) -> datetime:
        return as_of_for(self.effective_date)


@dataclass(frozen=True)
class Prediction:
    """One predicted theme for one segment."""

    theme: str
    segment: str
    band: VolumeBand
    relative_score: Decimal
    """Comparable within a run only. Not a complaint count."""
    suggested_mitigation: str


@dataclass
class ForesightReport:
    """Advisory output. Never an input to an automated action."""

    run_id: str
    scenario: str
    predictions: list[Prediction]
    basis: str
    scenario_id: str = ""
    effective_date: date | None = None
    generated_at: datetime | None = None
    """When the run happened, from the injected clock (I11)."""
    caveats: list[str] = field(default_factory=list)
    backtested: bool = False
    calibration: CalibrationReport | None = None
    """The backtest this report rests on, if any (plan 02 section 3.4)."""

    @property
    def top_themes(self) -> list[str]:
        seen: list[str] = []
        for prediction in self.predictions:
            if prediction.theme not in seen:
                seen.append(prediction.theme)
        return seen

    @property
    def is_decision_ready(self) -> bool:
        """False until backtested against real launches (plan section 3.4 gate)."""
        return self.backtested


class Foresight:
    """Statistical rehearsal of a change. Deterministic and explainable.

    Deterministic given the same scenario *and the same policy values*: two runs
    of one scenario agree because they resolve the same keys at the same
    ``as_of``, not because the numbers are compiled in.
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
        self, scenario: Scenario, *, calibration: CalibrationReport | None = None
    ) -> ForesightReport:
        as_of = scenario.as_of
        bands = self._catalogue.bands(as_of)
        catalogue = self._catalogue.themes(scenario.change_type, as_of)
        segments = scenario.segments
        if segments is None:
            segments = self._catalogue.segments(as_of)
        shares = {segment.name: segment.share_of_base for segment in segments}

        # The baseline is reached through the same port the comparison drivers
        # use (C3), so the reported numbers and the headline column of a
        # comparison are provably the same arithmetic rather than two copies of
        # it that can drift.
        baseline = StatisticalBaseline(self._catalogue).propensities(scenario)
        predictions = [
            self._prediction(propensity, shares[propensity.segment], bands)
            for propensity in baseline.propensities
        ]
        predictions.sort(key=lambda p: p.relative_score, reverse=True)

        return ForesightReport(
            run_id=new_id("FOR"),
            scenario=scenario.name,
            scenario_id=scenario.scenario_id,
            effective_date=scenario.effective_date,
            generated_at=self._clock(),
            predictions=predictions,
            basis=wording.BASIS,
            caveats=self._caveats(scenario, catalogue, bands, calibration),
            backtested=calibration is not None and calibration.is_calibrated,
            calibration=calibration,
        )

    def _prediction(
        self, propensity: Propensity, share_of_base: Decimal, bands: Bands
    ) -> Prediction:
        score = score_of(propensity.value, share_of_base)
        return Prediction(
            theme=propensity.theme,
            segment=propensity.segment,
            band=self._band(score, bands),
            relative_score=money(score * 1000) / 1000,
            suggested_mitigation=wording.mitigation_for(propensity.theme),
        )

    # ----------------------------------------------------------------- #

    def _caveats(
        self,
        scenario: Scenario,
        catalogue: ThemeCatalogue,
        bands: Bands,
        calibration: CalibrationReport | None,
    ) -> list[str]:
        caveats = [
            wording.CAVEATS["scenarios_not_certainties"],
            wording.CAVEATS["bands_are_relative"],
            wording.CAVEATS["segments_are_assumptions"],
        ]
        if catalogue.borrowed_from is not None:
            caveats.append(
                wording.borrowed_themes_caveat(
                    scenario.change_type.value, catalogue.borrowed_from.value
                )
            )
        if not catalogue.themes:
            caveats.append(wording.no_themes_caveat(scenario.change_type.value))
        if not bands.is_ordered:
            caveats.append(wording.band_thresholds_caveat())

        if calibration is None:
            caveats.append(wording.CAVEATS["not_backtested"])
            return caveats
        caveats.append(f"Backtest: {calibration.summary()}")
        if not calibration.is_calibrated:
            caveats.append(wording.CAVEATS["gate_not_reached"])
        return caveats

    def _band(self, score: Decimal, bands: Bands) -> VolumeBand:
        if score >= bands.high:
            return VolumeBand.HIGH
        if score >= bands.medium:
            return VolumeBand.MEDIUM
        return VolumeBand.LOW


__all__ = [
    "ChangeType",
    "Foresight",
    "ForesightReport",
    "Prediction",
    "Scenario",
    "Segment",
    "VolumeBand",
    "as_of_for",
    "score_of",
]
