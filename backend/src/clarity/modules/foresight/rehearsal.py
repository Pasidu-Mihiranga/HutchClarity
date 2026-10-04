"""Baseline headline, one comparison column (C3/F04, F11).

This file is where invariant I1 stops being a convention and becomes something a
caller cannot get around. The rule the plan sets out is that a propensity which
feeds a reported band is a decision-shaped number, so **the statistical baseline
is always the headline and any other driver is a comparison column**.

The structure enforces it rather than documenting it:

- :class:`PersonaRehearsal` constructs its own :class:`StatisticalBaseline`. It
  is not a constructor argument, so there is no value a caller can pass to put a
  model in charge of the reported band.
- The only injectable driver is named ``comparison`` and its output only ever
  reaches :attr:`RehearsalReport.comparison`.
- :attr:`RehearsalReport.predictions`, the bands anybody acts on, are built from
  the baseline alone.

Reporting the LLM column as the primary band would be an amendment to I1 and an
ADR, not a change of argument here.

**What the comparison is for, and what it is not.** A disagreement is a prompt
to go and look: two methods shaped differently expect different things, and the
pairs where they diverge are where the segment assumptions are doing the most
work. Agreement proves nothing, because both rest on the same segment
catalogue, and the report says so rather than letting a reader infer confidence
from a high agreement rate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from clarity.kernel.ids import new_id
from clarity.modules.foresight.catalogue import Bands, ForesightCatalogue
from clarity.modules.foresight.personas import (
    PersonaRun,
    PersonaSimulator,
    StatisticalBaseline,
)
from clarity.modules.foresight.simulation import (
    Foresight,
    ForesightReport,
    Prediction,
    Scenario,
    VolumeBand,
    score_of,
)

#: Said on every rehearsal, because a reader who sees two columns will otherwise
#: read the second as a second opinion.
_AGREEMENT_MEANS_NOTHING = (
    "Agreement between the two methods is not evidence that either is right: "
    "both rest on the same segment catalogue and neither has been calibrated "
    "against a real launch."
)
_HEADLINE_IS_THE_BASELINE = (
    "The reported bands are the statistical baseline's. The comparison column is "
    "a second method's view and never sets a band (I1)."
)


@dataclass(frozen=True)
class PairComparison:
    """One theme-segment pair, as each method sees it."""

    theme: str
    segment: str
    headline: VolumeBand
    headline_propensity: Decimal
    comparison: VolumeBand | None
    comparison_propensity: Decimal | None
    """``None`` when the comparison driver gave no estimate for this pair.

    Absent is not zero. A zero propensity is the finding that a segment will not
    complain; a missing one is the absence of a view.
    """

    @property
    def agrees(self) -> bool | None:
        """Whether both methods land in the same band, or ``None`` if only one did."""
        if self.comparison is None:
            return None
        return self.headline is self.comparison


@dataclass(frozen=True)
class RehearsalReport:
    """A foresight report plus the second method's column."""

    rehearsal_id: str
    seed: int
    headline_simulator: str
    report: ForesightReport
    comparison_simulator: str | None = None
    comparison: tuple[PairComparison, ...] = ()
    basis: str = ""
    caveats: tuple[str, ...] = field(default_factory=tuple)
    provenance: str = "SYNTHETIC"
    """Everything here is simulated and labelled as such (I16)."""

    @property
    def predictions(self) -> list[Prediction]:
        """The bands anybody acts on. The baseline's, always."""
        return self.report.predictions

    @property
    def compared_pairs(self) -> int:
        return sum(1 for pair in self.comparison if pair.comparison is not None)

    @property
    def agreement_rate(self) -> Decimal | None:
        """Share of compared pairs where both methods agreed.

        ``None`` when nothing was comparable, rather than ``0`` or ``1``: with no
        overlap there is no agreement to report, and either number would read as
        a finding about the methods.
        """
        compared = [pair for pair in self.comparison if pair.agrees is not None]
        if not compared:
            return None
        agreed = sum(1 for pair in compared if pair.agrees)
        return (Decimal(agreed) / Decimal(len(compared))).quantize(Decimal("0.001"))


class PersonaRehearsal:
    """Run the baseline, and optionally a second method beside it."""

    def __init__(
        self,
        catalogue: ForesightCatalogue,
        *,
        comparison: PersonaSimulator | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalogue = catalogue
        # Constructed here, never injected: this is the I1 boundary.
        self._headline = StatisticalBaseline(catalogue)
        self._comparison = comparison
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    @property
    def comparison_version(self) -> str | None:
        return self._comparison.version if self._comparison is not None else None

    def run(self, scenario: Scenario, *, seed: int = 42) -> RehearsalReport:
        report = Foresight(self._catalogue, clock=self._clock).run(scenario)

        as_of = scenario.as_of
        bands = self._catalogue.bands(as_of)
        segments = scenario.segments
        if segments is None:
            segments = self._catalogue.segments(as_of)
        shares = {segment.name: segment.share_of_base for segment in segments}

        headline = self._headline.propensities(scenario, seed=seed)
        second: PersonaRun | None = None
        if self._comparison is not None:
            second = self._comparison.propensities(scenario, seed=seed)

        other = second.by_pair() if second is not None and second.answered else {}
        comparison = tuple(
            PairComparison(
                theme=pair.theme,
                segment=pair.segment,
                headline=self._band(pair.value, shares[pair.segment], bands),
                headline_propensity=pair.value,
                comparison=(
                    self._band(other[(pair.theme, pair.segment)].value, shares[pair.segment], bands)
                    if (pair.theme, pair.segment) in other
                    else None
                ),
                comparison_propensity=(
                    other[(pair.theme, pair.segment)].value
                    if (pair.theme, pair.segment) in other
                    else None
                ),
            )
            for pair in headline.propensities
        )

        return RehearsalReport(
            rehearsal_id=new_id("REH"),
            seed=seed,
            headline_simulator=self._headline.version,
            report=report,
            comparison_simulator=second.simulator if second is not None else None,
            comparison=comparison,
            basis=self._basis(headline, second),
            caveats=self._caveats(headline, second),
        )

    # ----------------------------------------------------------------- #

    def _band(self, propensity: Decimal, share: Decimal, bands: Bands) -> VolumeBand:
        score = score_of(propensity, share)
        if score >= bands.high:
            return VolumeBand.HIGH
        if score >= bands.medium:
            return VolumeBand.MEDIUM
        return VolumeBand.LOW

    def _basis(self, headline: PersonaRun, second: PersonaRun | None) -> str:
        if second is None:
            return f"Headline: {headline.basis}"
        return f"Headline: {headline.basis} Comparison: {second.basis}"

    def _caveats(self, headline: PersonaRun, second: PersonaRun | None) -> tuple[str, ...]:
        caveats = [_HEADLINE_IS_THE_BASELINE, *headline.caveats]
        if second is None:
            return tuple(caveats)
        if not second.answered:
            caveats.append(
                f"The {second.simulator} comparison did not answer, so there is no "
                "second column. That is not agreement."
            )
            caveats.extend(second.caveats)
            return tuple(caveats)
        caveats.extend(second.caveats)
        caveats.append(_AGREEMENT_MEANS_NOTHING)
        return tuple(caveats)


__all__ = [
    "PairComparison",
    "PersonaRehearsal",
    "RehearsalReport",
]
