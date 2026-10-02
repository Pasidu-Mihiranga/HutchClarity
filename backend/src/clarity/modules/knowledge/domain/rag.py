"""Hybrid BM25-like lexical score + hash-bag embedding cosine."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from clarity.modules.knowledge.domain.corpus import Corpus

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_DIM = 64


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


def hash_embed(text: str, *, dim: int = _DIM) -> list[float]:
    """Stand-in for BGE-M3 / pgvector: bag-of-hashes into a fixed vector."""
    vec = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vec
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % dim
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vec[idx] += sign
    # L2 normalise
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True))


def _bm25_like(query_tokens: list[str], doc_tokens: list[str], *, avgdl: float) -> float:
    """Single-doc BM25-ish score (k1=1.2, b=0.75) with tf only (corpus IDF folded as 1)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    tf = Counter(doc_tokens)
    dl = len(doc_tokens)
    k1, b = 1.2, 0.75
    score = 0.0
    for term in set(query_tokens):
        freq = tf.get(term, 0)
        if freq == 0:
            continue
        denom = freq + k1 * (1 - b + b * dl / max(avgdl, 1.0))
        score += (freq * (k1 + 1)) / denom
    return score


@dataclass(slots=True)
class SearchHit:
    article_id: str
    title: str
    snippet: str
    score: float
    lexical: float
    semantic: float
    citation: dict[str, Any]
    pack_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "snippet": self.snippet,
            "score": round(self.score, 4),
            "lexical": round(self.lexical, 4),
            "semantic": round(self.semantic, 4),
            "citation": self.citation,
            "pack_version": self.pack_version,
        }


class HybridSearcher:
    """BM25-like term score + embedding cosine, blended."""

    def __init__(self, corpus: Corpus, *, alpha: float = 0.55) -> None:
        self._corpus = corpus
        self._alpha = alpha  # weight on lexical

    def search(self, query: str, *, lang: str = "en", limit: int = 5) -> list[SearchHit]:
        articles = self._corpus.all(lang=lang)
        if not articles:
            articles = self._corpus.all()
        q_tokens = tokenize(query)
        q_vec = hash_embed(query)
        docs = [(a, tokenize(f"{a.title} {a.body} {' '.join(a.labels)}")) for a in articles]
        avgdl = sum(len(t) for _, t in docs) / max(len(docs), 1)

        hits: list[SearchHit] = []
        for article, tokens in docs:
            lexical = _bm25_like(q_tokens, tokens, avgdl=avgdl)
            # Boost exact label matches
            label_boost = sum(1.0 for lab in article.labels if lab.lower() in q_tokens)
            lexical += label_boost
            semantic = cosine(q_vec, hash_embed(f"{article.title} {article.body}"))
            blended = self._alpha * lexical + (1 - self._alpha) * (semantic * 5.0)
            if blended <= 0:
                continue
            snippet = article.body[:180] + ("…" if len(article.body) > 180 else "")
            hits.append(
                SearchHit(
                    article_id=article.id,
                    title=article.title,
                    snippet=snippet,
                    score=blended,
                    lexical=lexical,
                    semantic=semantic,
                    citation={
                        "source": "knowledge",
                        "article_id": article.id,
                        "title": article.title,
                        "pack_version": article.pack_version,
                    },
                    pack_version=article.pack_version,
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]


class AnswerCache:
    """CX-approved answer cache keyed by normalised query."""

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(query: str, lang: str) -> str:
        return f"{lang}:{re.sub(r'\s+', ' ', query.strip().lower())}"

    def get(self, query: str, lang: str) -> dict[str, Any] | None:
        return self._cache.get(self._key(query, lang))

    def put(self, query: str, lang: str, answer: dict[str, Any]) -> dict[str, Any]:
        self._cache[self._key(query, lang)] = answer
        return answer

    def clear(self) -> None:
        self._cache.clear()
