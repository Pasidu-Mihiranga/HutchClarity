"""Persona drivers behind one port, and the I1 boundary (C3/F04, F11).

Replaces `test_foresight_swarm.py`. The thing it tested is gone: the previous
"swarm" hashed `seed:scenario:theme:segment`, took two hex digits modulo three
minus one, and shifted the baseline's band by that, then compared the result
against a second run of the same baseline. Its tests passed because a hash is
reproducible, which is true and says nothing about personas.

The tests that matter most here are the last section. I1 says the rules decide,
and a propensity that feeds a reported band is a decision-shaped number. So the
statistical baseline has to be the headline and a model can only ever be a
comparison column, and that has to be a thing a caller **cannot** get around
rather than a thing the documentation asks them not to do.
"""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from clarity.kernel.common import money
from clarity.modules.foresight.catalogue import (
    ChangeType,
    ForesightCatalogue,
)
from clarity.modules.foresight.personas import (
    LlmPersonaSimulator,
    PersonaSimulator,
    Propensity,
    RoleRouterPersonas,
    RoundBasedPersonaSimulator,
    StatisticalBaseline,
)
from clarity.modules.foresight.rehearsal import PersonaRehearsal
from clarity.modules.foresight.simulation import Foresight, Scenario, VolumeBand, score_of
from clarity.platform.config.artefacts import PolicyKey, PolicyValue, Tag
from clarity.platform.config.resolver import PolicyResolver
from tests.conftest import POLICY_DIR

_AT = datetime(2027, 1, 1, tzinfo=UTC)
_EFFECTIVE = date(2027, 10, 1)


def catalogue() -> ForesightCatalogue:
    return ForesightCatalogue(PolicyResolver.from_directory(POLICY_DIR))


def catalogue_with(**overrides: str) -> ForesightCatalogue:
    resolver = PolicyResolver.from_directory(POLICY_DIR)
    for key, value in overrides.items():
        resolver.add(
            PolicyKey(
                key=key.replace("__", "."),
                kind="number",
                owner_role="product",
                tags={Tag.OPERATIONAL},
                values=[PolicyValue(value=value, version=99)],
            )
        )
    return ForesightCatalogue(resolver)


def scenario(change_type: ChangeType = ChangeType.PACK_RETIRED) -> Scenario:
    return Scenario(name="probe", change_type=change_type, effective_date=_EFFECTIVE)


class StubRouter:
    """A fixed answer, labelled as a stub rather than dressed as a recording.

    **Not a cassette.** `ai/cassettes.py` replays what a real provider actually
    said, and no real recording for this prompt exists yet (plan F1). Writing a
    cassette by hand would present an authored answer as a measured one, which
    is the thing I16 forbids. So this is a stub, it says so, and recording the
    real thing stays F1's job.
    """

    def __init__(self, answer: str | None) -> None:
        self.answer = answer
        self.asked: list[tuple[str, dict[str, object], list[tuple[str, str]]]] = []

    def ask(
        self, *, system: str, facts: dict[str, object], pairs: list[tuple[str, str]]
    ) -> str | None:
        self.asked.append((system, facts, pairs))
        return self.answer


def llm(answer: str | None, cat: ForesightCatalogue | None = None) -> LlmPersonaSimulator:
    return LlmPersonaSimulator(cat or catalogue(), router=StubRouter(answer))


# --------------------------------------------------------------------------- #
# The port's contract, for every driver (the parity suite)
# --------------------------------------------------------------------------- #


def every_driver() -> list[tuple[str, PersonaSimulator]]:
    cat = catalogue()
    pairs = _pairs(cat)
    answer = "{" + ", ".join(f'"{t}||{s}": 0.25' for t, s in pairs) + "}"
    return [
        ("statistical", StatisticalBaseline(cat)),
        ("round-based", RoundBasedPersonaSimulator(cat)),
        ("llm", LlmPersonaSimulator(cat, router=StubRouter(answer))),
    ]


def _pairs(cat: ForesightCatalogue) -> list[tuple[str, str]]:
    themes = cat.themes(ChangeType.PACK_RETIRED, _AT).themes
    segments = cat.segments(_AT)
    return [(theme.theme, segment.name) for theme in themes for segment in segments]


