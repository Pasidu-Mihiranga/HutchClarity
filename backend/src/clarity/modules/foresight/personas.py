"""How a segment reacts to a change, behind one port (C3/F04, F11).

What this replaces is worth stating plainly. The previous "swarm" took the
statistical baseline, hashed ``seed:scenario:theme:segment``, took two hex
digits modulo three minus one, and shifted the baseline's band by that. Then it
compared the result against a second run of the same baseline and reported the
agreement. It measured a hash. Nothing about personas, complaints or the change
entered into it.

**The port returns propensities, never bands and never counts.** A propensity is
the share of a segment expected to complain about one theme in the month after
the change, in [0, 1]. Three things follow, and all three are the reason for the
choice:

1. Two drivers are comparable. A band is the output of a threshold, so two
   drivers that band their own numbers can disagree because they banded
   differently rather than because they expect different things.
2. Banding stays in the module, under the policy thresholds C1 put there. A
   driver cannot widen its own HIGH band.
3. A count is a claim about volume that none of these methods can support. The
   deck's footnote is the rule: scenarios, not certainties.

**I1 and the LLM driver.** A propensity that feeds a reported band is a
decision-shaped number, so the statistical baseline stays the headline and any
other driver is a comparison column. :class:`~clarity.modules.foresight.rehearsal.PersonaRehearsal`
makes that structural rather than conventional: it constructs the baseline
itself and accepts only a *comparison* simulator, so there is no argument a
caller can pass to put a model in charge of the reported band. Changing that is
an ADR and an amendment to I1, not a constructor argument.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Protocol

from clarity.modules.foresight.catalogue import (
    ForesightCatalogue,
    PersonaRounds,
    Segment,
    ThemeWeight,
)

if TYPE_CHECKING:  # simulation imports this module, so only for typing
    from clarity.modules.foresight.simulation import Scenario

_ONE = Decimal("1")
_ZERO = Decimal("0")
#: Propensities are reported to six places. Beyond that the drivers are
#: claiming a precision none of them has.
_PLACES = Decimal("0.000001")
#: Integer scale for the round-based driver's draws. Comparing an integer draw
#: against an integer threshold keeps the simulation exact: no float ever enters
#: a propensity, which is the same instinct as I3 even though this is not money.
_DRAW_SCALE = 1_000_000


@dataclass(frozen=True)
class Propensity:
    """Share of **one segment** expected to complain about one theme, in [0, 1].

    Per segment, not per subscriber base. That is what makes two drivers
    comparable: a cohort simulation naturally answers "how many of this segment
    complained", and a rate model naturally answers the same question once its
    segment-share factor is left out. How big the segment is belongs to the
    reporting step, not to the method, and
    :func:`~clarity.modules.foresight.simulation.score_of` is where it is
    applied.
    """

    theme: str
    segment: str
    value: Decimal

    def __post_init__(self) -> None:
        if not _ZERO <= self.value <= _ONE:
            raise ValueError(
                f"propensity {self.value} for {self.theme}/{self.segment} is not in [0, 1]"
            )


@dataclass(frozen=True)
class PersonaRun:
    """What one driver produced, and enough to tell which driver it was."""

    simulator: str
    """Version string. Recorded on every run, so two reports can be compared."""
    propensities: tuple[Propensity, ...]
    basis: str
    caveats: tuple[str, ...] = ()
    answered: bool = True
    """False when the driver could not answer at all.

    A driver that could not run reports nothing rather than zeros. A zero
    propensity means "this segment will not complain", which is a finding; the
    absence of an answer is not.
    """

    def by_pair(self) -> dict[tuple[str, str], Propensity]:
        return {(p.theme, p.segment): p for p in self.propensities}


class PersonaSimulator(Protocol):
    """One method of guessing how a segment reacts."""

    @property
    def version(self) -> str: ...

    def propensities(self, scenario: Scenario, *, seed: int) -> PersonaRun: ...


def _clamp(value: Decimal) -> Decimal:
    """Into [0, 1], quantised. A propensity outside it is not a propensity."""
    bounded = min(_ONE, max(_ZERO, value))
    return bounded.quantize(_PLACES)


def _inputs(
    catalogue: ForesightCatalogue, scenario: Scenario
) -> tuple[tuple[ThemeWeight, ...], tuple[Segment, ...]]:
    as_of = scenario.as_of
    themes = catalogue.themes(scenario.change_type, as_of).themes
    segments = scenario.segments
    if segments is None:
        segments = catalogue.segments(as_of)
    return themes, segments


class StatisticalBaseline:
    """Historic complaint rates per segment, scaled by the change (plan 12.9).

    The same arithmetic the C1 engine reports, exposed through the port so the
    other drivers are compared against the thing they are meant to be compared
    against rather than against a second copy of themselves.
    """

    version = "statistical-baseline-v2"

    def __init__(self, catalogue: ForesightCatalogue) -> None:
        self._catalogue = catalogue

    def propensities(self, scenario: Scenario, *, seed: int = 0) -> PersonaRun:
        themes, segments = _inputs(self._catalogue, scenario)
        return PersonaRun(
            simulator=self.version,
            propensities=tuple(
                Propensity(
                    theme=theme.theme,
                    segment=segment.name,
                    value=_clamp(
                        segment.monthly_complaint_rate
                        * theme.weight
                        * theme.sensitivity_of(segment)
                        * scenario.severity
                        * scenario.affected_share
                    ),
                )
                for theme in themes
                for segment in segments
            ),
            basis=(
                "Historic complaint rates per aggregated segment, scaled by the "
                "change's severity and reach. No individual customer data was read."
            ),
            caveats=("The rates are ASSUMPTIONS for the prototype and have not been measured.",),
        )


class RoundBasedPersonaSimulator:
    """Aggregate cohorts stepped through awareness over several rounds (F11).

    Each segment is a cohort of identical agents, not individuals: the cohort
    size is a resolution setting, and no agent corresponds to a subscriber. An
    agent moves unaware to aware to affected, and an affected agent either
    complains or absorbs. The propensity is the share that complained.

    Deterministic given a seed, with no dependency beyond the standard library.
    Draws are integers against integer thresholds, so a propensity is an exact
    ratio of two counts and never a float.

    **Why it can disagree with the baseline, usefully.** The baseline multiplies
    rates together, so reach and severity scale it linearly. This one compounds
    over rounds, so a change that only a tenth of the base notices in round one
    can still reach most of them by round five. Where the two disagree is the
    interesting column; where they agree, neither is evidence for the other.
    """

    version = "round-based-persona-v1"

    def __init__(self, catalogue: ForesightCatalogue) -> None:
        self._catalogue = catalogue

    def propensities(self, scenario: Scenario, *, seed: int) -> PersonaRun:
        themes, segments = _inputs(self._catalogue, scenario)
        settings = self._catalogue.persona_rounds(scenario.as_of)
        results: list[Propensity] = []

        for theme in themes:
            for segment in segments:
                # One stream per pair, seeded from the run seed and the pair, so
                # adding a theme does not change another theme's draws.
                rng = random.Random(f"{seed}:{theme.theme}:{segment.name}")
                complained = self._cohort(theme, segment, scenario, settings, rng)
                results.append(
                    Propensity(
                        theme=theme.theme,
                        segment=segment.name,
                        value=_clamp(Decimal(complained) / Decimal(settings.cohort_size)),
                    )
                )

        return PersonaRun(
            simulator=self.version,
            propensities=tuple(results),
            basis=(
                f"Aggregate cohorts of {settings.cohort_size} identical agents per "
                f"segment, stepped through {settings.rounds} rounds of awareness. "
                "An agent is a share of a segment, never a subscriber, and no "
                "individual customer data was read."
            ),
            caveats=(
                "Scenarios, not certainties. The round parameters are ASSUMPTIONS "
                "for the prototype and have not been calibrated against a real launch.",
                "Agreement with the statistical baseline is not evidence that "
                "either is right: both rest on the same segment assumptions.",
            ),
        )

    def _cohort(
        self,
        theme: ThemeWeight,
        segment: Segment,
        scenario: Scenario,
        settings: PersonaRounds,
        rng: random.Random,
    ) -> int:
        aware_chance = _draw_threshold(settings.awareness_per_round * scenario.affected_share)
        affect_chance = _draw_threshold(
            theme.weight
            * theme.sensitivity_of(segment)
            * scenario.severity
            / settings.pressure_scale
        )
        complain_chance = _draw_threshold(
            segment.monthly_complaint_rate * settings.complaint_multiplier
        )

        # 0 unaware, 1 aware, 2 affected; an agent that has resolved is removed
        # from the cohort rather than stepped again.
        unaware = settings.cohort_size
        aware = 0
        affected = 0
        complained = 0

        for _ in range(settings.rounds):
            became_aware = _draws(rng, unaware, aware_chance)
            unaware -= became_aware
            aware += became_aware

            became_affected = _draws(rng, aware, affect_chance)
            aware -= became_affected
            affected += became_affected

            resolved = _draws(rng, affected, complain_chance)
            affected -= resolved
            complained += resolved

        return complained


def _draw_threshold(probability: Decimal) -> int:
    """A probability as an integer threshold on :data:`_DRAW_SCALE`."""
    bounded = min(_ONE, max(_ZERO, probability))
    return int(bounded * _DRAW_SCALE)


def _draws(rng: random.Random, population: int, threshold: int) -> int:
    """How many of ``population`` fall under ``threshold``. Exact, no floats."""
    if population <= 0 or threshold <= 0:
        return 0
    return sum(1 for _ in range(population) if rng.randrange(_DRAW_SCALE) < threshold)


class LlmPersonaSimulator:
    """Personas written in-house, asked of a model through the existing seam.

    **What it may and may not do.** It supplies a propensity, which is why it is
    a comparison column and never the headline (I1): a number that feeds a
    reported band is decision-shaped, and the rules decide. It is never asked
    for an amount, a band, a count or an action, and it cannot reach one: the
    only thing read out of its answer is a number per theme-segment pair, and
    anything outside [0, 1] or unparseable is dropped.

    **It never calls a model in the test suite.** The router it is given is the
    one the composition root built; under ``make check`` that router's providers
    are recorded ones (``ai/cassettes.py``), and a missing cassette is an error
    rather than a live call. If no provider answers, the run reports
    ``answered=False`` and the comparison column is absent, which is different
    from a column of zeros.

    Because the personas are written here rather than adopted from
    MiroFish/OASIS/Zep, plan 04 T8's licence gate does not apply.
    """

    version = "llm-persona-v1"

    #: The whole instruction. Deliberately narrow: a propensity per pair and
    #: nothing else, with no room to volunteer a recommendation or a figure.
    SYSTEM = (
        "You are modelling how aggregated customer segments of a telecom operator "
        "react to an announced change. For each theme and segment pair you are "
        "given, estimate the share of that segment who would complain about that "
        "theme in the month after the change. Answer with a JSON object mapping "
        '"theme||segment" to a number between 0 and 1, and nothing else. Do not '
        "recommend anything, do not give amounts or counts, and do not add text "
        "outside the JSON object."
    )

    def __init__(self, catalogue: ForesightCatalogue, *, router: PersonaRouter) -> None:
        self._catalogue = catalogue
        self._router = router

    def propensities(self, scenario: Scenario, *, seed: int) -> PersonaRun:
        themes, segments = _inputs(self._catalogue, scenario)
        pairs = [(theme.theme, segment.name) for theme in themes for segment in segments]
        if not pairs:
            return PersonaRun(
                simulator=self.version,
                propensities=(),
                basis="No theme-segment pairs to ask about.",
                answered=False,
            )

        answer = self._router.ask(
            system=self.SYSTEM,
            facts=self._facts(scenario, themes, segments, seed),
            pairs=pairs,
        )
        if answer is None:
            return PersonaRun(
                simulator=self.version,
                propensities=(),
                basis="No model answered, so this comparison column is absent.",
                caveats=("A column of zeros would read as a finding; an absent one does not.",),
                answered=False,
            )

        parsed = _parse_propensities(answer, pairs)
        dropped = len(pairs) - len(parsed)
        caveats = [
            "A model's estimate, kept as a comparison column only. The reported "
            "bands come from the statistical baseline (I1).",
            "Scenarios, not certainties. This has not been calibrated against a real launch.",
        ]
        if dropped:
            caveats.append(
                f"{dropped} of {len(pairs)} pairs were missing or out of range in the "
                "model's answer and were dropped rather than defaulted."
            )
        return PersonaRun(
            simulator=self.version,
            propensities=tuple(parsed),
            basis=(
                "An in-house persona prompt answered by the configured reason-role "
                "model. Only aggregated segment statistics were sent; no individual "
                "customer data was read."
            ),
            caveats=tuple(caveats),
            answered=True,
        )

    def _facts(
        self,
        scenario: Scenario,
        themes: tuple[ThemeWeight, ...],
        segments: tuple[Segment, ...],
        seed: int,
    ) -> dict[str, object]:
        """The read-only context. Aggregates and codes, no customer anything."""
        return {
            "change_type": scenario.change_type.value,
            "effective_date": scenario.effective_date.isoformat(),
            "severity": str(scenario.severity),
            "affected_share": str(scenario.affected_share),
            "seed": seed,
            "segments": [
                {
                    "segment": segment.name,
                    "share_of_base": str(segment.share_of_base),
                    "monthly_complaint_rate": str(segment.monthly_complaint_rate),
                    "price_sensitivity": str(segment.price_sensitivity),
                    "data_intensity": str(segment.data_intensity),
                }
                for segment in segments
            ],
            "themes": [
                {"theme": theme.theme, "weight": str(theme.weight), "driver": theme.driver}
                for theme in themes
            ],
        }


class PersonaRouter(Protocol):
    """The narrow slice of the AI layer the persona driver needs.

    A protocol rather than ``RoleRouter`` itself so the module depends on the
    question it asks, not on the routing machinery: the driver cannot reach a
    provider, a token bucket or another role through this.
    """

    def ask(
        self, *, system: str, facts: dict[str, object], pairs: list[tuple[str, str]]
    ) -> str | None:
        """The model's text, or ``None`` when nothing answered."""
        ...


