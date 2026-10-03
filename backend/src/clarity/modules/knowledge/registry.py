"""The source registry: publish governed content, read back what applied then.

K01 (#31), plan 22 section 7 and plan 20 kind K2.

The registry owns two decisions, and both are refusals rather than fallbacks.

**Two versions may not claim the same instant.** "Old versions stay retrievable
for what applied then" only means something if exactly one version was in force
at any given moment. Publishing a version whose window overlaps a sibling's is
refused, because the alternative is retrieval picking one by a tie-break and a
"what applied in March" answer depending on which record was written first.
``supersede`` is the ergonomic path: it closes the current version at the
successor's start, so the common case needs no bookkeeping and still leaves no
gap and no overlap.

**Audience is filtered on read, by the reader's own audience.** A staff SOP is
never returned to a customer reader, and that is enforced here rather than left
to a caller remembering to pass a filter: ``chunks_as_of`` requires the
audience argument, so there is no call that forgets it (I9, deny by default).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime

from clarity.contracts.events import KnowledgePublishedV1
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import Language, utc_now
from clarity.modules.knowledge.ingest import ingest
from clarity.modules.knowledge.repository import (
    CHUNKS,
    SOURCES,
    KnowledgeRepository,
    StoredKnowledgeRepository,
)
from clarity.modules.knowledge.sources import Audience, Chunk, KnowledgeSource
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    UnitOfWork,
    UnitOfWorkFactory,
)


class PublicationRefused(ValueError):
    """The registry will not publish this source version."""


class KnowledgeRegistry:
    """Publishes source versions and reads chunks back as of a moment.

    Owns its units of work rather than taking a bound repository, because
    publishing is a read-modify-write: the overlap check and the save have to
    see the same state or two concurrent publications could both pass the
    check. The lock covers the gap within a process and the unit of work covers
    it across them.
    """

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        supplied_unit = open_unit
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit
        self._clock = clock
        self._lock = threading.Lock()
        # The default in-memory store has no outbox table, so a registry built
        # without one (a test, a script) records no events. Not a silent
        # downgrade: the flag is set only when the caller supplied no unit of
        # work factory at all, so a real deployment always announces.
        self._events_disabled = supplied_unit is None

    @staticmethod
    def _repository_for(unit: UnitOfWork) -> KnowledgeRepository:
        return StoredKnowledgeRepository(unit.repository(SOURCES), unit.repository(CHUNKS))

    # -- publishing ------------------------------------------------------- #

    def publish(self, source: KnowledgeSource) -> tuple[Chunk, ...]:
        """Ingest and store one source version.

        Refuses a duplicate ``(source_id, version)`` and refuses a window that
        overlaps a sibling version. Ingestion runs first, so a source whose
        text cannot be chunked or whose declared language contradicts its
        script never reaches the store.
        """
        with self._lock, self._open_unit() as unit:
            repository = self._repository_for(unit)
            chunks = self._publish_in(repository, source)
            self._announce(unit, repository, source, len(chunks))
            unit.commit()
        return chunks

    def supersede(self, source: KnowledgeSource) -> tuple[Chunk, ...]:
        """Publish *source*, closing whatever it replaces at its start date.

        The governed path for a new version of existing content: the previous
        version keeps its text and its history and gains an end date, so it is
        still retrievable for the period it covered.

        One unit of work for both halves. A crash between closing the
        predecessor and publishing the successor would otherwise leave a period
        covered by nothing, and a question about that period would get silence
        instead of the text that was really in force.
        """
        with self._lock, self._open_unit() as unit:
            repository = self._repository_for(unit)
            predecessor = _in_force(repository.versions(source.source_id), source.effective_from)
            if predecessor is not None and predecessor.version != source.version:
                closed = predecessor.model_copy(update={"effective_to": source.effective_from})
                repository.save_source(closed)
                repository.replace_chunks(closed.source_id, closed.version, ingest(closed))
            chunks = self._publish_in(repository, source)
            self._announce(unit, repository, source, len(chunks))
            unit.commit()
        return chunks

    def _announce(
        self,
        unit: UnitOfWork,
        repository: KnowledgeRepository,
        source: KnowledgeSource,
        chunk_count: int,
    ) -> None:
        """Record `knowledge.published` in the same unit as the write (I7).

        Through the outbox, so the event and the state change commit together:
        an event announcing a publication that rolled back is a lie, and a
        publication nobody was told about leaves a cache serving the old text.

        Carries the source's identity and window, never its text. An event is
        a notification that something changed, and copying a clause into the
        bus would put governed content somewhere nobody owns its version.
        """
        if self._events_disabled:
            return
        outbox_in(unit).append(
            Event.of(
                KnowledgePublishedV1(
                    source_id=source.source_id,
                    source_version=source.version,
                    kind=source.kind.value,
                    owner=source.owner,
                    audience=source.audience.value,
                    language=source.language.value,
                    effective_from=source.effective_from,
                    effective_to=source.effective_to,
                    chunk_count=chunk_count,
                    corpus_version=_fingerprint(repository.all_sources()),
                ),
                # The subject is the source, not a subscriber: governed content
                # has no customer, and partitioning by source keeps a busy
                # source's publications in order.
                subject=source.source_id,
            )
        )

    @staticmethod
    def _publish_in(repository: KnowledgeRepository, source: KnowledgeSource) -> tuple[Chunk, ...]:
        existing = repository.versions(source.source_id)
        if any(other.version == source.version for other in existing):
            raise PublicationRefused(
                f"{source.ref} is already published; a correction is a new version, "
                "because the old one may already have been cited"
            )
        clashing = [other for other in existing if source.overlaps(other)]
        if clashing:
            raise PublicationRefused(
                f"{source.ref} is in force at the same time as "
                f"{', '.join(other.ref for other in clashing)}; close the previous version "
                "or use supersede, so that 'what applied then' has one answer"
            )

        chunks = ingest(source)
        repository.save_source(source)
        repository.replace_chunks(source.source_id, source.version, chunks)
        return chunks

    # -- reading ---------------------------------------------------------- #

    def source_as_of(self, source_id: str, moment: datetime) -> KnowledgeSource | None:
        """The one version of *source_id* in force at *moment*."""
        with self._open_unit() as unit:
            return _in_force(self._repository_for(unit).versions(source_id), moment)

    def versions(self, source_id: str) -> list[KnowledgeSource]:
        """Every version of one source, oldest first. The audit view."""
        with self._open_unit() as unit:
            found = self._repository_for(unit).versions(source_id)
        return sorted(found, key=lambda version: version.version)

    def chunks_as_of(
        self,
        moment: datetime | None = None,
        *,
        audience: Audience,
        language: Language | None = None,
        product_ids: Sequence[str] = (),
    ) -> list[Chunk]:
        """Every chunk a reader of *audience* may see, in force at *moment*.

        This is the filter half of retrieval; K02 adds the ranking. It is
        deliberately a filter and not a search: an effective-date or audience
        mistake is a disclosure or a wrong answer about the law, so it is
        decided here on metadata rather than anywhere near a score.

        ``audience`` is keyword-only and required. ``language`` and
        ``product_ids`` narrow when given and are ignored when not, because a
        query with no product in the case should still find general policy.
        """
        at = moment if moment is not None else self._clock()
        wanted = set(product_ids)
        with self._open_unit() as unit:
            candidates = self._repository_for(unit).all_chunks()
        return [
            chunk
            for chunk in candidates
            if chunk.effective_at(at)
            and chunk.readable_by(audience)
            and (language is None or chunk.language is language)
            and (not wanted or not chunk.product_ids or wanted & set(chunk.product_ids))
        ]

    def sources(self) -> list[KnowledgeSource]:
        with self._open_unit() as unit:
            return self._repository_for(unit).all_sources()

    def corpus_version(self) -> str:
        """A fingerprint of everything published, for cache keying.

        Changes whenever any source version is added or its window is changed,
        which is what makes a cached answer composed from superseded text
        unreachable rather than merely invalidated. See `cache.py`.
        """
        with self._open_unit() as unit:
            return _fingerprint(self._repository_for(unit).all_sources())


def _fingerprint(sources: Sequence[KnowledgeSource]) -> str:
    """A stable hash of every published version and its window.

    Sorted, so two replicas that stored the same sources in a different order
    agree. The window is included because closing a version changes what is in
    force without adding one, and a cache keyed only on the set of refs would
    not notice.
    """
    refs = sorted(
        (
            source.source_id,
            source.version,
            source.effective_from.isoformat(),
            source.effective_to.isoformat() if source.effective_to else "",
        )
        for source in sources
    )
    return hash_payload({"corpus": refs})


def _in_force(versions: Sequence[KnowledgeSource], moment: datetime) -> KnowledgeSource | None:
    """The one version in force at *moment*, or ``None``.

    `publish` refuses overlaps, so at most one qualifies. Taking the highest
    version rather than the first found means a store that somehow holds an
    overlap returns the later text instead of an arbitrary one.
    """
    in_force = [version for version in versions if version.effective_at(moment)]
    if not in_force:
        return None
    return sorted(in_force, key=lambda version: version.version)[-1]


def publish_all(registry: KnowledgeRegistry, sources: Iterable[KnowledgeSource]) -> list[Chunk]:
    """Publish a batch, in the order given. Used by the seed and by tests."""
    chunks: list[Chunk] = []
    for source in sources:
        chunks.extend(registry.publish(source))
    return chunks


__all__ = ["KnowledgeRegistry", "PublicationRefused", "publish_all"]
