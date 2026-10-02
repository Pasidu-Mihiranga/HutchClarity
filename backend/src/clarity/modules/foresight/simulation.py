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

**Prototype note.** Plan §3.4 uses MiroFish/OASIS swarm simulation. This is the
statistical baseline that plan §12.9 requires *alongside* it - historic
complaint rates per segment, scaled by how much the change affects each one.
The baseline is what a simulation would be calibrated against, and it carries
no licensing or maturity risk. Until it is backtested on ≥3 real launches
(plan §3.4 gate), neither should be used to make a launch decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from clarity.kernel.common import money
from clarity.kernel.ids import new_id


class ChangeType(StrEnum):
    PACK_RETIRED = "pack_retired"
    PRICE_INCREASE = "price_increase"
    FUP_TIGHTENED = "fup_tightened"
    POLICY_CHANGE = "policy_change"
    OUTAGE = "outage"


class VolumeBand(StrEnum):
    """Relative, never absolute. An exact count would imply a precision we do not have."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class Segment:
    """An aggregated persona. No individual data (deck S8)."""

    name: str
    share_of_base: Decimal
    """Fraction of the subscriber base, 0-1."""
    monthly_complaint_rate: Decimal
    """Historic complaints per subscriber per month, from aggregates."""
    price_sensitivity: Decimal = Decimal("1.0")
    data_intensity: Decimal = Decimal("1.0")

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.share_of_base <= Decimal("1"):
            raise ValueError("share_of_base must be a fraction between 0 and 1")


#: Illustrative segments from the deck (S11: students, dual-SIM, tourists,
#: parents). Shares and rates are **ASSUMPTIONS** for the demo and must be
#: replaced with real aggregates before any launch decision.
DEMO_SEGMENTS: tuple[Segment, ...] = (
    Segment("students", Decimal("0.28"), Decimal("0.09"), Decimal("1.6"), Decimal("1.8")),
    Segment("dual-SIM users", Decimal("0.22"), Decimal("0.06"), Decimal("1.3"), Decimal("0.9")),
    Segment("parents", Decimal("0.19"), Decimal("0.07"), Decimal("1.1"), Decimal("1.0")),
    Segment("tourists", Decimal("0.06"), Decimal("0.12"), Decimal("0.7"), Decimal("1.4")),
    Segment("low-usage prepaid", Decimal("0.25"), Decimal("0.04"), Decimal("1.4"), Decimal("0.5")),
)

#: Which complaint themes a change type tends to produce, and how strongly.
#: Derived from the deck's known causes (S11), not from a model.
_THEMES: dict[ChangeType, tuple[tuple[str, Decimal, str], ...]] = {
    ChangeType.PACK_RETIRED: (
        ("pack sunset confusion", Decimal("1.8"), "data_intensity"),
        ("wrong pack after migration", Decimal("1.2"), "data_intensity"),
        ("balance burn after pack ends", Decimal("1.0"), "data_intensity"),
    ),
    ChangeType.PRICE_INCREASE: (
        ("unexpected charge amount", Decimal("1.6"), "price_sensitivity"),
        ("balance disappeared faster", Decimal("1.1"), "price_sensitivity"),
    ),
    ChangeType.FUP_TIGHTENED: (
        ("data stopped at cap", Decimal("2.0"), "data_intensity"),
        ("unlimited not unlimited", Decimal("1.4"), "data_intensity"),
    ),
    ChangeType.POLICY_CHANGE: (
        ("consent and subscription confusion", Decimal("1.3"), "price_sensitivity"),
    ),
    ChangeType.OUTAGE: (
        ("service unavailable", Decimal("2.4"), "data_intensity"),
        ("pack validity lost during outage", Decimal("1.5"), "data_intensity"),
    ),
}


@dataclass
class Scenario:
    """A change to rehearse."""

    name: str
    change_type: ChangeType
    affected_share: Decimal = Decimal("1.0")
    """Fraction of the base the change touches."""
    severity: Decimal = Decimal("1.0")
    """How big the change is, relative to a typical one of its type."""
    segments: tuple[Segment, ...] = DEMO_SEGMENTS

    @property
    def scenario_id(self) -> str:
        return new_id("SIM")


@dataclass
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
    caveats: list[str] = field(default_factory=list)
    backtested: bool = False

    @property
    def top_themes(self) -> list[str]:
        seen: list[str] = []
        for prediction in self.predictions:
            if prediction.theme not in seen:
                seen.append(prediction.theme)
        return seen

    @property
    def is_decision_ready(self) -> bool:
        """False until backtested against real launches (plan §3.4 gate)."""
        return self.backtested


_MITIGATIONS: dict[str, str] = {
    "pack sunset confusion": "Publish a migration card and a self-service flow before the change.",
    "wrong pack after migration": "Add a provisioning check and a one-tap correction.",
    "balance burn after pack ends": "Offer data-stop and a spend cap at pack end.",
    "unexpected charge amount": "Show the new price in the pack truth label before purchase.",
    "balance disappeared faster": "Send a proactive balance alert for affected segments.",
    "data stopped at cap": "State the cap and after-cap speed at purchase; alert at 80% and 95%.",
    "unlimited not unlimited": "Rename the offer and disclose the cap prominently.",
    "consent and subscription confusion": "Re-confirm consent and brief agents on the new policy.",
    "service unavailable": "Prepare an outage notice with an honest ETA.",
    "pack validity lost during outage": "Pre-approve a validity extension rule.",
}


class Foresight:
    """Statistical rehearsal of a change. Deterministic and explainable."""

    #: Score thresholds for the bands. Relative within one run.
    _HIGH = Decimal("0.045")
    _MEDIUM = Decimal("0.015")

    def run(self, scenario: Scenario) -> ForesightReport:
        predictions: list[Prediction] = []

        for theme, weight, driver in _THEMES.get(scenario.change_type, ()):
            for segment in scenario.segments:
                sensitivity = getattr(segment, driver, Decimal("1.0"))
                score = (
                    segment.share_of_base
                    * segment.monthly_complaint_rate
                    * weight
                    * sensitivity
                    * scenario.severity
                    * scenario.affected_share
                )
                predictions.append(
                    Prediction(
                        theme=theme,
                        segment=segment.name,
                        band=self._band(score),
                        relative_score=money(score * 1000) / 1000,
                        suggested_mitigation=_MITIGATIONS.get(
                            theme, "Review with CX before launch."
                        ),
                    )
                )

        predictions.sort(key=lambda p: p.relative_score, reverse=True)
        return ForesightReport(
            run_id=new_id("FOR"),
            scenario=scenario.name,
            predictions=predictions,
            basis=(
                "Statistical baseline over aggregated segments. No individual "
                "customer data was read."
            ),
            caveats=[
                "Scenarios, not certainties (deck S11).",
                "Volume bands are relative within this run and are not complaint counts.",
                "Segment shares and complaint rates are ASSUMPTIONS for the demo.",
                "Not backtested against real launches, so not usable for a launch decision.",
            ],
            backtested=False,
        )

    def _band(self, score: Decimal) -> VolumeBand:
        if score >= self._HIGH:
            return VolumeBand.HIGH
        if score >= self._MEDIUM:
            return VolumeBand.MEDIUM
        return VolumeBand.LOW
