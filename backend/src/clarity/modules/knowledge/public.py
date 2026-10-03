"""Public surface of the knowledge module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py).

The module owns governed knowledge content: source versions with an owner, an
effective window, an audience and a language, and the chunks ingestion makes of
them. ``KnowledgeRegistry`` is the way in and the way out: publish a version,
read back the chunks that were in force at a moment for a given audience.

K01 (#31) is the registry and ingestion. Ranking is K02 (#32) and grounded
answers with a citation verifier are K03 (#33); ``chunks_as_of`` is the filtered
candidate set both build on.
"""

from __future__ import annotations

from clarity.modules.knowledge.answers import (
    ACCORDING_TO,
    NO_SOURCE,
    QUOTED_IN_TEMPLATE,
    AnswerKind,
    Composer,
    GroundedAnswer,
    compose_answer,
    refuse,
)
from clarity.modules.knowledge.cache import (
    DEFAULT_CAPACITY,
    AnswerCache,
    CacheKey,
)
from clarity.modules.knowledge.citations import (
    CitationCheck,
    CitationFault,
    CitationReport,
    all_faults,
    citations_in,
    malformed_citations,
    sources_of,
    verify_citations,
)
from clarity.modules.knowledge.config import (
    BM25Params,
    HybridWeights,
    RerankBonuses,
    RetrievalConfig,
    RetrievalConfigInvalid,
)
from clarity.modules.knowledge.ingest import (
    WORDS_OF_OVERLAP,
    WORDS_PER_CHUNK,
    IngestionRefused,
    check_language,
    clean,
    dominant_script,
    ingest,
)
from clarity.modules.knowledge.registry import (
    KnowledgeRegistry,
    PublicationRefused,
    publish_all,
)
from clarity.modules.knowledge.repository import (
    CHUNKS,
    SOURCES,
    KnowledgeRepository,
    StoredKnowledgeRepository,
)
from clarity.modules.knowledge.retrieval import (
    Hit,
    KnowledgeRetriever,
    QueryRewriter,
    RetrievalTrace,
    RewritingRetriever,
    SemanticRanker,
)
from clarity.modules.knowledge.service import Answer, KnowledgeService
from clarity.modules.knowledge.sources import (
    Audience,
    Chunk,
    KnowledgeSource,
    SourceKind,
)
from clarity.modules.knowledge.terms import query_terms, tokens

__all__ = [
    "ACCORDING_TO",
    "CHUNKS",
    "DEFAULT_CAPACITY",
    "NO_SOURCE",
    "QUOTED_IN_TEMPLATE",
    "SOURCES",
    "WORDS_OF_OVERLAP",
    "WORDS_PER_CHUNK",
    "Answer",
    "AnswerCache",
    "AnswerKind",
    "Audience",
    "BM25Params",
    "CacheKey",
    "Chunk",
    "CitationCheck",
    "CitationFault",
    "CitationReport",
    "Composer",
    "GroundedAnswer",
    "Hit",
    "HybridWeights",
    "IngestionRefused",
    "KnowledgeRegistry",
    "KnowledgeRepository",
    "KnowledgeRetriever",
    "KnowledgeService",
    "KnowledgeSource",
    "PublicationRefused",
    "QueryRewriter",
    "RerankBonuses",
    "RetrievalConfig",
    "RetrievalConfigInvalid",
    "RetrievalTrace",
    "RewritingRetriever",
    "SemanticRanker",
    "SourceKind",
    "StoredKnowledgeRepository",
    "all_faults",
    "check_language",
    "citations_in",
    "clean",
    "compose_answer",
    "dominant_script",
    "ingest",
    "malformed_citations",
    "publish_all",
    "query_terms",
    "refuse",
    "sources_of",
    "tokens",
    "verify_citations",
]
