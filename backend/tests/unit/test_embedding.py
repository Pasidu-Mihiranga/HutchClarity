"""The `embed` role's local driver, and the semantic ranker over it (F4).

What these pin is mostly about honesty rather than accuracy. The embedder is a
hashed character-n-gram space, so it has a small number of properties worth
guaranteeing and one big limitation worth stating in a test so nobody
rediscovers it as a bug:

- it is **deterministic across processes**, because replay has to be exact
  (I11) and Python's own `hash` is salted per process;
- it closes a **morphological** gap (`renewal` against `renewed`);
- it does **not** close a **synonym** gap (`activated` against `turned on`),
  and the test says so rather than leaving it to be assumed either way.

The last one is the reason the `rag.citation_accuracy` gate still fails after
F4. A test asserting it is how that stays a known limit instead of becoming a
surprise when somebody expects hybrid retrieval to understand paraphrase.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime

import pytest

from clarity.ai.embedding import (
    DIMENSIONS,
    HashingEmbedder,
    cosine,
    features,
    fit_idf,
)
from clarity.kernel.common import Language
from clarity.modules.knowledge.public import Audience, SourceKind
from clarity.modules.knowledge.semantic import (
    TITLE_WEIGHT,
    VectorSemanticRanker,
    embedding_text,
)
from clarity.modules.knowledge.sources import Chunk

CLAUSES = {
    "vas-consent": (
        "Value added service subscriptions",
        "A value added service subscription requires the subscriber's explicit "
        "consent before the first charge. A renewal notification is sent before "
        "each renewal charge is applied.",
    ),
    "billing-cycle": (
        "The billing cycle",
        "The billing cycle begins on the account's own anniversary date each "
        "month. Allowances that reset monthly do so at the start of the cycle.",
    ),
    "pack-activate": (
        "Activating a data pack",
        "A data pack is activated immediately on successful purchase and a "
        "confirmation message is sent. Activation may fail where the balance is "
        "insufficient.",
    ),
}


def chunk(chunk_id: str, title: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_id=chunk_id,
        version=1,
        ordinal=0,
        text=text,
        title=title,
        kind=SourceKind.LEGAL_TEXT,
        audience=Audience.CUSTOMER,
        owner="hutch-sim",
        language=Language.EN,
        effective_from=datetime(2024, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def corpus() -> list[Chunk]:
    return [chunk(cid, title, text) for cid, (title, text) in CLAUSES.items()]


@pytest.fixture
def fitted(corpus: list[Chunk]) -> HashingEmbedder:
    embedder = HashingEmbedder()
    embedder.fit([embedding_text(c) for c in corpus])
    return embedder


# --------------------------------------------------------------- the vectors


def test_vectors_are_unit_length(fitted: HashingEmbedder):
    """So a dot product is the cosine and no caller has to normalise."""
    (vector,) = fitted.embed(["a renewal notification is sent"])
    assert len(vector) == DIMENSIONS
    assert pytest.approx(sum(v * v for v in vector) ** 0.5, abs=1e-9) == 1.0


def test_text_with_no_word_characters_embeds_to_zero(fitted: HashingEmbedder):
    """Punctuation is not an error, and it matches nothing."""
    (vector,) = fitted.embed(["... !!! ???"])
    assert all(value == 0.0 for value in vector)
    (other,) = fitted.embed(["renewal"])
    assert cosine(vector, other) == 0.0


def test_the_same_text_embeds_the_same_way_in_a_new_process():
    """Determinism across processes, which `hash` would not give (I11).

    Run in a subprocess on purpose: within one process a salted hash is still
    self-consistent, so an in-process assertion would pass even if the
    embedder used `hash`. A fresh interpreter gets a fresh salt.
    """
    code = (
        "from clarity.ai.embedding import HashingEmbedder;"
        "v = HashingEmbedder().embed(['renewal notification'])[0];"
        "print(round(sum(v[:8]), 10))"
    )
    first = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    second = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert first.stdout.strip() == second.stdout.strip()
    assert first.stdout.strip() not in {"", "0.0"}


def test_sinhala_and_tamil_produce_real_vectors(fitted: HashingEmbedder):
    """An ASCII-only word pattern would silently return zeros for both."""
    for text in ("මගේ ඩේටා ඉක්මනින් ඉවර වුණා", "எனது ரீலோட் வரவு வைக்கப்படவில்லை"):
        (vector,) = fitted.embed([text])
        assert any(value != 0.0 for value in vector), text


# ------------------------------------------------------------- the features


def test_word_boundaries_are_marked(fitted: HashingEmbedder):
    """`on` inside `connection` must not count as the word `on`."""
    found = features("on connection")
    assert "w:on" in found
    assert "g:<on>" in found
    # The three-gram of the padded word `on` appears once, from `on` itself,
    # not again from the middle of `connection`.
    assert found["g:<on>"] == 1


def test_idf_falls_as_document_frequency_rises(corpus: list[Chunk]):
    """The invariant, asserted over every bucket rather than two chosen words.

    An earlier version of this picked `the` and `renewal` and compared their
    buckets. It failed, and it was the test that was wrong: at 512 dimensions
    the bucket for `renewal` also receives a feature present in every clause,
    so the two shared an IDF. Collisions are the documented cost of having no
    vocabulary, so a test must not assume any particular feature owns a bucket.

    What is actually promised is monotonicity: a bucket seen in more documents
    is weighted no higher than one seen in fewer.
    """
    from clarity.ai.embedding import _digest

    documents = [embedding_text(c) for c in corpus]
    idf = fit_idf(documents)

    frequency: dict[int, int] = {}
    for text in documents:
        for bucket in {_digest(f) % DIMENSIONS for f in features(text)}:
            frequency[bucket] = frequency.get(bucket, 0) + 1

    assert set(frequency) == set(idf)
    # More documents must never mean more weight.
    for left, left_df in frequency.items():
        for right, right_df in frequency.items():
            if left_df < right_df:
                assert idf[left] > idf[right]

    # And the range is real: something is rarer than something else here.
    assert max(idf.values()) > min(idf.values())
    # Damped, never deleted: a query of only common words still has signal.
    assert min(idf.values()) > 0


def test_an_unfitted_embedder_says_so_and_still_works():
    """No corpus statistics is a reported state, not a refusal."""
    embedder = HashingEmbedder()
    assert embedder.fitted is False
    (vector,) = embedder.embed(["renewal"])
    assert any(value != 0.0 for value in vector)
    embedder.fit(["a renewal notification", "the billing cycle"])
    assert embedder.fitted is True


# ----------------------------------------------- what it does and does not do


def test_it_closes_a_morphological_gap(fitted: HashingEmbedder, corpus: list[Chunk]):
    """`renewed` reaches a clause written `renewal`. BM25 scores that zero.

    This is the gap subword matching exists to close, and the reason it is
    worth more on Sinhala and Tamil than on English.
    """
    ranker = VectorSemanticRanker(fitted)
    scores = ranker.scores("renewed", corpus)
    assert scores["vas-consent"] > scores["billing-cycle"]
    assert scores["vas-consent"] > scores["pack-activate"]


def test_it_does_not_close_a_synonym_gap(fitted: HashingEmbedder, corpus: list[Chunk]):
    """`turned on` does not reach `activated`, and that is a stated limit.

    Asserted rather than assumed. This is why `rag.citation_accuracy` still
    fails after F4: closing it needs a learned multilingual model, which the
    `Embedder` port exists to accept. If this test ever starts failing because
    somebody wired such a model, the right response is to delete it, not to
    work around it.
    """
    ranker = VectorSemanticRanker(fitted)
    scores = ranker.scores("it never turned on", corpus)
    assert scores["pack-activate"] <= max(
        scores["vas-consent"], scores["billing-cycle"]
    ), "a hashed n-gram space is not expected to connect 'turned on' to 'activated'"


# -------------------------------------------------------------- the ranker


def test_the_title_is_weighted(fitted: HashingEmbedder):
    """The one line written to say what a clause is about should carry."""
    text = embedding_text(chunk("x", "Fair usage", "Speed may be reduced."))
    assert text.count("Fair usage") == TITLE_WEIGHT


def test_scores_are_clamped_not_shifted(fitted: HashingEmbedder, corpus: list[Chunk]):
    """0 means unrelated. Shifting to 0..1 would give everything half a point."""
    scores = VectorSemanticRanker(fitted).scores("recipe for chicken curry", corpus)
    assert scores
    assert all(value >= 0.0 for value in scores.values())
    assert all(value < 0.5 for value in scores.values())


def test_an_empty_query_or_corpus_runs_no_semantic_half(fitted: HashingEmbedder, corpus):
    """An empty mapping is what the retriever reads as "it did not run"."""
    ranker = VectorSemanticRanker(fitted)
    assert ranker.scores("   ", corpus) == {}
    assert ranker.scores("renewal", []) == {}


def test_chunk_vectors_are_cached_and_refitting_clears_them(corpus: list[Chunk]):
    """A chunk is immutable, so its vector is; a refit changes the weights."""
    counted: list[int] = []

    class Counting(HashingEmbedder):
        def embed(self, texts):  # type: ignore[override]
            counted.append(len(texts))
            return super().embed(texts)

    ranker = VectorSemanticRanker(Counting())
    ranker.fit(corpus)
    ranker.scores("renewal", corpus)
    # Three chunks plus the query.
    assert counted[-2:] == [len(corpus), 1]

    ranker.scores("renewal", corpus)
    # Only the query the second time; the chunks came from the cache.
    assert counted[-1] == 1

    ranker.fit(corpus)
    ranker.scores("renewal", corpus)
    assert counted[-2:] == [len(corpus), 1]


def test_a_ranker_over_an_embedder_with_no_fit_is_left_alone(corpus: list[Chunk]):
    """A remote model is already trained, so `fit` is duck-typed, not required."""

    class Trained:
        name = "remote-pretend"
        dimensions = 4

        def embed(self, texts):
            return [(1.0, 0.0, 0.0, 0.0) for _ in texts]

    ranker = VectorSemanticRanker(Trained())
    ranker.fit(corpus)  # must not raise
    scores = ranker.scores("anything", corpus)
    assert set(scores) == {c.chunk_id for c in corpus}
