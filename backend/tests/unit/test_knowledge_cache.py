"""The answer cache: generic only, and structurally never stale (K03, #33).

Plan 22 section 7 ("Cache" and "Freshness"). Two properties carry the weight,
and both are enforced rather than documented:

**Staleness is impossible, not merely prevented.** The corpus fingerprint is
part of the key, so publishing anything makes every earlier entry unreachable.
An invalidation scheme that depended on the `knowledge.published` event
arriving would be one lost message away from quoting last month's terms with
this month's confidence.

**Only generic, grounded answers are stored.** A cache that can hold a
case-specific answer will eventually serve one customer's figures to another.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from clarity.kernel.common import Language
from clarity.modules.knowledge.answers import AnswerKind
from clarity.modules.knowledge.public import (
    AnswerCache,
    Audience,
    CacheKey,
    KnowledgeRegistry,
    KnowledgeRetriever,
    KnowledgeService,
    KnowledgeSource,
    RetrievalConfig,
    SourceKind,
)

CONFIG = Path(__file__).parents[3] / "config" / "ai" / "retrieval.yaml"
NOW = datetime(2026, 10, 3, tzinfo=UTC)
LAST_YEAR = datetime(2025, 1, 1, tzinfo=UTC)
NEXT_YEAR = datetime(2027, 1, 1, tzinfo=UTC)

FUP_V1 = "4.2 Speeds may be reduced after the fair usage threshold is reached."
FUP_V2 = "4.2 Speeds are reduced to 512 kbps after the fair usage threshold is reached."


def fup(version: int, body: str, *, effective_from=LAST_YEAR, effective_to=None):
    return KnowledgeSource(
        source_id="SIM-FUP",
        version=version,
        title="Fair usage",
        kind=SourceKind.LEGAL_TEXT,
        owner="legal-sim",
        audience=Audience.CUSTOMER,
        language=Language.EN,
        clause_prefix="T&C",
        body=body,
        effective_from=effective_from,
        effective_to=effective_to,
    )


@pytest.fixture
def service() -> KnowledgeService:
    registry = KnowledgeRegistry(clock=lambda: NOW)
    registry.publish(fup(1, FUP_V1))
    retriever = KnowledgeRetriever(registry, RetrievalConfig.from_file(CONFIG))
    retriever.index(registry.chunks_as_of(NOW, audience=Audience.STAFF))
    return KnowledgeService(registry, retriever, cache=AnswerCache(), clock=lambda: NOW)


QUERY = "why were my speeds reduced"


# -- the cache works ----------------------------------------------------- #


def test_the_same_question_twice_is_served_from_the_cache(service) -> None:
    first = service.ask(QUERY, audience=Audience.CUSTOMER)
    second = service.ask(QUERY, audience=Audience.CUSTOMER)

    assert first.cached is False
    assert second.cached is True
    assert second.text == first.text
    assert second.citations == first.citations


def test_punctuation_and_case_do_not_make_a_new_entry(service) -> None:
    """The key is the normalised terms, so "Why...?" is the same question."""
    service.ask(QUERY, audience=Audience.CUSTOMER)

    again = service.ask("Why were my speeds REDUCED?", audience=Audience.CUSTOMER)

    assert again.cached is True


def test_the_cache_stores_no_customer_text(service) -> None:
    """The key is a hash of the terms, so a row cannot be read back as a query.

    I13: nothing recoverable as what somebody typed is stored.
    """
    key = CacheKey.for_query(
        "my number is 0781234567 and my speed is slow",
        language=Language.EN,
        audience=Audience.CUSTOMER,
        corpus_version="v1",
    )

    assert "0781234567" not in key.terms_hash
    assert "speed" not in key.terms_hash
    assert key.terms_hash.startswith("sha256:")


# -- staleness is impossible --------------------------------------------- #


def test_publishing_a_new_version_makes_the_cached_answer_unreachable(service) -> None:
    """The property the whole key design exists for.

    Not "the event invalidates it": the corpus fingerprint is part of the key,
    so the old entry cannot be found even if no event is ever delivered.
    """
    first = service.ask(QUERY, audience=Audience.CUSTOMER)
    assert "512 kbps" not in first.text

    service._registry.supersede(fup(2, FUP_V2, effective_from=NOW))
    service._retriever.index(service._registry.chunks_as_of(NOW, audience=Audience.STAFF))

    after = service.ask(QUERY, audience=Audience.CUSTOMER)

    assert after.cached is False, "a cached answer survived a publication"
    assert "512 kbps" in after.text, "the new version was not used"


def test_closing_a_version_also_changes_the_key(service) -> None:
    """A window can change without a version being added.

    A fingerprint over the set of refs alone would not notice, and the cache
    would keep an answer composed from text that is no longer in force.
    """
    before = service._registry.corpus_version()

    service._registry.supersede(fup(2, FUP_V2, effective_from=NEXT_YEAR))

    assert service._registry.corpus_version() != before


def test_the_audience_is_part_of_the_key(service) -> None:
    """Otherwise a staff answer could be served to a customer.

    The retrieval filter went to some trouble to keep staff sources out of a
    customer's result set; a cache keyed without the audience would hand one
    over anyway.
    """
    customer = CacheKey.for_query(
        QUERY, language=Language.EN, audience=Audience.CUSTOMER, corpus_version="v1"
    )
    staff = CacheKey.for_query(
        QUERY, language=Language.EN, audience=Audience.STAFF, corpus_version="v1"
    )

    assert customer != staff


def test_the_language_is_part_of_the_key(service) -> None:
    english = CacheKey.for_query(
        QUERY, language=Language.EN, audience=Audience.CUSTOMER, corpus_version="v1"
    )
    sinhala = CacheKey.for_query(
        QUERY, language=Language.SI, audience=Audience.CUSTOMER, corpus_version="v1"
    )

    assert english != sinhala


def test_invalidate_drops_entries_from_an_older_corpus(service) -> None:
    """Housekeeping, so a long-lived process does not carry dead entries."""
    service.ask(QUERY, audience=Audience.CUSTOMER)
    assert len(service.cache) == 1

    dropped = service.on_knowledge_published("a-different-corpus-version")

    assert dropped == 1
    assert len(service.cache) == 0


# -- what may not be cached ---------------------------------------------- #


def test_a_refusal_is_never_cached(service) -> None:
    """Caching "I do not know" would keep saying it after the source lands.

    And that is the one staleness a customer cannot detect: a wrong answer can
    be argued with, a refusal just looks like the system not knowing.
    """
    first = service.ask("what is the capital of france", audience=Audience.CUSTOMER)
    assert first.answer.kind is AnswerKind.REFUSAL

    second = service.ask("what is the capital of france", audience=Audience.CUSTOMER)

    assert second.cached is False
    assert len(service.cache) == 0


def test_a_case_specific_answer_is_never_cached(service) -> None:
    """A shared cache holding one customer's answer is the worst outcome here."""
    service.ask(QUERY, audience=Audience.CUSTOMER, case_specific=True)

    assert len(service.cache) == 0
    again = service.ask(QUERY, audience=Audience.CUSTOMER, case_specific=True)
    assert again.cached is False