@pytest.mark.parametrize(
    "name,driver", every_driver(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_every_driver_answers_every_theme_segment_pair(name: str, driver: PersonaSimulator):
    run = driver.propensities(scenario(), seed=7)

    assert {(p.theme, p.segment) for p in run.propensities} == set(_pairs(catalogue()))


@pytest.mark.parametrize(
    "name,driver", every_driver(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_every_driver_returns_propensities_in_range(name: str, driver: PersonaSimulator):
    """Never a band, never a count: a share of one segment, in [0, 1]."""
    run = driver.propensities(scenario(), seed=7)

    assert run.propensities
    for propensity in run.propensities:
        assert Decimal("0") <= propensity.value <= Decimal("1")
        assert isinstance(propensity.value, Decimal)


@pytest.mark.parametrize(
    "name,driver", every_driver(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_no_driver_emits_a_band_or_a_count(name: str, driver: PersonaSimulator):
    """Banding stays in the module so a driver cannot widen its own HIGH band."""
    run = driver.propensities(scenario(), seed=7)

    for propensity in run.propensities:
        assert not isinstance(propensity.value, VolumeBand)
        assert not hasattr(propensity, "band")
        assert not hasattr(propensity, "count")
        assert not hasattr(propensity, "complaints")


@pytest.mark.parametrize(
    "name,driver", every_driver(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_every_driver_states_its_version_and_basis(name: str, driver: PersonaSimulator):
    run = driver.propensities(scenario(), seed=7)

    assert run.simulator == driver.version
    assert run.basis


@pytest.mark.parametrize(
    "name,driver", every_driver(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_every_driver_says_it_read_no_individual_data(name: str, driver: PersonaSimulator):
    """Deck S8: Foresight on aggregates only."""
    run = driver.propensities(scenario(), seed=7)

    assert "no individual" in run.basis.lower() or "never" in run.basis.lower()


def test_a_propensity_outside_zero_to_one_is_refused():
    with pytest.raises(ValueError, match="not in"):
        Propensity(theme="t", segment="s", value=Decimal("1.5"))


# --------------------------------------------------------------------------- #
# The statistical baseline is the same arithmetic the report publishes
# --------------------------------------------------------------------------- #


def test_the_baseline_propensity_is_per_segment_not_per_subscriber_base():
    """What makes two methods comparable at all.

    A cohort simulation naturally answers "how many of this segment complained".
    The baseline has to answer the same question, so its segment-share factor
    moves out of the method and into the reporting step.
    """
    cat = catalogue()
    segment = next(s for s in cat.segments(_AT) if s.name == "students")
    theme = cat.themes(ChangeType.PACK_RETIRED, _AT).themes[0]

    run = StatisticalBaseline(cat).propensities(scenario())
    students = next(
        p for p in run.propensities if p.segment == "students" and p.theme == theme.theme
    )

    expected = segment.monthly_complaint_rate * theme.weight * theme.sensitivity_of(segment)
    assert students.value == expected.quantize(Decimal("0.000001"))
    assert students.value > segment.share_of_base * expected, "the share factor is not in here"


def test_the_reported_score_is_the_propensity_weighted_by_segment_share():
    """`score_of` is the only place the two are joined, and the report uses it."""
    cat = catalogue()
    rehearsed = scenario()
    report = Foresight(cat).run(rehearsed)
    run = StatisticalBaseline(cat).propensities(rehearsed)
    shares = {s.name: s.share_of_base for s in cat.segments(_AT)}

    by_pair = {(p.theme, p.segment): p.value for p in run.propensities}
    assert report.predictions
    for prediction in report.predictions:
        propensity = by_pair[(prediction.theme, prediction.segment)]
        expected = money(score_of(propensity, shares[prediction.segment]) * 1000) / 1000
        assert prediction.relative_score == expected


# --------------------------------------------------------------------------- #
# The round-based driver
# --------------------------------------------------------------------------- #


def test_the_round_based_driver_is_deterministic_for_one_seed():
    driver = RoundBasedPersonaSimulator(catalogue())
    rehearsed = scenario()

    assert driver.propensities(rehearsed, seed=9) == driver.propensities(rehearsed, seed=9)


def test_a_different_seed_gives_a_different_run():
    driver = RoundBasedPersonaSimulator(catalogue())
    rehearsed = scenario()

    first = driver.propensities(rehearsed, seed=1).propensities
    second = driver.propensities(rehearsed, seed=2).propensities

    assert first != second


def test_each_pair_draws_from_its_own_stream():
    """So adding a theme does not silently move another theme's numbers."""
    cat = catalogue()
    driver = RoundBasedPersonaSimulator(cat)

    pack = driver.propensities(scenario(ChangeType.PACK_RETIRED), seed=5)
    outage = driver.propensities(scenario(ChangeType.OUTAGE), seed=5)

    shared = {(p.theme, p.segment): p.value for p in pack.propensities}
    for propensity in outage.propensities:
        key = (propensity.theme, propensity.segment)
        if key in shared:
            assert propensity.value == shared[key], "a shared pair must not move"


def test_the_round_count_comes_from_policy():
    """I10: the driver has no constant to shadow the key with."""
    few = RoundBasedPersonaSimulator(catalogue_with(foresight__persona__rounds="1"))
    many = RoundBasedPersonaSimulator(catalogue_with(foresight__persona__rounds="20"))
    rehearsed = scenario()

    short = sum(p.value for p in few.propensities(rehearsed, seed=3).propensities)
    long = sum(p.value for p in many.propensities(rehearsed, seed=3).propensities)

    assert long > short, "more rounds let a change spread further"


def test_the_cohort_size_comes_from_policy_and_sets_the_resolution():
    cat = catalogue_with(foresight__persona__cohort_size="100")

    run = RoundBasedPersonaSimulator(cat).propensities(scenario(), seed=3)

    for propensity in run.propensities:
        assert (propensity.value * 100) == (propensity.value * 100).to_integral_value()


def test_a_propensity_is_an_exact_ratio_of_two_counts_never_a_float():
    """No float enters a propensity, which is I3's instinct applied here."""
    cat = catalogue_with(foresight__persona__cohort_size="1000")

    run = RoundBasedPersonaSimulator(cat).propensities(scenario(), seed=3)

    for propensity in run.propensities:
        assert isinstance(propensity.value, Decimal)
        assert (propensity.value * 1000) % 1 == 0


def test_the_round_based_driver_says_agreement_proves_nothing():
    run = RoundBasedPersonaSimulator(catalogue()).propensities(scenario(), seed=3)

    assert any("not evidence" in c.lower() for c in run.caveats)


def test_an_agent_is_declared_not_to_be_a_subscriber():
    run = RoundBasedPersonaSimulator(catalogue()).propensities(scenario(), seed=3)

    assert "never a subscriber" in run.basis


def test_the_two_deterministic_drivers_land_on_a_comparable_scale():
    """Not that they agree: that a disagreement means the methods disagree.

    If one driver answered in hundredths and the other in thousandths, every
    comparison would be a disagreement about units.
    """
    cat = catalogue()
    rehearsed = scenario()
    baseline = {
        (p.theme, p.segment): p.value
        for p in StatisticalBaseline(cat).propensities(rehearsed).propensities
    }
    rounds = {
        (p.theme, p.segment): p.value
        for p in RoundBasedPersonaSimulator(cat).propensities(rehearsed, seed=42).propensities
    }

    ratios = sorted(rounds[k] / baseline[k] for k in baseline if baseline[k] > 0)
    median = ratios[len(ratios) // 2]
    assert Decimal("0.25") < median < Decimal("4")


# --------------------------------------------------------------------------- #
# The LLM driver
# --------------------------------------------------------------------------- #


def test_the_llm_driver_reads_a_propensity_per_pair():
    cat = catalogue()
    pairs = _pairs(cat)
    answer = "{" + ", ".join(f'"{t}||{s}": 0.4' for t, s in pairs) + "}"

    run = llm(answer, cat).propensities(scenario(), seed=1)

    assert run.answered
    assert len(run.propensities) == len(pairs)
    assert all(p.value == Decimal("0.400000") for p in run.propensities)


def test_a_fenced_json_block_is_read():
    cat = catalogue()
    pairs = _pairs(cat)
    body = "{" + ", ".join(f'"{t}||{s}": 0.1' for t, s in pairs) + "}"

    run = llm(f"```json\n{body}\n```", cat).propensities(scenario(), seed=1)

    assert len(run.propensities) == len(pairs)


def test_a_pair_the_model_did_not_answer_is_dropped_not_defaulted():
    """Substituting zero turns a non-answer into "this segment will not complain"."""
    cat = catalogue()
    first = _pairs(cat)[0]
    answer = f'{{"{first[0]}||{first[1]}": 0.5}}'

    run = llm(answer, cat).propensities(scenario(), seed=1)

    assert len(run.propensities) == 1
    assert any("dropped rather than defaulted" in c for c in run.caveats)


@pytest.mark.parametrize("bad", ["1.5", "-0.2", '"high"', "null", "true"])
def test_a_value_that_is_not_a_propensity_is_dropped(bad: str):
    cat = catalogue()
    first = _pairs(cat)[0]

    run = llm(f'{{"{first[0]}||{first[1]}": {bad}}}', cat).propensities(scenario(), seed=1)

    assert run.propensities == ()


def test_a_key_the_run_did_not_ask_about_is_ignored():
    """A model cannot add a theme or a segment by naming one."""
    cat = catalogue()

    run = llm('{"invented theme||invented segment": 0.9}', cat).propensities(scenario(), seed=1)

    assert run.propensities == ()


def test_unparseable_text_yields_no_propensities_rather_than_a_guess():
    run = llm("I think students will be quite upset.").propensities(scenario(), seed=1)

    assert run.propensities == ()


def test_no_model_answering_is_absent_not_zero():
    """A column of zeros reads as a finding; an absent column does not."""
    run = llm(None).propensities(scenario(), seed=1)

    assert not run.answered
    assert run.propensities == ()
    assert any("zeros would read as a finding" in c for c in run.caveats)


def test_the_prompt_carries_only_aggregates_and_codes():
    """I13: nothing customer-shaped can reach a provider from here."""
    router = StubRouter("{}")
    LlmPersonaSimulator(catalogue(), router=router).propensities(scenario(), seed=1)

    _, facts, _ = router.asked[0]
    serialised = str(facts)
    assert "msisdn" not in serialised
    assert "subscriber" not in serialised
    assert "+94" not in serialised
    assert set(facts) == {
        "change_type",
        "effective_date",
        "severity",
        "affected_share",
        "seed",
        "segments",
        "themes",
    }


def test_the_prompt_asks_for_a_share_and_forbids_amounts_and_recommendations():
    """I1: the model is never asked for a decision-shaped output."""
    system = LlmPersonaSimulator.SYSTEM.lower()

    assert "share" in system
    assert "do not recommend" in system
    assert "do not give amounts or counts" in system


def test_the_llm_column_says_it_never_sets_a_band():
    cat = catalogue()
    first = _pairs(cat)[0]

    run = llm(f'{{"{first[0]}||{first[1]}": 0.5}}', cat).propensities(scenario(), seed=1)

    assert any("never sets a band" in c or "comparison column only" in c for c in run.caveats)


def test_the_router_adapter_passes_the_pairs_through():
    seen: dict[str, object] = {}

    def invoke(system: str, facts: dict[str, object], user: str) -> str | None:
        seen["user"] = user
        return "{}"

    RoleRouterPersonas(invoke).ask(system="s", facts={}, pairs=[("t", "g"), ("t2", "g2")])

    assert seen["user"] == "t||g\nt2||g2"


# --------------------------------------------------------------------------- #
# I1: the baseline is the headline, structurally
# --------------------------------------------------------------------------- #


def test_the_rehearsal_takes_no_headline_argument():
    """The boundary is the constructor, not the documentation.

    If a caller could pass a headline, I1 would rest on nobody doing it.
    """
    parameters = inspect.signature(PersonaRehearsal.__init__).parameters

    assert "headline" not in parameters
    assert "baseline" not in parameters
    assert "comparison" in parameters


def test_the_headline_is_the_statistical_baseline_even_with_a_model_wired():
    cat = catalogue()
    pairs = _pairs(cat)
    answer = "{" + ", ".join(f'"{t}||{s}": 0.99' for t, s in pairs) + "}"

    rehearsed = PersonaRehearsal(
        cat, comparison=LlmPersonaSimulator(cat, router=StubRouter(answer))
    ).run(scenario())

    assert rehearsed.headline_simulator == StatisticalBaseline.version
    assert rehearsed.comparison_simulator == LlmPersonaSimulator.version


def test_a_confident_model_cannot_move_a_reported_band():
    """The test that would fail if somebody made the comparison the headline."""
    cat = catalogue()
    pairs = _pairs(cat)
    shouting = "{" + ", ".join(f'"{t}||{s}": 1.0' for t, s in pairs) + "}"

    alone = PersonaRehearsal(cat).run(scenario())
    beside = PersonaRehearsal(
        cat, comparison=LlmPersonaSimulator(cat, router=StubRouter(shouting))
    ).run(scenario())

    assert [p.band for p in alone.predictions] == [p.band for p in beside.predictions]
    assert any(pair.comparison is VolumeBand.HIGH for pair in beside.comparison)


def test_the_reported_predictions_are_the_baselines():
    cat = catalogue()

    rehearsed = PersonaRehearsal(cat, comparison=RoundBasedPersonaSimulator(cat)).run(scenario())

    assert [p.band for p in rehearsed.predictions] == [
        p.band for p in Foresight(cat).run(scenario()).predictions
    ]


def test_the_report_says_the_bands_are_the_baselines():
    rehearsed = PersonaRehearsal(catalogue()).run(scenario())

    assert any("never sets a band" in c for c in rehearsed.caveats)


def test_a_rehearsal_with_no_comparison_has_no_second_column():
    rehearsed = PersonaRehearsal(catalogue()).run(scenario())

    assert rehearsed.comparison_simulator is None
    assert all(pair.comparison is None for pair in rehearsed.comparison)
    assert rehearsed.agreement_rate is None


def test_a_pair_with_no_comparison_reports_no_agreement_rather_than_disagreement():
    """Absent is not zero, and it is not a disagreement either."""
    cat = catalogue()
    first = _pairs(cat)[0]

    rehearsed = PersonaRehearsal(
        cat,
        comparison=LlmPersonaSimulator(
            cat, router=StubRouter(f'{{"{first[0]}||{first[1]}": 0.5}}')
        ),
    ).run(scenario())

    answered = [p for p in rehearsed.comparison if p.comparison is not None]
    absent = [p for p in rehearsed.comparison if p.comparison is None]
    assert len(answered) == 1
    assert absent
    assert all(p.agrees is None for p in absent)


def test_a_comparison_that_did_not_answer_is_not_agreement():
    cat = catalogue()

    rehearsed = PersonaRehearsal(
        cat, comparison=LlmPersonaSimulator(cat, router=StubRouter(None))
    ).run(scenario())

    assert rehearsed.agreement_rate is None
    assert any("That is not agreement." in c for c in rehearsed.caveats)


def test_agreement_is_reported_but_declared_meaningless():
    cat = catalogue()

    rehearsed = PersonaRehearsal(cat, comparison=RoundBasedPersonaSimulator(cat)).run(scenario())

    assert rehearsed.agreement_rate is not None
    assert rehearsed.compared_pairs > 0
    assert any("not evidence that either is right" in c for c in rehearsed.caveats)


def test_a_rehearsal_is_labelled_simulated():
    """I16: never present a simulated figure as a measured one."""
    assert PersonaRehearsal(catalogue()).run(scenario()).provenance == "SYNTHETIC"


def test_the_rehearsal_carries_no_customer_or_complaint_fields():
    rehearsed = PersonaRehearsal(catalogue()).run(scenario())

    assert not hasattr(rehearsed, "customer_id")
    assert not hasattr(rehearsed, "complaints")
    assert not hasattr(rehearsed, "subscriber_ref")
