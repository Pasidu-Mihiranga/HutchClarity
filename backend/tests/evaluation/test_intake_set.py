"""The intake set: four languages, measured against the real intake (A05, #9).

This file checks the dataset and the measurement, not the quality of the
classifier. Quality is the gate's job, and the gate currently cannot do it: the
set holds 20 utterances per language against the 300 plan 22 section 10 asks
for, so the intake gate reports UNEVALUABLE and blocks. That is the honest
state, and `make eval` prints the scores alongside the shortfall.

What is asserted here is the part that would otherwise rot silently: that the
set is well formed, that its gold labels are real intents, and that every
declared language actually gets measured rather than quietly producing nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clarity.ai.evaluation import GateSet, GateStatus, Labelled, by_language, load_intake
from clarity.ai.evaluation.datasets import DatasetInvalid
from clarity.modules.conversation.intents import Intent
from clarity.modules.conversation.public import extract_intake
from clarity.modules.conversation.service import detect_language

REPO = Path(__file__).resolve().parents[3]
DATASET = Path(__file__).parent / "datasets" / "intake.jsonl"
GATES = REPO / "config" / "ai" / "gates.yaml"

#: The four languages plan 22 section 10 sets a gate for.
DECLARED = ("si", "ta", "en", "si-en")


@pytest.fixture(scope="module")
def dataset():
    return load_intake(DATASET)


@pytest.fixture(scope="module")
def rows(dataset):
    return [
        Labelled(
            language=example.language,
            gold=example.intent,
            predicted=extract_intake(example.text).intent,
        )
        for example in dataset.examples
    ]


# -- the dataset itself --------------------------------------------------- #


def test_the_set_covers_every_language_the_gate_requires(dataset):
    assert set(dataset.languages) == set(DECLARED)
    for language in DECLARED:
        assert dataset.counts_per_language[language] > 0, f"nothing for {language}"


def test_every_gold_label_is_a_real_intent(dataset):
    """A typo in a gold label silently becomes an intent nothing can predict.

    It would then count against every classifier for ever, and look like a
    model problem rather than a dataset problem.
    """
    known = {intent.value for intent in Intent}
    unknown = sorted({e.intent for e in dataset.examples} - known)
    assert unknown == [], f"gold labels that are not intents: {unknown}"


def test_the_set_is_not_written_against_the_matcher(rows):
    """A set the current intake gets entirely right would be measuring itself.

    This is the same mistake the authorization parity suite made before M-IAM:
    comparing an implementation against a restatement of itself always agrees.
    An intake set with no misses is a set written by reading the keyword
    patterns, so it has to contain phrasings the matcher gets wrong.
    """
    missed = [row for row in rows if row.gold != row.predicted]
    assert missed, "every utterance was classified correctly, so this set proves nothing"


def test_a_malformed_dataset_is_refused(tmp_path):
    bad = tmp_path / "intake.jsonl"
    bad.write_text('{"id": "x", "language": "en"}\n', encoding="utf-8")
    with pytest.raises(DatasetInvalid, match="'text' is required"):
        load_intake(bad)


def test_a_duplicate_id_is_refused(tmp_path):
    """Two lines with one id means one of them is silently uncounted."""
    bad = tmp_path / "intake.jsonl"
    line = '{"id": "x", "language": "en", "text": "hello", "intent": "FALLBACK"}'
    bad.write_text(f"{line}\n{line}\n", encoding="utf-8")
    with pytest.raises(DatasetInvalid, match="duplicate id"):
        load_intake(bad)


# -- the measurement ------------------------------------------------------ #


def test_every_declared_language_is_actually_measured(rows):
    """A language that produces no observation is the failure mode to catch.

    The gate would report UNEVALUABLE for it, which blocks, but it would block
    for the wrong reason: "we did not measure Tamil" reads the same as "Tamil
    regressed" unless the measurement itself is checked.
    """
    measurement = by_language("intent_f1", rows, statistic="macro_f1")

    for language in DECLARED:
        observation = measurement.per_language.get(language)
        assert observation is not None, f"{language} was not measured at all"
        assert observation.measured, f"{language} produced no value"
        assert observation.sample_size == 20


def test_the_classifier_is_not_wholly_broken_in_any_language(rows):
    """A floor, not a gate: zero in a language means nothing matches at all."""
    measurement = by_language("intent_f1", rows, statistic="macro_f1")

    for language in DECLARED:
        value = measurement.per_language[language].value
        assert value is not None and value > 0.0, f"intent F1 is zero for {language}"


def test_slot_accuracy_is_measured_only_where_a_slot_is_declared(dataset):
    """Examples with nothing to extract must not be counted as correct.

    Counting them would inflate the metric with examples that never tested it,
    which is the quiet way a slot gate comes to read 1.00.
    """
    with_slots = [example for example in dataset.examples if example.slots]
    assert with_slots, "the set declares no slots at all"
    assert len(with_slots) < len(dataset.examples), "every example declares a slot"

    for example in with_slots:
        assert "amount_lkr" in example.slots
        assert example.slots["amount_lkr"].isdigit()


# -- the gate, over the committed gate set -------------------------------- #


def test_the_intake_gate_blocks_today_because_the_set_is_too_small(rows):
    """Recorded on purpose: the score is reported, the gate still blocks.

    When the set reaches 300 per language this test will fail, and that failure
    is the signal to stop treating the intake gate as pending. The scores are in
    the report artefact from `make eval`, not asserted here, because a hard floor
    would have to be rewritten every time an utterance is added.
    """
    gates = GateSet.from_file(GATES)
    spec = gates.spec("intake")
    measurement = by_language("intent_f1", rows, statistic="macro_f1")

    assert spec.min_per_language == 300
    for language in DECLARED:
        observed = measurement.per_language[language]
        assert observed.sample_size < spec.min_per_language, (
            f"{language} now has {observed.sample_size} utterances. The set has grown: "
            "drop this test and let the intake gate score for real."
        )


def test_singlish_is_detected_as_its_own_language(dataset):
    """C04 (#23) closed the gap this test used to record.

    Until C04 this asserted `detected == {"en"}` and said in its docstring that
    failing would be the point. Singlish is romanised Sinhala, so it has no
    script to find: it is recognised by vocabulary, and nothing else can
    recognise it.

    This matters beyond the metric. Anything routing on the detected language
    used to treat these customers as English speakers, and `compose_reply` now
    answers them in Sinhala, which is the language their words are.
    """
    detected = {detect_language(example.text) for example in dataset.for_language("si-en")}

    assert detected == {"si-en"}, f"Singlish detected as {detected}"


def test_sinhala_and_tamil_script_still_win_over_the_singlish_lexicon(dataset):
    """Script is unambiguous, so it is checked first.

    A Sinhala sentence containing a romanised loan word must not be read as
    Singlish, and the order of the checks in `detect_language` is what
    guarantees it.
    """
    for language in ("si", "ta"):
        detected = {detect_language(example.text) for example in dataset.for_language(language)}
        assert detected == {language}, f"{language} detected as {detected}"


def test_one_singlish_word_is_not_enough_to_call_a_sentence_singlish():
    """Two markers, because one is often a name or a coincidence.

    "Please reload my account" is English and contains "reload", which is in
    the shared lexicon. Reading it as Singlish would answer an English speaker
    in Sinhala.
    """
    assert detect_language("Please reload my account") == "en"
    assert detect_language("My data pack is slow") == "en"


def test_the_safety_gate_is_the_one_that_can_pass_today():
    """Sanity: not every gate is stuck, so a green safety gate is meaningful."""
    gates = GateSet.from_file(GATES)
    safety = gates.spec("safety")

    assert safety.min_per_language == 0
    assert [t.minimum for t in safety.thresholds] == [1.0]
    assert not any(t.per_language for t in safety.thresholds)


def test_the_gate_set_declares_the_same_languages_the_dataset_ships(dataset):
    """Config and data have to agree, or a language is gated but never measured."""
    gates = GateSet.from_file(GATES)
    assert set(gates.spec("intake").languages) == set(dataset.languages)


def test_an_unevaluable_intake_gate_is_still_a_block(rows):
    gates = GateSet.from_file(GATES)
    from clarity.ai.evaluation import evaluate_gate

    verdicts = evaluate_gate(
        gates.spec("intake"),
        {"intent_f1": by_language("intent_f1", rows, statistic="macro_f1")},
    )

    unevaluable = [v for v in verdicts if v.status is GateStatus.UNEVALUABLE]
    assert unevaluable, "the intake gate should not be passing on 20 utterances"
    assert all(v.blocks_release for v in unevaluable)
