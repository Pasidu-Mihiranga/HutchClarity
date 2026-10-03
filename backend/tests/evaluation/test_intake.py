"""Intake measured per language (C04 #23, acceptance 1).

F1 at or above 0.90 per language, on the labelled intake set. No model: the
keyword rules are what is measured, because they are the floor every deployment
has (ADR-0009) and the only tier that runs with no provider configured.

**Two sets, and the second is the one to believe.** `intake.jsonl` is the set
the rules were extended against during C04, so a good number on it says the
rules cover the vocabulary in it. `intake_heldout.jsonl` was written before the
rules were touched and deliberately not consulted while touching them, so a
good number on it says they generalise. Reporting only the first would be
reporting a fit.

**What neither set can do** is validate a keyword set. The `intake` gate
requires 300 examples per language and these hold 20 and 9, so the gate stays
UNEVALUABLE at any F1, which is the honest state: twenty examples per language
cannot tell a rule that works from a rule that happens to match twenty
sentences. The gate says so and blocks; these tests stop regressions in the
meantime.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clarity.ai.evaluation import Labelled, load_intake, macro_f1
from clarity.modules.conversation.intake import (
    ASSIST_BELOW,
    RULES,
    UNSURE,
    classify,
    detect_language,
)
from clarity.modules.conversation.intents import Intent
from clarity.modules.conversation.public import extract_intake

DATASETS = Path(__file__).parent / "datasets"
TUNED = load_intake(DATASETS / "intake.jsonl")
HELD_OUT = load_intake(DATASETS / "intake_heldout.jsonl", name="intake-heldout")

#: The gate's threshold, from `config/ai/gates.yaml`.
F1_MIN = 0.90

LANGUAGES = ("en", "si", "ta", "si-en")


def measure(dataset, language: str):
    rows = [
        Labelled(
            language=language,
            gold=example.intent,
            predicted=extract_intake(example.text).intent,
        )
        for example in dataset.for_language(language)
    ]
    return macro_f1(rows), [row for row in rows if row.gold != row.predicted]


# -- acceptance 1 --------------------------------------------------------- #


@pytest.mark.parametrize("language", LANGUAGES)
def test_intent_f1_clears_the_gate_per_language(language: str) -> None:
    """Acceptance 1. Per language, because an overall number hides a language.

    Singlish is the one that makes this worth gating per language: before C04
    it measured 0.305 while the overall figure looked survivable, because 13 of
    its 20 examples classified as FALLBACK for want of any Singlish vocabulary
    at all.
    """
    observed, wrong = measure(TUNED, language)

    assert observed.measured
    assert observed.value is not None
    assert observed.value >= F1_MIN, (
        f"{language} F1 is {observed}, gate {F1_MIN}. Misses: "
        + "; ".join(f"{row.gold} read as {row.predicted}" for row in wrong)
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_rules_generalise_to_examples_they_were_not_written_against(
    language: str,
) -> None:
    """The held-out set, which is the honest half of acceptance 1.

    A keyword rule can always be made to pass the sentence it was written for.
    This set was written first and not looked at while the rules were extended,
    so it is the only number here that says anything about a sentence nobody
    has seen.
    """
    observed, wrong = measure(HELD_OUT, language)

    assert observed.measured
    assert observed.value is not None
    assert observed.value >= F1_MIN, (
        f"held-out {language} F1 is {observed}, gate {F1_MIN}. Misses: "
        + "; ".join(f"{row.gold} read as {row.predicted}" for row in wrong)
    )


def test_the_held_out_set_is_independent_of_the_tuned_one() -> None:
    """Otherwise it is a copy and proves nothing."""
    tuned = {example.text.casefold() for example in TUNED.examples}
    held = {example.text.casefold() for example in HELD_OUT.examples}

    assert tuned & held == set()
    assert set(HELD_OUT.languages) == set(LANGUAGES)


# -- Singlish, the language this work was about -------------------------- #


def test_every_singlish_example_is_detected_as_singlish() -> None:
    """Singlish has no script, so it is recognised by vocabulary or not at all.

    A05 recorded that intake reported it as `en`, which meant anything routing
    on the detected language treated these customers as English speakers.
    """
    for dataset in (TUNED, HELD_OUT):
        for example in dataset.for_language("si-en"):
            assert detect_language(example.text) == "si-en", example.text


def test_english_with_one_borrowed_word_is_still_english() -> None:
    """Two markers are required, because one is often a coincidence.

    "Please reload my account" is English and carries "reload", which is in the
    lexicon shared with retrieval. Reading it as Singlish would answer an
    English speaker in Sinhala.
    """
    assert detect_language("Please reload my account") == "en"
    assert detect_language("My data pack is slow today") == "en"
    assert detect_language("I want to activate a package") == "en"


def test_script_wins_over_the_singlish_lexicon() -> None:
    """A Sinhala sentence with a romanised loan word is Sinhala."""
    assert detect_language("මගේ data pack eka වැඩ කරන්නේ නැහැ") == "si"


def test_singlish_is_answered_in_sinhala() -> None:
    """The approved templates are si, ta and en (I15), and Singlish is Sinhala.

    Answering it in English would be a guess about literacy.
    """
    from clarity.modules.conversation.intake import reply_language

    assert reply_language("si-en") == "si"
    assert reply_language("en") == "en"
    assert reply_language("si") == "si"


# -- the rule table itself ------------------------------------------------ #


def test_every_intent_is_reachable_by_some_rule() -> None:
    """An intent no rule can produce is a flow no customer can reach.

    All 19 intents are claimed by exactly one flow (C02 asserts that half), so
    an unreachable intent is a journey that exists in the flow files and is
    dead in practice. FALLBACK is excluded: it is what the table returns when
    nothing matched, so by construction no rule names it.
    """
    reachable = {rule.intent for rule in RULES}
    missing = sorted(
        intent.value
        for intent in Intent
        if intent not in reachable and intent is not Intent.FALLBACK
    )

    assert missing == [], f"no rule can produce: {missing}"


def test_no_two_rules_share_a_pattern() -> None:
    """A duplicated pattern means the second one can never fire.

    The table is first-match-wins, so an identical pattern lower down is dead
    code that reads like a working rule.
    """
    from collections import Counter

    repeated = [
        pattern for pattern, count in Counter(rule.pattern for rule in RULES).items() if count > 1
    ]

    assert repeated == []


def test_every_rule_covers_every_language_or_says_why() -> None:
    """A rule with no Sinhala, Tamil or Singlish alternation is a rule those
    customers cannot reach, which is how Singlish came to score 0.305.

    Checked by script range rather than by meaning: a pattern carrying no
    Sinhala and no Tamil character is English-only. A handful legitimately are,
    because the words are loanwords customers type in Latin script whatever
    they speak, and those carry a `note` saying so.
    """
    import re as _re

    english_only = [
        rule.intent.value
        for rule in RULES
        if not _re.search(r"[\u0D80-\u0DFF\u0B80-\u0BFF]", rule.pattern)
    ]

    # ESIM_HELP is the loanword case: "esim" is written the same way in all
    # four. Everything else must reach a Sinhala or Tamil speaker.
    assert set(english_only) <= {Intent.ESIM_HELP.value}, (
        f"these rules cannot be reached in Sinhala or Tamil: {sorted(set(english_only))}"
    )


def _first_match(text: str) -> tuple[str, float]:
    """The rule table's answer, with no model assist in the way."""
    return classify(text)[:2]


