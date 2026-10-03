"""Tokenisation, folding and the Singlish lexicon (K02, #32).

The index and the query go through one module on purpose: retrieval is only as
good as their agreement, and a corpus normalised one way against a query
normalised another shares no terms at all. These tests are mostly about that
agreement.
"""

from __future__ import annotations

import pytest

from clarity.ai.language import SINGLISH_TERMS, STOPWORDS, _fold
from clarity.modules.knowledge.public import query_terms, tokens

# -- folding -------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("inflected", "base"),
    [
        ("travelling", "travel"),
        ("spending", "spend"),
        ("reduced", "reduce"),
        ("charges", "charge"),
        ("speeds", "speed"),
        ("activated", "activate"),
        ("cycles", "cycle"),
        ("renewals", "renewal"),
        ("notifications", "notification"),
        ("crawling", "crawl"),
    ],
)
def test_the_two_forms_of_a_word_fold_together(inflected: str, base: str) -> None:
    """The property that matters: both forms reach the same stem.

    Not "the stem is correct English". A stem is internal and never shown, so
    "reduc" is a fine stem; what is not fine is "reduced" and "reduce" folding
    to different ones, which is a bug this suite caught once already.
    """
    assert _fold(inflected) == _fold(base)


@pytest.mark.parametrize("word", ["address", "process", "business", "access"])
def test_a_double_s_is_not_a_plural(word: str) -> None:
    assert _fold(word) == word


@pytest.mark.parametrize("word", ["ring", "used", "is", "the", "gb", "sim"])
def test_short_words_are_left_alone(word: str) -> None:
    """Over-stemming creates false matches, which are harder to spot than
    missed ones. "ring" must not become "r"."""
    assert _fold(word) == word


@pytest.mark.parametrize(
    "word",
    ["gaasthu", "wegaya", "karanna", "naththa", "ජංගම", "நிபந்தனை"],
)
def test_non_english_words_are_never_stemmed(word: str) -> None:
    """An English suffix rule applied to romanised Sinhala mangles it.

    "gaasthu" ending in "u" is not an inflection, and Sinhala and Tamil are
    agglutinative: a correct stemmer for either is a model-sized problem, so
    the guard is to not try.
    """
    assert _fold(word) == word


# -- tokenising ----------------------------------------------------------- #


def test_scripts_are_tokenised_as_their_own_runs() -> None:
    """A mixed sentence must tokenise both halves, not one."""
    found = tokens("Reload ජංගම 100")

    assert "reload" in found
    assert "ජංගම" in found
    assert "100" in found


def test_combining_marks_are_normalised_the_same_way_the_corpus_is() -> None:
    """K01 stores NFC. A query in NFD would share no term with it."""
    import unicodedata

    composed = "සි"
    decomposed = unicodedata.normalize("NFD", composed)

    assert tokens(composed) == tokens(decomposed)


def test_stopwords_are_dropped_from_both_sides() -> None:
    assert tokens("what is the charge") == tokens("charge")


def test_a_stopword_only_question_has_no_terms() -> None:
    """Otherwise "what is the" matches every document equally and ranks none."""
    assert tokens("what is the") == []
    assert query_terms("what is it") == []


# -- the Singlish lexicon ------------------------------------------------- #


def test_singlish_expands_to_the_english_the_corpus_uses() -> None:
    expanded = query_terms("Mage wegaya adu karala ai?")

    assert _fold("speed") in expanded
    assert _fold("reduced") in expanded
    assert _fold("why") in expanded


def test_the_expansion_is_additive() -> None:
    """A Singlish corpus entry should still match on the original word."""
    expanded = query_terms("gaasthu")

    assert "gaasthu" in expanded
    assert _fold("charge") in expanded


def test_every_expansion_is_stored_in_the_form_the_index_holds() -> None:
    """The bug this caught: the lexicon is written in dictionary form.

    The index holds folded stems, so appending a raw lexicon value puts a term
    in the query that no document can contain. The expansion silently matched
    nothing until an unrelated change to the folding rules exposed it, which is
    the worst kind of bug: a feature that appears to work.
    """
    for singlish, english in SINGLISH_TERMS.items():
        expanded = query_terms(singlish)
        for term in english:
            assert _fold(term) in expanded, f"{singlish} -> {term!r} is not in index form"


def test_no_lexicon_key_is_also_a_stopword() -> None:
    """A key that is a stopword is dropped before it can ever expand."""
    overlap = sorted(set(SINGLISH_TERMS) & STOPWORDS)

    assert overlap == [], f"these lexicon entries can never fire: {overlap}"


def test_no_lexicon_entry_is_unreachable() -> None:
    """Lookup happens after folding, so a key must be found in folded form.

    Two entries here, "nodanne" and "prashne", fold to "nodann" and "prashn"
    and so were never looked up at all before this test existed. The golden set
    did not notice, because the query carrying "nodanne" also carries "service"
    and "gaasthu" and passed on those: a dead lexicon entry is invisible from
    the outside, which is why this is asserted directly.
    """
    from clarity.ai.language import _LEXICON

    unreachable = [key for key in SINGLISH_TERMS if _fold(key) not in _LEXICON]

    assert unreachable == [], f"folded before lookup, so never matched: {unreachable}"


def test_each_lexicon_key_actually_fires() -> None:
    """End to end for every entry: the key in, the English out."""
    for singlish, english in SINGLISH_TERMS.items():
        expanded = query_terms(singlish)
        assert any(_fold(term) in expanded for term in english), (
            f"{singlish!r} expanded to {expanded}, which carries none of {english}"
        )


# -- the index is derived, not owned -------------------------------------- #


def test_a_cold_index_scores_the_same_as_a_warm_one() -> None:
    """The condition that lets the BM25 index live in an attribute at all.

    `tests/architecture/test_module_state.py` allows `_frequencies` and
    `_lengths` as a derived index rather than business state, and the second
    condition it requires is this one: a lookup for something the index has not
    seen populates it instead of missing. Without that, a cold index after a
    restart would silently retrieve less than a warm one, which is business
    state wearing an index's name.
    """
    from datetime import UTC, datetime
    from pathlib import Path

    from clarity.kernel.common import Language
    from clarity.modules.knowledge.public import (
        Audience,
        KnowledgeRegistry,
        KnowledgeRetriever,
        KnowledgeSource,
        RetrievalConfig,
        SourceKind,
    )

    now = datetime(2026, 10, 3, tzinfo=UTC)
    registry = KnowledgeRegistry(clock=lambda: now)
    registry.publish(
        KnowledgeSource(
            source_id="SIM-COLD",
            version=1,
            title="Speed",
            kind=SourceKind.HELP_ARTICLE,
            owner="legal-sim",
            audience=Audience.CUSTOMER,
            language=Language.EN,
            body="Speeds may be reduced once the fair usage threshold is reached.",
            effective_from=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    config = RetrievalConfig.from_file(
        Path(__file__).parents[3] / "config" / "ai" / "retrieval.yaml"
    )

    warm = KnowledgeRetriever(registry, config)
    warm.index(registry.chunks_as_of(now, audience=Audience.STAFF))
    cold = KnowledgeRetriever(registry, config)  # never indexed

    query = {"audience": Audience.CUSTOMER, "moment": now}
    assert (
        cold.search("speed reduced", **query).citations
        == warm.search("speed reduced", **query).citations
    )
