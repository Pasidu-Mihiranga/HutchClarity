"""The knowledge module's one entry point for answering a question (K03, #33).

Retrieve, compose, verify, cache. Everything a caller needs is one call, and
everything a caller could get wrong is decided here rather than left to them:
the audience is required, the moment is explicit, and nothing case-specific
reaches the cache.

Plan 22 section 7 end to end.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from clarity.kernel.common import Language, utc_now
from clarity.modules.knowledge.answers import (
    AnswerKind,
    Composer,
    GroundedAnswer,
    compose_answer,
)
from clarity.modules.knowledge.cache import AnswerCache, CacheKey
from clarity.modules.knowledge.registry import KnowledgeRegistry
from clarity.modules.knowledge.retrieval import KnowledgeRetriever, RetrievalTrace
from clarity.modules.knowledge.sources import Audience


@dataclass(frozen=True)
class Answer:
    """A grounded answer and the retrieval behind it.

    The trace travels with the answer because the answer is only as checkable
    as the thing it was composed from: an auditor asking "why did it say that"
    needs the candidate count and the citations, not just the text.
    """

    answer: GroundedAnswer
    trace: RetrievalTrace
    cached: bool = False

    @property
    def text(self) -> str:
        return self.answer.text

    @property
    def grounded(self) -> bool:
        return self.answer.grounded

    @property
    def needs_person(self) -> bool:
        return self.answer.needs_person

    @property
    def citations(self) -> tuple[str, ...]:
        return self.answer.citations

    def to_detail(self) -> dict[str, object]:
        return {**self.trace.to_detail(), **self.answer.to_detail(), "answer_cached": self.cached}


class KnowledgeService:
    """Answer a question from published sources, or say it cannot."""

    def __init__(
        self,
        registry: KnowledgeRegistry,
        retriever: KnowledgeRetriever,
        *,
        cache: AnswerCache | None = None,
        composer: Composer | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._registry = registry
        self._retriever = retriever
        self._cache = cache
        self._composer = composer
        self._clock = clock

    @property
    def cache(self) -> AnswerCache | None:
        return self._cache

    def ask(
        self,
        query: str,
        *,
        audience: Audience,
        language: Language = Language.EN,
        moment: datetime | None = None,
        product_ids: tuple[str, ...] = (),
        case_specific: bool = False,
    ) -> Answer:
        """Answer one question.

        ``case_specific`` is the caller saying this answer depends on one
        customer's records. It is not cached, and it defaults to ``False``
        because this module has no access to a case: the default is true of
        every call it can currently receive, and a caller that gains case
        facts has to say so.

        ``moment`` is the moment being asked *about*, which for a dispute is
        the event time and not now (plan 22 section 7).
        """
        at = moment if moment is not None else self._clock()
        cacheable = self._cache is not None and not case_specific and not product_ids
        key = (
            CacheKey.for_query(
                query,
                language=language,
                audience=audience,
                corpus_version=self._registry.corpus_version(),
            )
            if cacheable
            else None
        )

        if key is not None and self._cache is not None:
            hit = self._cache.get(key)
            if hit is not None:
                # The trace is not cached with the answer: it describes one
                # retrieval, and presenting a previous query's trace as this
                # one's would make the audit record wrong. The citations on the
                # answer are what remains checkable.
                return Answer(
                    answer=hit,
                    trace=RetrievalTrace(
                        query=query,
                        terms=(),
                        candidates=0,
                        returned=len(hit.citations),
                        semantic=False,
                    ),
                    cached=True,
                )

        trace = self._retriever.search(
            query,
            audience=audience,
            moment=at,
            product_ids=product_ids,
        )
        answer = compose_answer(
            trace,
            audience=audience,
            moment=at,
            language=language,
            composer=self._composer,
        )

        if key is not None and self._cache is not None and answer.kind is not AnswerKind.REFUSAL:
            self._cache.put(key, answer, generic=not case_specific)

        return Answer(answer=answer, trace=trace)

    def on_knowledge_published(self, corpus_version: str) -> int:
        """Drop cached answers composed against an older corpus.

        What a `knowledge.published` consumer calls. Correctness does not
        depend on this running: the corpus version is part of the cache key, so
        a stale entry is unreachable rather than merely marked. This stops a
        long-lived process carrying dead entries.
        """
        if self._cache is None:
            return 0
        return self._cache.invalidate(corpus_version)


__all__ = ["Answer", "KnowledgeService"]
