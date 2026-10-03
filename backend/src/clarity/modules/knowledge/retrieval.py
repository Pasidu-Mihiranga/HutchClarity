"""Retrieval: filter, rank, rerank, cut (K02, #32; plan 22 section 7).

The order is the design, and it is not negotiable:

1. **Filter** on effective date, audience, language and products. K01 owns
   this and it is authoritative. A chunk the reader may not see, or that was not
   in force at the moment being asked about, is not a weak candidate: it is not
   a candidate.
2. **Rank** the survivors, lexically with BM25 and, when an embedder exists,
   semantically too, fusing the two by configured weight.
3. **Rerank** deterministically, with small bonuses for a cited clause, the
   query's own language and a product in the case.
4. **Cut** to `top_k`, dropping anything below `min_relative_score`.

Filtering first rather than scoring first is what stops a disclosure or a wrong
answer about the law from depending on a relevance score. Scoring first and
filtering after is cheaper and can starve the reader: if the best-scoring
candidates are all staff-audience or superseded, a customer gets nothing while
relevant customer chunks sit below the cut.

**The semantic half does not exist yet, and this says so rather than pretending.**
Plan 22 section 7 specifies pgvector with embeddings from the `embed` role in
the `full` profile. There is no embedding model in the system: `ModelRole.EMBED`
is a declared name, `local-bge` is bound to the template provider as a stand-in,
and `RoleRouter.invoke` returns text, which cannot carry a vector. So
`SemanticRanker` is a protocol with no implementation, the retriever takes one
optionally, and with none the weights renormalise onto the lexical half.
`RetrievalTrace.semantic` reports whether it ran, so a caller can tell a hybrid
result from a lexical one instead of assuming.

That is ADR-0009 applied: every step works without a model, and models improve
it when configured.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from clarity.ai.language import query_terms
from clarity.kernel.common import Language
from clarity.modules.knowledge.bm25 import BM25Index
from clarity.modules.knowledge.config import RetrievalConfig
from clarity.modules.knowledge.registry import KnowledgeRegistry
from clarity.modules.knowledge.sources import Audience, Chunk


@dataclass(frozen=True)
class Hit:
    """One retrieved chunk, with enough of its working to be checked."""

    chunk: Chunk
    score: float
    lexical: float
    semantic: float | None
    matched: tuple[str, ...]
    """Query terms this chunk actually carries. Empty would be a bug."""

    @property
    def citation(self) -> str:
        return self.chunk.citation


@dataclass(frozen=True)
class RetrievalTrace:
    """What retrieval did, for the turn audit and for K03's verifier.

    ``semantic`` is here so nobody has to assume: a result produced without an
    embedder is a lexical result, and an answer composed from it should not be
    described as hybrid.
    """

    query: str
    terms: tuple[str, ...]
    candidates: int
    """How many chunks survived the filters, before ranking."""

    returned: int
    semantic: bool
    """Whether the semantic ranker ran. False means lexical only."""

    hits: tuple[Hit, ...] = field(default_factory=tuple)

    @property
    def citations(self) -> tuple[str, ...]:
        return tuple(hit.citation for hit in self.hits)

    @property
    def chunk_ids(self) -> tuple[str, ...]:
        return tuple(hit.chunk.chunk_id for hit in self.hits)

    def to_detail(self) -> dict[str, object]:
        return {
            "retrieval_candidates": self.candidates,
            "retrieval_returned": self.returned,
            "retrieval_semantic": self.semantic,
            "retrieval_citations": list(self.citations),
        }


class SemanticRanker(Protocol):
    """A vector ranker over a candidate set. No implementation yet (see above).

    Scores are expected normalised to 0..1 so the fusion weights mean the same
    thing on both halves. A ranker returning raw inner products would make the
    configured weights meaningless.
    """

    def scores(self, query: str, candidates: Sequence[Chunk]) -> dict[str, float]: ...


class KnowledgeRetriever:
    """Filters with the registry, then ranks what is left."""

    def __init__(
        self,
        registry: KnowledgeRegistry,
        config: RetrievalConfig,
        *,
        semantic: SemanticRanker | None = None,
    ) -> None:
        self._registry = registry
        self._config = config
        self._lexical = BM25Index(config.bm25)
        self._semantic = semantic

    @property
    def config(self) -> RetrievalConfig:
        return self._config

    @property
    def has_semantic(self) -> bool:
        return self._semantic is not None

    def index(self, chunks: Sequence[Chunk]) -> None:
        """Add chunks to the lexical index. Idempotent per chunk id."""
        self._lexical.add_all(chunks)

    def search(
        self,
        query: str,
        *,
        audience: Audience,
        moment: datetime | None = None,
        language: Language | None = None,
        product_ids: Sequence[str] = (),
        top_k: int | None = None,
    ) -> RetrievalTrace:
        """Retrieve for one query. ``audience`` is required, as in K01.

        ``language`` filters the corpus when given. It is separate from the
        language the *query* is in, which only influences the rerank: a Sinhala
        speaker asking about a clause published only in English should still
        find it, so the language is a preference at rank time and a filter only
        when a caller explicitly asks for one.
        """
        terms = query_terms(query)
        candidates = self._registry.chunks_as_of(
            moment,
            audience=audience,
            language=language,
            product_ids=product_ids,
        )
        if not terms or not candidates:
            return RetrievalTrace(
                query=query,
                terms=tuple(terms),
                candidates=len(candidates),
                returned=0,
                semantic=False,
            )

        lexical = self._lexical.scores(terms, candidates)
        semantic = self._semantic.scores(query, candidates) if self._semantic else {}
        fused = self._fuse(lexical, semantic)
        if not fused:
            # Terms and candidates, but nothing in common: a real outcome, not
            # an error. "internet is crawling in the evenings" shares no term
            # with a clause written as "data speed ... busy times of day", and
            # the honest answer is no sources rather than a weak one. K03
            # refuses on this rather than composing from nothing.
            return RetrievalTrace(
                query=query,
                terms=tuple(terms),
                candidates=len(candidates),
                returned=0,
                semantic=bool(semantic),
            )

        # Rerank the top candidates rather than the whole set: the bonuses are
        # small and cannot rescue something the ranking put nowhere near.
        shortlist = sorted(fused, key=lambda cid: (-fused[cid], cid))[: self._config.candidates]
        by_id = {chunk.chunk_id: chunk for chunk in candidates}
        scale = max(fused.values())
        reranked = {
            cid: fused[cid]
            + self._bonus(by_id[cid], query=query, product_ids=product_ids, scale=scale)
            for cid in shortlist
        }

        wanted = top_k if top_k is not None else self._config.top_k
        ordered = sorted(reranked, key=lambda cid: (-reranked[cid], cid))
        best = reranked[ordered[0]] if ordered else 0.0
        floor = best * self._config.min_relative_score

        # **There is no term-coverage or absolute-score guard here, and that is
        # a measured decision rather than an omission.**
        #
        # A query sharing one incidental word with a document gets a cited
        # answer from it: "what is the share price of the company?" retrieves
        # the pack-activation article because "price" appears in it. Two guards
        # were tried against the golden set and both were reverted:
        #
        # - a minimum share or count of the query's words matched. Half the
        #   *correct* hits in the golden set match exactly one term (25 of 51),
        #   so any such rule removes as many right answers as wrong ones.
        #   Measured: recall@5 fell from 0.967 to 0.900 at a third coverage and
        #   to 0.733 at two words, with Tamil reaching 0.000.
        # - an absolute score floor. The distributions overlap completely:
        #   correct hits run from 0.438 up and wrong hits reach 1.160, so there
        #   is no cut that separates them.
        #
        # What separates a relevant hit from an irrelevant one here is meaning,
        # not word overlap, and that is the embedding model the system does not
        # have (K02 and K03 devlogs). So retrieval recall is gated and good,
        # precision is weak and ungated, and this is the honest place to say so
        # rather than a number that looks fine.
        hits: list[Hit] = []
        for cid in ordered:
            if len(hits) >= wanted:
                break
            if reranked[cid] < floor:
                continue
            matched = self._lexical.matched_terms(terms, cid)
            hits.append(
                Hit(
                    chunk=by_id[cid],
                    score=reranked[cid],
                    lexical=lexical.get(cid, 0.0),
                    semantic=semantic.get(cid) if self._semantic else None,
                    matched=matched,
                )
            )
        hits_tuple = tuple(hits)
        return RetrievalTrace(
            query=query,
            terms=tuple(terms),
            candidates=len(candidates),
            returned=len(hits_tuple),
            semantic=bool(semantic),
            hits=hits_tuple,
        )

    # ------------------------------------------------------------------ #

    def _fuse(self, lexical: dict[str, float], semantic: dict[str, float]) -> dict[str, float]:
        """Combine the two rankings by configured weight.

        Both halves are normalised to 0..1 against their own best score first.
        Raw BM25 and a cosine similarity are not on the same scale, and
        weighting them unnormalised would make the configured weights mean
        whatever the corpus size happened to make them mean.

        With no semantic ranker the weights renormalise onto the lexical half,
        so the lexical ordering is preserved exactly rather than being halved
        and compared against zeros.
        """
        weights = self._config.hybrid
        if not semantic:
            return _normalise(lexical)

        total = weights.lexical + weights.semantic or 1.0
        lexical_share = weights.lexical / total
        semantic_share = weights.semantic / total
        normalised_lexical = _normalise(lexical)
        normalised_semantic = _normalise(semantic)
        return {
            cid: normalised_lexical.get(cid, 0.0) * lexical_share
            + normalised_semantic.get(cid, 0.0) * semantic_share
            for cid in set(normalised_lexical) | set(normalised_semantic)
        }

    def _bonus(
        self,
        chunk: Chunk,
        *,
        query: str,
        product_ids: Sequence[str],
        scale: float,
    ) -> float:
        """The deterministic rerank. Each bonus is a share of the top score.

        A share rather than an absolute, so a bonus nudges an ordering instead
        of replacing it: an absolute bonus larger than the score range would
        make the rerank the ranking.
        """
        rerank = self._config.rerank
        bonus = 0.0
        if chunk.clause_ref:
            bonus += rerank.clause_bonus
        if _query_language(query) is chunk.language:
            bonus += rerank.language_bonus
        if product_ids and chunk.product_ids and set(product_ids) & set(chunk.product_ids):
            bonus += rerank.product_bonus
        return bonus * scale


def _normalise(scores: dict[str, float]) -> dict[str, float]:
    """Scale to 0..1 against the best score present."""
    if not scores:
        return {}
    best = max(scores.values())
    if best <= 0:
        return dict.fromkeys(scores, 0.0)
    return {key: value / best for key, value in scores.items()}


def _query_language(query: str) -> Language | None:
    """The script the query is written in, for the rerank preference only.

    Deliberately script-based and so blind to Singlish, which is Latin script.
    A Singlish query therefore gets the English preference, which is right: the
    corpus it can actually match is the English one, because that is what the
    Singlish expansion in `terms.py` maps onto.
    """
    from clarity.modules.knowledge.ingest import dominant_script

    return dominant_script(query)


class QueryRewriter(Protocol):
    """Rewrites a customer's query into terms the corpus is written in.

    The optional assist on top of the deterministic expansion in `terms.py`.
    Plan 22 section 7 and issue #32 name the `extract` role for this, and
    ADR-0009 makes it an improvement rather than a requirement: the lexicon
    handles the common Singlish vocabulary without a model, and a rewriter is
    wired only where one is configured.

    Returning the query unchanged, or returning something empty, must be safe.
    """

    def rewrite(self, query: str) -> str: ...


class RewritingRetriever:
    """A retriever that tries a rewritten query and keeps the better result.

    **Both queries are run, and the original wins ties.** A rewrite is a model
    output and so is a guess: it can drop the one term that mattered, or
    hallucinate a term that pulls in the wrong clause. Running the original as
    well means a bad rewrite costs latency rather than an answer, which is the
    same shape as the bounded agent step falling back to its deterministic one
    (C03).

    "Better" is more hits, then a higher top score. Not the rewrite's own
    opinion of itself, which it has no way to form.
    """

    def __init__(self, inner: KnowledgeRetriever, rewriter: QueryRewriter | None = None) -> None:
        self._inner = inner
        self._rewriter = rewriter

    @property
    def config(self) -> RetrievalConfig:
        return self._inner.config

    def index(self, chunks: Sequence[Chunk]) -> None:
        self._inner.index(chunks)

    def search(self, query: str, **kwargs: object) -> RetrievalTrace:
        direct = self._inner.search(query, **kwargs)  # type: ignore[arg-type]
        if self._rewriter is None:
            return direct
        try:
            rewritten = self._rewriter.rewrite(query)
        except Exception:
            # A rewriter is a network call. Its failure is not the turn's.
            return direct
        if not rewritten or rewritten.strip() == query.strip():
            return direct

        alternative = self._inner.search(rewritten, **kwargs)  # type: ignore[arg-type]
        return alternative if _is_better(alternative, direct) else direct


def _is_better(candidate: RetrievalTrace, incumbent: RetrievalTrace) -> bool:
    """Strictly better, so the original query wins a tie."""
    if candidate.returned != incumbent.returned:
        return candidate.returned > incumbent.returned
    best_candidate = candidate.hits[0].score if candidate.hits else 0.0
    best_incumbent = incumbent.hits[0].score if incumbent.hits else 0.0
    return best_candidate > best_incumbent


__all__ = [
    "Hit",
    "KnowledgeRetriever",
    "QueryRewriter",
    "RetrievalTrace",
    "RewritingRetriever",
    "SemanticRanker",
]
