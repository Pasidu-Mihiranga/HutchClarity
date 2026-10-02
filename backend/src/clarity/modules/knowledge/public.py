"""Public facade for the knowledge module."""

from __future__ import annotations

from typing import Any

from clarity.modules.knowledge.domain.corpus import Article, Corpus
from clarity.modules.knowledge.domain.rag import AnswerCache, HybridSearcher

_corpus = Corpus()
_cache = AnswerCache()
_searcher = HybridSearcher(_corpus)


def get_corpus() -> Corpus:
    return _corpus


def reset_knowledge(corpus: Corpus | None = None) -> None:
    global _corpus, _searcher, _cache
    if corpus is None:
        _corpus.reset_seed()
    else:
        _corpus = corpus
    _searcher = HybridSearcher(_corpus)
    _cache = AnswerCache()


def get_article(article_id: str) -> Article:
    article = _corpus.get(article_id)
    if article is None:
        raise KeyError(article_id)
    return article


def search(query: str, lang: str = "en", *, limit: int = 5) -> dict[str, Any]:
    """Hybrid search with citations; returns cached answer when present."""
    if not query or not query.strip():
        raise ValueError("query is required")
    normalised = query.strip()
    cached = _cache.get(normalised, lang)
    if cached is not None:
        return {**cached, "cached": True}

    hits = [h.to_dict() for h in _searcher.search(normalised, lang=lang, limit=limit)]
    answer_text = ""
    citations: list[dict[str, Any]] = []
    if hits:
        top = hits[0]
        article = get_article(top["article_id"])
        answer_text = article.body
        citations = [h["citation"] for h in hits]

    result = {
        "query": normalised,
        "lang": lang,
        "answer": answer_text,
        "hits": hits,
        "citations": citations,
        "cached": False,
    }
    # Cache successful answers for instant CX-approved replies.
    if answer_text:
        _cache.put(normalised, lang, {k: v for k, v in result.items() if k != "cached"})
    return result


__all__ = [
    "Article",
    "Corpus",
    "get_article",
    "get_corpus",
    "reset_knowledge",
    "search",
]