_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def _parse_propensities(answer: str, pairs: list[tuple[str, str]]) -> list[Propensity]:
    """Read a propensity per pair, dropping anything that is not one.

    Dropping rather than defaulting is the point. A pair the model did not
    answer for, or answered with 1.5, or answered with "high", is a pair with no
    estimate; substituting zero would turn a non-answer into the finding that
    the segment will not complain.
    """
    document = _json_object(answer)
    if document is None:
        return []

    wanted = {f"{theme}||{segment}": (theme, segment) for theme, segment in pairs}
    found: list[Propensity] = []
    for key, raw in document.items():
        pair = wanted.get(key)
        if pair is None:
            continue
        value = _as_fraction(raw)
        if value is None:
            continue
        found.append(Propensity(theme=pair[0], segment=pair[1], value=value))
    return found


def _json_object(answer: str) -> dict[str, object] | None:
    """The JSON object in a model's answer, or ``None``.

    Tolerates the fenced block a model tends to wrap JSON in, and nothing more
    adventurous: a repair pass that guesses at malformed JSON is a way to invent
    numbers the model did not give.
    """
    text = answer.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        document = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _as_fraction(raw: object) -> Decimal | None:
    """A number in [0, 1] as an exact Decimal, or ``None``.

    Parsed from the string form so a JSON float never becomes a propensity by
    binary approximation.
    """
    if isinstance(raw, bool) or raw is None:
        return None
    text = str(raw).strip()
    if not _NUMBER.match(text):
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not _ZERO <= value <= _ONE:
        return None
    return value.quantize(_PLACES)


class RoleRouterPersonas:
    """:class:`PersonaRouter` over the AI layer's ``RoleRouter``.

    Lives here rather than in ``ai/`` because it is foresight's question, and
    the composition root is what joins the two. It asks the ``reason`` role,
    which is the role for "longer explanation over evidence, still never
    supplying an amount"; a propensity is the furthest that role goes here, and
    it goes into a comparison column.
    """

    def __init__(self, invoke: PersonaInvoke) -> None:
        self._invoke = invoke

    def ask(
        self, *, system: str, facts: dict[str, object], pairs: list[tuple[str, str]]
    ) -> str | None:
        asked = "\n".join(f"{theme}||{segment}" for theme, segment in pairs)
        return self._invoke(system, facts, asked)


class PersonaInvoke(Protocol):
    """The one call the composition root supplies, already masked and routed."""

    def __call__(self, system: str, facts: dict[str, object], user: str) -> str | None: ...


__all__ = [
    "LlmPersonaSimulator",
    "PersonaInvoke",
    "PersonaRouter",
    "PersonaRun",
    "PersonaSimulator",
    "Propensity",
    "RoleRouterPersonas",
    "RoundBasedPersonaSimulator",
    "StatisticalBaseline",
]
