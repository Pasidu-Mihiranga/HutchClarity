"""The semantic half of retrieval (F4, K02; plan 22 section 7).

:class:`SemanticRanker` has been a protocol with no implementation, so every
retrieval has been lexical and the configured ``hybrid.semantic`` weight has
been dead. This is the implementation, over the :class:`~clarity.ai.embedding.Embedder`
port, so the same class serves the local driver in ``lite`` and a remote
embedding model in ``full`` without the retriever knowing which it has.

**What the vectors are embedded from.** Title and body, with the title counted
twice. A clause's title is the one line written to say what it is about
("Activating a data pack"), and weighting it is a cheap way to let that
intention carry. Counting it once leaves it drowned by a body ten times its
length; counting it more than twice turns retrieval into title matching.

**Chunk vectors are a derived index, not state.** A chunk is immutable once
published (K01), so its vector is too, and the alternative is re-embedding the
whole candidate set on every query. `_vectors` meets both conditions
`tests/architecture/test_module_state.py` sets for an index rather than
business state: every entry is a pure function of records the knowledge
repository already holds, and a chunk not in it is embedded on demand, so a
cold index answers exactly as a warm one does. Losing it costs CPU, never a
fact, and two replicas build the same one from the same records.

**The ranker fits the embedder to the corpus, once.** Inverse document
frequency is what makes the vectors rank rather than merely cluster (see
:mod:`clarity.ai.embedding`), and it needs document counts. :meth:`fit` takes
the published corpus and hands it to the embedder; the composition root calls
it with the same chunks it indexes lexically. An embedder that needs no corpus
statistics, such as a remote model, simply has no ``fit`` and is left alone.

Fitting on the whole corpus rather than per query is deliberate: IDF computed
over one query's candidate set would change with the candidates, so the same
document would score differently depending on what it was compared against.

**Scores are clamped at zero, not shifted.** Cosine runs -1 to 1 and signed
hashing puts unrelated pairs slightly either side of zero. A negative score
means "no evidence of relatedness", which is the same thing as zero for
ranking, so it is clamped. Shifting the range to 0..1 instead would give every
unrelated document half a point and make the fusion weights meaningless, which
is the mistake the protocol's docstring warns about.
"""

from __future__ import annotations

from collections.abc import Sequence

from clarity.ai.embedding import Embedder, cosine
from clarity.modules.knowledge.sources import Chunk

#: How much more the title counts than the body. See the module docstring.
TITLE_WEIGHT = 2


def embedding_text(chunk: Chunk) -> str:
    """What a chunk is embedded from: its title, weighted, then its body."""
    title = (chunk.title or "").strip()
    body = (chunk.text or "").strip()
    return " ".join([title] * TITLE_WEIGHT + [body]).strip()


class VectorSemanticRanker:
    """Ranks candidates by cosine against the query, through any embedder."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._vectors: dict[str, tuple[float, ...]] = {}

    @property
    def embedder_name(self) -> str:
        return self._embedder.name

    def fit(self, chunks: Sequence[Chunk]) -> None:
        """Give the embedder the corpus it needs for IDF, if it wants one.

        Duck-typed rather than widened into the `Embedder` port: a remote
        model is already trained and has nothing to fit, and putting `fit` in
        the protocol would make every driver implement a no-op to satisfy it.
        """
        fit = getattr(self._embedder, "fit", None)
        if fit is None:
            return
        fit([embedding_text(chunk) for chunk in chunks])
        # Vectors embedded before fitting used different weights, so they are
        # no longer comparable with ones embedded after.
        self._vectors.clear()

    def scores(self, query: str, candidates: Sequence[Chunk]) -> dict[str, float]:
        """Cosine per chunk id, clamped to 0..1.

        Returns an empty mapping for an empty query or an empty candidate set,
        which the retriever reads as "the semantic half did not run" and
        reports in its trace. Returning zeros instead would claim a hybrid
        result that had nothing in it.
        """
        if not query.strip() or not candidates:
            return {}

        missing = [
            chunk for chunk in candidates if chunk.chunk_id not in self._vectors
        ]
        if missing:
            vectors = self._embedder.embed([embedding_text(chunk) for chunk in missing])
            for chunk, vector in zip(missing, vectors, strict=True):
                self._vectors[chunk.chunk_id] = vector

        (query_vector,) = self._embedder.embed([query])
        return {
            chunk.chunk_id: max(0.0, cosine(query_vector, self._vectors[chunk.chunk_id]))
            for chunk in candidates
        }


__all__ = ["TITLE_WEIGHT", "VectorSemanticRanker", "embedding_text"]
