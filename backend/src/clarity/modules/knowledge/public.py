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
from clarity.modules.knowledge.sources import (
    Audience,
    Chunk,
    KnowledgeSource,
    SourceKind,
)

__all__ = [
    "CHUNKS",
    "SOURCES",
    "WORDS_OF_OVERLAP",
    "WORDS_PER_CHUNK",
    "Audience",
    "Chunk",
    "IngestionRefused",
    "KnowledgeRegistry",
    "KnowledgeRepository",
    "KnowledgeSource",
    "PublicationRefused",
    "SourceKind",
    "StoredKnowledgeRepository",
    "check_language",
    "clean",
    "dominant_script",
    "ingest",
    "publish_all",
]
