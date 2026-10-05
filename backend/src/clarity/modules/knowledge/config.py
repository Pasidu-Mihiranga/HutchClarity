"""Retrieval parameters, loaded from config rather than written in code (K02).

I10: no hard-coded policy values, and more to the point no hard-coded numbers
that decide what an answer is grounded in. ``config/ai/retrieval.yaml`` is the
file; this is the loader, and it refuses a file it cannot read exactly for the
same reason the rule-pack loader does. A retrieval config that silently falls
back to defaults is a deployment that is not running the parameters anyone
reviewed.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field

from clarity.kernel.common import ClarityModel


class RetrievalConfigInvalid(ValueError):
    """The retrieval config is missing a field or holds a value out of range."""


class BM25Params(ClarityModel):
    k1: float = Field(gt=0)
    b: float = Field(ge=0, le=1)


class HybridWeights(ClarityModel):
    lexical: float = Field(ge=0)
    semantic: float = Field(ge=0)
    min_semantic: float = Field(default=0.0, ge=0, le=1)
    """Absolute cosine below which a chunk is not a candidate at all (F4).

    This exists because turning the semantic half on removed a safety the
    lexical-only retriever had for free. With no embedder, a query sharing no
    term with any document produced no candidates, so K03 refused to answer
    and said why. A cosine is never exactly zero, so every document became a
    weak candidate, `min_relative_score` is a *share of the best* and could not
    tell "all weak" from "one strong", and a question about evening speeds
    grounded itself in the billing-cycle clause.

    An absolute floor is the right shape here where a relative one is not: the
    question is whether this chunk is related to the query at all, which does
    not depend on what else was retrieved.
    """


class RerankBonuses(ClarityModel):
    clause_bonus: float = Field(ge=0)
    language_bonus: float = Field(ge=0)
    product_bonus: float = Field(ge=0)


class RetrievalConfig(ClarityModel):
    """Everything retrieval reads from config."""

    version: int = Field(ge=1)
    top_k: int = Field(ge=1)
    candidates: int = Field(ge=1)
    min_relative_score: float = Field(ge=0, le=1)
    bm25: BM25Params
    hybrid: HybridWeights
    rerank: RerankBonuses

    @classmethod
    def from_file(cls, path: Path) -> RetrievalConfig:
        if not path.is_file():
            raise RetrievalConfigInvalid(f"{path} does not exist")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise RetrievalConfigInvalid(f"{path}: {error}") from error
        if not isinstance(document, dict):
            raise RetrievalConfigInvalid(f"{path}: expected a mapping at the top level")
        try:
            return cls.model_validate(document)
        except ValueError as error:
            raise RetrievalConfigInvalid(f"{path}: {error}") from error


__all__ = [
    "BM25Params",
    "HybridWeights",
    "RerankBonuses",
    "RetrievalConfig",
    "RetrievalConfigInvalid",
]
