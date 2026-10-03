"""Okapi BM25 over the knowledge chunks (K02, #32; plan 22 section 7).

The `lite` index: pure Python, no service, no model, which is what keeps the
zero-setup profile honest (ADR-0006).

**Why the index is built once but scored per candidate set.** Tokenising the
corpus on every query would make retrieval O(corpus) in Python, so the postings
are built once and updated when a version is published. But the *IDF* is
computed over the candidate set the reader may actually see, not over the whole
corpus, and that is deliberate:

- Filtering before scoring is not optional. Scoring first and filtering after
  can starve a reader: if the top candidates all happen to be staff-audience or
  superseded, a customer gets nothing while relevant customer chunks sit just
  below the cut. K01 decides what may be read; this only orders it.
- Given that the candidate set is what is being ranked, its own term statistics
  are the right ones. A term common across the whole corpus but rare among the
  chunks in force for this reader is a discriminating term *for this query*.

The cost is that IDF shifts as filters change, so a score is comparable within
one query and not across two. Nothing compares them across queries: the cutoff
is relative to the best hit in the same result set for exactly this reason.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from clarity.modules.knowledge.config import BM25Params
from clarity.modules.knowledge.sources import Chunk
from clarity.modules.knowledge.terms import tokens


class BM25Index:
    """Term frequencies per chunk, scored against a candidate subset."""

    def __init__(self, params: BM25Params) -> None:
        self._params = params
        #: chunk_id -> term -> count within that chunk
        self._frequencies: dict[str, Counter[str]] = {}
        #: chunk_id -> token count, for the length normalisation
        self._lengths: dict[str, int] = {}

    def add(self, chunk: Chunk) -> None:
        """Index one chunk. Re-adding the same id replaces it."""
        counted = Counter(tokens(chunk.text))
        self._frequencies[chunk.chunk_id] = counted
        self._lengths[chunk.chunk_id] = sum(counted.values())

    def add_all(self, chunks: Sequence[Chunk]) -> None:
        for chunk in chunks:
            self.add(chunk)

    def forget(self, chunk_id: str) -> None:
        self._frequencies.pop(chunk_id, None)
        self._lengths.pop(chunk_id, None)

    def knows(self, chunk_id: str) -> bool:
        return chunk_id in self._frequencies

    def __len__(self) -> int:
        return len(self._frequencies)

    def scores(self, query: Sequence[str], candidates: Sequence[Chunk]) -> dict[str, float]:
        """BM25 per candidate, keyed by chunk id. Zero scores are omitted.

        Omitted rather than zero so a caller cannot mistake "did not match" for
        "matched weakly": a chunk sharing no term with the query is not a hit at
        any threshold.
        """
        if not query or not candidates:
            return {}

        # Any candidate not yet indexed is indexed now, so a caller cannot get
        # a silently empty result by forgetting to index. This is the only
        # place that matters, because the registry indexes on publish.
        for chunk in candidates:
            if chunk.chunk_id not in self._frequencies:
                self.add(chunk)

        ids = [chunk.chunk_id for chunk in candidates]
        total = len(ids)
        average_length = sum(self._lengths[cid] for cid in ids) / total or 1.0

        k1 = self._params.k1
        b = self._params.b
        scored: dict[str, float] = {}

        # A query term repeated ("speed speed" after expansion) must not count
        # twice: that would let an expansion with several synonyms outweigh a
        # direct match.
        for term in dict.fromkeys(query):
            carrying = [cid for cid in ids if self._frequencies[cid].get(term)]
            if not carrying:
                continue
            # Standard BM25 IDF, over the candidate set. The +1 inside the log
            # keeps it positive for a term present in every candidate, which
            # the classic form makes negative.
            idf = math.log(1 + (total - len(carrying) + 0.5) / (len(carrying) + 0.5))
            for cid in carrying:
                frequency = self._frequencies[cid][term]
                length = self._lengths[cid] or 1
                saturated = (
                    frequency * (k1 + 1) / (frequency + k1 * (1 - b + b * length / average_length))
                )
                scored[cid] = scored.get(cid, 0.0) + idf * saturated
        return scored

    def matched_terms(self, query: Sequence[str], chunk_id: str) -> tuple[str, ...]:
        """Which query terms this chunk actually carries. For the trace."""
        frequencies = self._frequencies.get(chunk_id)
        if frequencies is None:
            return ()
        return tuple(term for term in dict.fromkeys(query) if frequencies.get(term))


__all__ = ["BM25Index"]
