"""Where knowledge sources and chunks live (K01, #31; B02, ADR-0013).

Governed content is a record, not runtime state: a published clause outlives
the process that ingested it and has to be readable years later for "what
applied then", so it sits behind a repository like any other artefact.

Chunks are stored rather than derived on read. Ingestion is deterministic, so
re-chunking on demand would give the same answer, but a published version's
chunks are what an answer cited: changing the chunker must not silently change
what a citation from last March points at. Re-ingestion is explicit
(``replace_chunks``) and belongs to publishing a version, not to reading one.
"""

from __future__ import annotations

from typing import Protocol

from clarity.modules.knowledge.sources import Chunk, KnowledgeSource
from clarity.platform.persistence import Repository

#: Collection names the drivers use. One collection is one table in B05.
SOURCES = "knowledge.sources"
CHUNKS = "knowledge.chunks"


class KnowledgeRepository(Protocol):
    """Published source versions and the chunks ingested from them."""

    def save_source(self, source: KnowledgeSource) -> None: ...

    def versions(self, source_id: str) -> list[KnowledgeSource]:
        """Every stored version of one source, in no particular order."""
        ...

    def all_sources(self) -> list[KnowledgeSource]: ...

    def replace_chunks(self, source_id: str, version: int, chunks: tuple[Chunk, ...]) -> None:
        """Set the chunks for one source version, discarding any it had."""
        ...

    def all_chunks(self) -> list[Chunk]: ...


class StoredKnowledgeRepository:
    """``KnowledgeRepository`` over any persistence driver."""

    def __init__(
        self,
        sources: Repository[str, KnowledgeSource],
        chunks: Repository[str, Chunk],
    ) -> None:
        self._sources = sources
        self._chunks = chunks

    @staticmethod
    def _key(source_id: str, version: int) -> str:
        return f"{source_id}@{version}"

    def save_source(self, source: KnowledgeSource) -> None:
        self._sources.put(self._key(source.source_id, source.version), source)

    def versions(self, source_id: str) -> list[KnowledgeSource]:
        return [source for source in self._sources.values() if source.source_id == source_id]

    def all_sources(self) -> list[KnowledgeSource]:
        return self._sources.values()

    def replace_chunks(self, source_id: str, version: int, chunks: tuple[Chunk, ...]) -> None:
        for existing in self._chunks.values():
            if existing.source_id == source_id and existing.version == version:
                self._chunks.delete(existing.chunk_id)
        for chunk in chunks:
            self._chunks.put(chunk.chunk_id, chunk)

    def all_chunks(self) -> list[Chunk]:
        return self._chunks.values()


__all__ = ["CHUNKS", "SOURCES", "KnowledgeRepository", "StoredKnowledgeRepository"]