def test_an_answer_scoped_to_a_product_is_not_cached(service) -> None:
    """Product filtering makes the result specific to the case's products."""
    service.ask(QUERY, audience=Audience.CUSTOMER, product_ids=("P-1299",))

    assert len(service.cache) == 0


def test_put_refuses_an_ungrounded_answer() -> None:
    """An answer whose citations did not verify must not become the fast path."""
    from clarity.modules.knowledge.answers import GroundedAnswer

    cache = AnswerCache()
    key = CacheKey.for_query(
        QUERY, language=Language.EN, audience=Audience.CUSTOMER, corpus_version="v1"
    )

    stored = cache.put(
        key,
        GroundedAnswer(text="Speeds drop.", kind=AnswerKind.MODEL, citations=("SIM-FUP@1",)),
        generic=True,
    )

    assert stored is False, "an answer with an unverified report was cached"
    assert cache.refused == 1


def test_an_answer_with_no_citations_is_not_cached() -> None:
    from clarity.modules.knowledge.answers import GroundedAnswer

    cache = AnswerCache()
    key = CacheKey.for_query(
        QUERY, language=Language.EN, audience=Audience.CUSTOMER, corpus_version="v1"
    )

    assert not cache.put(key, GroundedAnswer(text="Speeds drop.", kind=AnswerKind.TEMPLATE))


def test_the_cache_evicts_least_recently_used() -> None:
    cache = AnswerCache(capacity=2)
    keys = [
        CacheKey.for_query(
            f"question {n}",
            language=Language.EN,
            audience=Audience.CUSTOMER,
            corpus_version="v1",
        )
        for n in range(3)
    ]
    from clarity.modules.knowledge.answers import GroundedAnswer
    from clarity.modules.knowledge.citations import CitationCheck, CitationReport

    def grounded(n: int) -> GroundedAnswer:
        return GroundedAnswer(
            text=f"answer {n}",
            kind=AnswerKind.TEMPLATE,
            citations=("SIM-FUP@1",),
            report=CitationReport(checks=(CitationCheck(citation="SIM-FUP@1", ok=True),)),
        )

    assert cache.put(keys[0], grounded(0))
    assert cache.put(keys[1], grounded(1))
    cache.get(keys[0])  # keeps 0 warm, so 1 is the oldest use
    assert cache.put(keys[2], grounded(2))

    assert len(cache) == 2
    assert cache.get(keys[1]) is None
    assert cache.get(keys[0]) is not None


def test_a_cached_answer_does_not_carry_a_previous_query_trace(service) -> None:
    """The trace describes one retrieval, and reusing it would make the audit
    record of this turn describe a different one."""
    service.ask(QUERY, audience=Audience.CUSTOMER)

    again = service.ask(QUERY, audience=Audience.CUSTOMER)

    assert again.cached is True
    assert again.trace.query == QUERY
    assert again.trace.candidates == 0, "a reused trace would claim candidates it did not score"