def test_a_handoff_request_always_wins() -> None:
    """Whatever else the message says, a customer asking for a person gets one.

    The handoff rule is first in the table for this reason, and the test is
    worth having because a later edit that moves it would be invisible.
    """
    for text in (
        "my balance is wrong, let me speak to a human",
        "I want an agent, my pack is not working",
        "Mata kenek ekka katha karanna ona, package eka wada na",
    ):
        intent, confidence = _first_match(text)
        assert intent == Intent.HANDOFF.value, text
        assert confidence > ASSIST_BELOW


# -- the model assist is optional and bounded ---------------------------- #


def test_the_assist_is_not_asked_when_the_rules_are_confident() -> None:
    """A model that can overrule a matched phrase can reroute a customer."""
    asked: list[str] = []

    class Assist:
        def classify(self, text: str) -> str | None:
            asked.append(text)
            return Intent.HANDOFF.value

    intent, _confidence, assisted = classify("I want to activate a data pack", assist=Assist())

    assert asked == []
    assert assisted is False
    assert intent == Intent.PACK_ACTIVATE.value


def test_the_assist_is_asked_when_the_rules_are_unsure() -> None:
    class Assist:
        def classify(self, text: str) -> str | None:
            return Intent.ESIM_HELP.value

    intent, confidence, assisted = classify("hmm, something odd here", assist=Assist())

    assert assisted is True
    assert intent == Intent.ESIM_HELP.value
    # Capped: a model-sourced intent must not look as certain as a matched
    # phrase, because the router uses the number to decide whether to pull a
    # customer out of a flow they are already in (C02).
    assert UNSURE <= confidence <= ASSIST_BELOW


def test_an_invented_intent_is_rejected() -> None:
    """A model naming an intent that does not exist is a rejected answer.

    Accepting one would let a model reach a flow no rule can reach, which is
    agency this layer does not have (I1).
    """

    class Assist:
        def classify(self, text: str) -> str | None:
            return "REFUND_EVERYTHING_NOW"

    intent, _confidence, assisted = classify("hmm, something odd here", assist=Assist())

    assert assisted is True
    assert intent == Intent.FALLBACK.value


def test_an_assist_that_raises_leaves_the_rules_answer() -> None:
    class Assist:
        def classify(self, text: str) -> str | None:
            raise RuntimeError("the provider is down")

    intent, _confidence, assisted = classify("why was I charged", assist=Assist())

    assert assisted is False
    assert intent == Intent.UNEXPECTED_CHARGE.value


def test_without_an_assist_the_rules_answer_alone() -> None:
    """ADR-0009: no model configured is the default, not a degraded mode.

    Everything measured above runs on this path.
    """
    intent, _confidence, assisted = classify("why was I charged")

    assert assisted is False
    assert intent == Intent.UNEXPECTED_CHARGE.value


def test_slots_stay_hints(dataset_free=None) -> None:
    """I2: intake fills slots, and nothing downstream treats them as evidence.

    The amount a customer typed narrows which charges are worth looking at and
    is never the amount in a reply; C02's devlog records the bug that proved it
    matters.
    """
    result = extract_intake("Why was LKR 49 deducted from my balance?")

    assert result.slots["amount_lkr"] == "49"
    assert result.intent == Intent.BALANCE_DEDUCTION_QUERY.value
