"""The retriever port's contract, which every ranker must hold (K02, #32).

Plan 22 section 7 specifies two indexes: in-memory BM25 for `lite` and a
pgvector hybrid for `full`. Issue #32 asks for a parity suite so the two give
the same top results on a fixed corpus within tolerance.

**Only one driver exists, and this file says so rather than pretending.** There
is no embedding model in the system: `ModelRole.EMBED` is a declared role name
with no implementation, `local-bge` is bound to the template provider as a
stand-in, and `RoleRouter.invoke` returns text, which cannot carry a vector. So
the hybrid driver is registered here and **skips**, exactly as the Kafka driver
skips in `test_bus_parity.py` when no broker is reachable.

That is deliberate and it is the useful half of the work: the contract below is
what the pgvector driver will have to pass, written now, while the properties
are being decided rather than after one implementation has made them up. A
suite that only ever ran against the implementation it was written from proves
nothing about the next one.

The properties here are the ones that must not vary by index, which is a
narrower set than "the same ordering". Two rankers with different scoring will
order near-ties differently and that is allowed; what may not vary is **which
chunks are eligible at all** and **what a result means**.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from clarity.kernel.common import Language
from clarity.modules.knowledge.public import (
    Audience,
    KnowledgeRegistry,
    KnowledgeRetriever,
    KnowledgeSource,
    RetrievalConfig,
    SourceKind,
)

CONFIG = Path(__file__).parents[3] / "config" / "ai" / "retrieval.yaml"
NOW = datetime(2026, 10, 3, tzinfo=UTC)
LAST_YEAR = datetime(2025, 1, 1, tzinfo=UTC)
NEXT_MONTH = datetime(2026, 11, 1, tzinfo=UTC)

#: A fixed corpus, so a parity failure is a driver difference and not a data
#: difference. Small and deliberately overlapping in vocabulary.
CORPUS: tuple[dict[str, object], ...] = (
    {
        "source_id": "SIM-SPEED",
        "title": "Speed reduction",
        "kind": SourceKind.LEGAL_TEXT,
        "clause_prefix": "T&C",
        "body": "4.2 Speeds may be reduced once the fair usage threshold is reached.",
    },
    {
        "source_id": "SIM-EXPIRY",
        "title": "Pack expiry",
        "kind": SourceKind.LEGAL_TEXT,
        "clause_prefix": "T&C",
        "body": "8.2 Unused allowance in an expired pack lapses and is not carried forward.",
    },
    {
        "source_id": "SIM-REFUND",
        "title": "Refund timing",
        "kind": SourceKind.LEGAL_TEXT,
        "clause_prefix": "T&C",
        "body": "12.1 An approved refund is credited to the balance within three working days.",
    },
    {
        "source_id": "SIM-SOP",
        "title": "Desk procedure",
        "kind": SourceKind.STAFF_SOP,
        "audience": Audience.STAFF,
        "body": "A refund above the desk limit is escalated to the duty manager.",
    },
)


def _registry() -> KnowledgeRegistry:
    registry = KnowledgeRegistry(clock=lambda: NOW)
    for entry in CORPUS:
        fields: dict[str, object] = {
            "version": 1,
            "owner": "legal-sim",
            "audience": Audience.CUSTOMER,
            "language": Language.EN,
            "effective_from": LAST_YEAR,
            **entry,
        }
        registry.publish(KnowledgeSource(**fields))  # type: ignore[arg-type]
    return registry


def _lexical() -> Iterator[KnowledgeRetriever]:
    """The `lite` driver: in-memory BM25, no service and no model."""
    registry = _registry()
    retriever = KnowledgeRetriever(registry, RetrievalConfig.from_file(CONFIG))
    retriever.index(registry.chunks_as_of(NOW, audience=Audience.STAFF))
    yield retriever


def _hybrid() -> Iterator[KnowledgeRetriever]:
    """The `full` driver: pgvector plus BM25. Not implemented (see the header).

    Skipped rather than absent, so the gap is visible in a test run instead of
    being something a reader has to notice is missing.
    """
    if not os.environ.get("CLARITY_EMBEDDINGS"):
        pytest.skip(
            "no embedding model: ModelRole.EMBED has no implementation and "
            "local-bge is a template stand-in, so the pgvector hybrid driver "
            "cannot be built yet (K02 devlog)"
        )
    raise AssertionError("unreachable until an embedder exists")


DRIVERS: dict[str, Callable[[], Iterator[KnowledgeRetriever]]] = {
    "lexical": _lexical,
    "hybrid": _hybrid,
}


@pytest.fixture(params=sorted(DRIVERS), ids=sorted(DRIVERS))
def retriever(request: pytest.FixtureRequest) -> Iterator[KnowledgeRetriever]:
    yield from DRIVERS[request.param]()


def search(retriever: KnowledgeRetriever, text: str, **kwargs):
    return retriever.search(text, audience=Audience.CUSTOMER, moment=NOW, **kwargs)


# -- what may not vary by index ------------------------------------------ #


def test_the_filters_are_applied_whatever_the_index(retriever) -> None:
    """A staff source is never a candidate, however well it scores.

    The property that must hold identically in both drivers: ranking never
    decides eligibility. "refund" matches the staff SOP strongly, so an index
    that filtered after scoring would surface it.
    """
    trace = search(retriever, "refund credited to the balance")

    assert trace.returned > 0
    assert all(hit.chunk.audience is Audience.CUSTOMER for hit in trace.hits)
    assert "SIM-SOP" not in {hit.chunk.source_id for hit in trace.hits}


def test_a_superseded_version_is_never_a_candidate(retriever) -> None:
    """Effective dating is a filter, not a ranking signal."""
    assert all(hit.chunk.effective_at(NOW) for hit in search(retriever, "refund").hits)


def test_the_best_hit_is_the_one_about_the_query(retriever) -> None:
    """Weak parity on ordering: the top hit, not the whole ranking.

    Two rankers with different scoring will order near-ties differently, and
    requiring an identical ordering would make the suite a test of one
    implementation. What both must get right is which source the query is
    actually about.
    """
    assert search(retriever, "my speed was reduced").hits[0].chunk.source_id == "SIM-SPEED"
    assert search(retriever, "unused allowance lapses").hits[0].chunk.source_id == "SIM-EXPIRY"


def test_top_k_is_honoured(retriever) -> None:
    assert search(retriever, "refund", top_k=1).returned <= 1
    assert search(retriever, "pack speed refund balance").returned <= retriever.config.top_k


def test_every_hit_carries_a_citation_and_a_matched_term(retriever) -> None:
    """A hit nothing can be checked against is not a usable hit (K03)."""
    for hit in search(retriever, "speed reduced fair usage").hits:
        assert hit.citation.startswith(hit.chunk.source_id)
        assert "@" in hit.citation
        assert hit.score > 0


def test_a_query_matching_nothing_returns_nothing(retriever) -> None:
    """Not a weak match. K03 refuses rather than composing from nothing."""
    trace = search(retriever, "zzzqqq nonexistent terminology")

    assert trace.returned == 0
    assert trace.hits == ()


def test_an_empty_query_returns_nothing(retriever) -> None:
    assert search(retriever, "").returned == 0
    assert search(retriever, "   ").returned == 0


def test_a_stopword_only_query_returns_nothing(retriever) -> None:
    """ "what is the" carries no term, so it must not match everything."""
    assert search(retriever, "what is the").returned == 0


def test_the_trace_says_whether_the_semantic_half_ran(retriever) -> None:
    """So a caller can tell a hybrid result from a lexical one.

    K03 composes an answer from this and should not describe a lexical result
    as hybrid. Asserted of both drivers because the honesty of the flag is the
    contract, not its value.
    """
    trace = search(retriever, "refund")

    assert trace.semantic is retriever.has_semantic


def test_retrieval_is_deterministic(retriever) -> None:
    """Same corpus and query, same result. Replay and the gate depend on it."""
    first = search(retriever, "speed reduced fair usage")
    second = search(retriever, "speed reduced fair usage")

    assert first.citations == second.citations
    assert [hit.score for hit in first.hits] == [hit.score for hit in second.hits]
