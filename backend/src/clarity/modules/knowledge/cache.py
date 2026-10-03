"""The answer cache: generic answers only, and never stale (K03, #33).

Plan 22 section 7 ("Cache"): an exact and meaning cache for generic,
CX-approved answers only, keyed by catalogue version and language, never
case-specific; and ("Freshness") a `knowledge.published` event invalidates
entries and re-indexes affected chunks.

**Staleness is made impossible by the key, not prevented by the event.** The
corpus fingerprint is part of the cache key, so publishing anything changes
every key and no lookup can return an answer composed from superseded text.
The event still fires, because a consumer has re-indexing to do and because a
long-lived process should drop the dead entries rather than carry them, but the
*correctness* does not depend on the event arriving. An invalidation scheme that
depends on a message being delivered is one lost message away from quoting last
month's terms with this month's confidence.

**Only generic answers are cached, and the rule is enforced rather than
documented.** `put` refuses an answer that is not grounded, refuses a refusal,
and refuses anything a caller marks case-specific. A cache that can hold a
case-specific answer will eventually serve one customer's figures to another,
which is the worst available outcome for a module whose job is to be checkable.

**The cache holds no customer text.** The key is a hash of the normalised query
terms, not the query, so the stored row cannot be read back into what somebody
typed. The query itself is never stored.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from clarity.ai.language import query_terms
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import Language
from clarity.modules.knowledge.answers import AnswerKind, GroundedAnswer
from clarity.modules.knowledge.sources import Audience

#: How many answers one process keeps. Small on purpose: this is a latency and
#: token saver for repeated generic questions, not a store. The eviction is
#: least-recently-used, so the questions people actually repeat stay warm.
DEFAULT_CAPACITY = 512


@dataclass(frozen=True)
class CacheKey:
    """What makes two questions the same question.

    The audience is in the key. Without it a staff answer composed from staff
    sources could be served to a customer, which the retrieval filter went to
    some trouble to prevent.
    """

    terms_hash: str
    language: str
    audience: str
    corpus_version: str

    @classmethod
    def for_query(
        cls,
        query: str,
        *,
        language: Language,
        audience: Audience,
        corpus_version: str,
    ) -> CacheKey:
        """Key one lookup.

        The terms rather than the raw text, so "why is my speed slow" and "Why
        is my speed slow?" are one entry, and so that nothing recoverable as
        customer text is stored (I13).
        """
        terms = sorted(set(query_terms(query)))
        return cls(
            terms_hash=hash_payload({"terms": terms}),
            language=language.value,
            audience=audience.value,
            corpus_version=corpus_version,
        )


class AnswerCache:
    """An LRU of grounded, generic answers, keyed by corpus version."""

    def __init__(self, *, capacity: int = DEFAULT_CAPACITY) -> None:
        self._entries: OrderedDict[CacheKey, GroundedAnswer] = OrderedDict()
        self._capacity = max(1, capacity)
        self.hits = 0
        self.misses = 0
        self.refused = 0
        """Answers `put` declined to store. Non-zero is normal, not a fault."""

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: CacheKey) -> GroundedAnswer | None:
        found = self._entries.get(key)
        if found is None:
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return found

    def put(self, key: CacheKey, answer: GroundedAnswer, *, generic: bool = True) -> bool:
        """Store an answer, if it is the kind of answer that may be stored.

        Returns whether it was stored, so a caller can assert on it rather than
        having to inspect the cache.

        Four refusals, each for its own reason:

        - **not generic**: a case-specific answer in a shared cache is one
          customer's figures waiting to be served to another.
        - **a refusal**: caching "I do not know" would keep saying it after the
          source that answers it is published, and that is the one answer whose
          staleness a customer cannot detect.
        - **not grounded**: an answer whose citations did not verify must not
          become the fast path.
        - **no citations**: nothing to check it against later.
        """
        if not generic or answer.kind is AnswerKind.REFUSAL or not answer.grounded:
            self.refused += 1
            return False
        if not answer.citations:
            self.refused += 1
            return False

        self._entries[key] = answer
        self._entries.move_to_end(key)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)
        return True

    def invalidate(self, corpus_version: str) -> int:
        """Drop everything not composed against ``corpus_version``.

        What a `knowledge.published` consumer calls. Correctness does not
        depend on it, because the version is in the key: this is housekeeping
        so a long-lived process does not carry dead entries.
        """
        dead = [key for key in self._entries if key.corpus_version != corpus_version]
        for key in dead:
            del self._entries[key]
        return len(dead)

    def clear(self) -> None:
        self._entries.clear()


__all__ = ["DEFAULT_CAPACITY", "AnswerCache", "CacheKey"]
