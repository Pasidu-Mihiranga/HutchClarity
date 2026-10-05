"""The ``embed`` role: text to vectors (F4, plan 22 section 7, ADR-0009).

``ModelRole.EMBED`` has been a declared name with nothing behind it. The reason
is structural rather than an oversight: :meth:`RoleRouter.invoke` returns text,
and a vector is not text, so the embed role could not be invoked through the
same seam as every other role. This module is that seam.

**What is here, and what is deliberately not.**

:class:`Embedder` is the port. :class:`HashingEmbedder` is the local driver that
makes the chain terminate without a model, which is what ADR-0009 requires of
every role. A remote driver (plan 19 section 2.1 names BGE-M3) implements the
same port and is bound by the composition root when one is configured.

**What ``HashingEmbedder`` is, stated plainly, because the difference matters
to what an answer may claim.** It is a hashed character-n-gram vector space: a
classical IR technique, deterministic, no dependency, no network. It closes the
*morphological* gap that word-level BM25 leaves open, which is a real gap on
this corpus and a much bigger one in Sinhala and Tamil:

- ``renewed`` and ``renewal`` share the n-grams ``renew``, ``enew``, ``newa``,
  so a query written one way reaches a clause written the other. BM25 tokenises
  both as distinct terms and scores the pair at zero.
- Code-mixed Singlish spells the same word several ways. Subword overlap
  survives that; exact token matching does not.

It is **not** a learned embedding and it does not capture meaning. ``turned on``
and ``activated`` share no substring, so it cannot connect them, and no amount
of tuning here will. That is a synonym gap, it needs a trained multilingual
model, and the honest consequence is recorded against the ``rag`` gate rather
than papered over (see the F4 devlog and ``config/ai/gates.yaml``).

**Why the features are IDF-weighted, and why that is not optional.** The first
version of this was unweighted and it ranked worse than useless on the golden
set: the vector of a clause is dominated by the words every clause contains
("the", "charge", "billing"), so two unrelated clauses look similar because
both are written in English. ``renewal`` appearing three times in one document
and nowhere else is the whole signal, and unweighted it counted exactly as much
as ``the``. Inverse document frequency is the standard correction and it is
what makes a hashed vector space a retrieval tool rather than a language
detector. :func:`fit_idf` computes it from the corpus and
:meth:`HashingEmbedder.embed` applies it.

An unfitted embedder still works and says so: it falls back to unweighted,
which is honest about having no corpus statistics rather than refusing.

**Why hashing rather than a vocabulary.** A fixed vocabulary has to be built
from a corpus, which makes the vectors depend on which corpus built them and
makes a newly published clause unrepresentable until a rebuild. Hashing has no
vocabulary, so a document published a second ago embeds exactly like one
published last year. Collisions are the cost and at 512 dimensions over a
corpus this size they are rare and harmless: a collision adds a little noise to
one dimension, it does not swap two documents.

**Determinism is a requirement, not a nicety.** Replay has to be exact (I11),
so the hash is ``blake2b`` and never Python's ``hash``, which is randomised per
process by default and would make the same text embed differently on every run.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

#: Dimensions of the local vector space.
#:
#: 512 is a judgement, not a measurement: large enough that collisions between
#: the n-grams of one corpus are rare, small enough that embedding a 24-chunk
#: candidate set costs nothing worth measuring. A remote driver reports its own
#: model's dimensions and this does not constrain it.
DIMENSIONS = 512

#: Character n-gram widths. 3 to 5 is the usual range for subword retrieval:
#: 2 matches almost everything and 6 stops matching across a suffix change,
#: which is the whole point of doing this.
NGRAM_WIDTHS = (3, 4, 5)

#: Word-ish runs, in any script. ``\w`` with ``re.UNICODE`` keeps Sinhala and
#: Tamil, which an ASCII-only pattern would silently drop to empty vectors.
_WORD = re.compile(r"\w+", re.UNICODE)


class Embedder(Protocol):
    """Turns text into a unit vector.

    Vectors are L2-normalised, so a dot product *is* the cosine and a caller
    never has to know which one it is holding. ``name`` names the driver for
    the trace, exactly as a model provider does.
    """

    name: str

    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """One unit vector per input, in the order given."""
        ...


def _digest(feature: str) -> int:
    """A stable 64-bit integer for one feature.

    ``blake2b`` with a small digest rather than ``hash``: the built-in is
    salted per process (PYTHONHASHSEED), so vectors would differ between runs
    and a replay would not reproduce a retrieval.
    """
    return int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")


def features(text: str) -> Counter[str]:
    """The features of one piece of text: its words and their n-grams.

    Words are kept beside the n-grams rather than replaced by them. An exact
    word match is stronger evidence than a shared prefix, and keeping both lets
    the vector say so: ``renewal`` scores higher against ``renewal`` than
    against ``renewed``, while still scoring against both.

    Each word is padded with a boundary marker so an n-gram at the start of a
    word is distinct from the same letters mid-word. Without it ``on`` inside
    ``connection`` counts as the word ``on``, which is how subword retrieval
    gets a reputation for matching nonsense.
    """
    found: Counter[str] = Counter()
    for word in _WORD.findall(text.lower()):
        found[f"w:{word}"] += 1
        padded = f"<{word}>"
        for width in NGRAM_WIDTHS:
            if len(padded) < width:
                continue
            for start in range(len(padded) - width + 1):
                found[f"g:{padded[start : start + width]}"] += 1
    return found


def fit_idf(documents: Sequence[str], *, dimensions: int = DIMENSIONS) -> dict[int, float]:
    """Inverse document frequency per hash bucket, from a corpus.

    Smoothed as ``log((1 + N) / (1 + df)) + 1``, which is scikit-learn's form:
    it never reaches zero, so a feature in every document is damped rather than
    deleted. Deleting it would throw away the only signal a query of entirely
    common words has.

    Keyed by bucket rather than by feature, because the bucket is what the
    vector has. Two features that collide share an IDF, which is the same
    approximation the hashing itself already makes.
    """
    if not documents:
        return {}
    total = len(documents)
    document_frequency: Counter[int] = Counter()
    for text in documents:
        document_frequency.update(
            {_digest(feature) % dimensions for feature in features(text)}
        )
    return {
        bucket: math.log((1.0 + total) / (1.0 + df)) + 1.0
        for bucket, df in document_frequency.items()
    }


class HashingEmbedder:
    """The local ``embed`` driver. Deterministic, offline, no dependency.

    Feature weights are sublinear in frequency (``1 + log tf``), the standard
    damping: a clause repeating "renewal" three times is more about renewal
    than one mentioning it once, but not three times more. They are then scaled
    by the corpus IDF when one has been fitted (see the module docstring).

    The sign of each feature's contribution comes from the hash too. Signed
    hashing makes collisions cancel on average instead of always adding, which
    is what keeps a 512-dimension space usable without a vocabulary.
    """

    name = "local-hash-ngram"

    def __init__(
        self,
        *,
        dimensions: int = DIMENSIONS,
        idf: dict[int, float] | None = None,
    ) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self._dimensions = dimensions
        self._idf = dict(idf or {})

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def fitted(self) -> bool:
        """Whether corpus statistics are in use. False means unweighted."""
        return bool(self._idf)

    def fit(self, documents: Sequence[str]) -> None:
        """Learn the IDF weights from a corpus. Idempotent per corpus."""
        self._idf = fit_idf(documents, dimensions=self._dimensions)

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self._dimensions
        for feature, count in features(text).items():
            code = _digest(feature)
            bucket = code % self._dimensions
            sign = 1.0 if (code >> 63) & 1 else -1.0
            # Unfitted corpora weight every bucket at 1.0, which is the
            # unweighted vector space and is reported by `fitted`.
            weight = self._idf.get(bucket, 1.0)
            vector[bucket] += sign * (1.0 + math.log(count)) * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            # No word characters at all: punctuation, or a script the pattern
            # does not cover. A zero vector scores zero against everything,
            # which is the right answer rather than an error.
            return tuple(vector)
        return tuple(value / norm for value in vector)


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity of two vectors from the same embedder.

    Both are expected L2-normalised, so this is their dot product. It is
    computed as a dot product rather than re-normalising, because a driver that
    returned unnormalised vectors is a bug in the driver and silently rescuing
    it here would hide that.
    """
    return sum(a * b for a, b in zip(left, right, strict=True))


__all__ = [
    "DIMENSIONS",
    "NGRAM_WIDTHS",
    "Embedder",
    "HashingEmbedder",
    "cosine",
    "features",
    "fit_idf",
]
