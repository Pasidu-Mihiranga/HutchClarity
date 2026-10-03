"""Autopsy as a running service, fed by events (AU01, #13; plan 02 section 3.3).

Before AU01 the pipeline ran as a batch over demo data when somebody asked a
demo route for it, and the clusters it produced died with the request. This is
the same pipeline, fed by `complaint.created`, with the clusters and their
reviews kept.

**The event carries no complaint text, and that is deliberate.**
`ComplaintCreatedV1` holds a `complaint_id`, a channel, a language and a case
id. Putting the customer's words in the message bus would copy complaint
content into a place nobody owns its retention, which is the same reason
`conversation.turn.completed` carries no message text and `knowledge.published`
carries no clause text.

So the consumer is a notification handler, not a data handler: it takes the id
and fetches the text from whoever owns complaints, through the `ComplaintSource`
seam the composition root fills. Nothing in this module reaches for a store it
does not own (I6).

**Clustering happens on a re-run, not per complaint.** One complaint is not a
cluster and cannot be: a cluster is a claim that several complaints share a
cause, so the arrival of one changes the answer for all of them. The consumer
therefore masks and keeps each complaint as it arrives, and `rerun` redraws the
hypotheses over everything kept. That is what makes the batch packaging and the
event feed the same code path rather than two implementations that drift.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from clarity.ai.pii import ForbiddenContent
from clarity.contracts.events import ComplaintCreatedV1
from clarity.kernel.common import utc_now
from clarity.modules.autopsy.pipeline import (
    AutopsyReport,
    Complaint,
    ComplaintAutopsy,
)
from clarity.modules.autopsy.repository import (
    CLUSTERS,
    COMPLAINTS,
    AutopsyRepository,
    StoredAutopsyRepository,
)
from clarity.modules.autopsy.review import (
    ClusterReviews,
    ReviewedCluster,
    ReviewRefused,
    staff_view,
)
from clarity.platform.messaging.envelope import Event
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    UnitOfWork,
    UnitOfWorkFactory,
)


class ComplaintSource(Protocol):
    """Where the text of a complaint comes from.

    The event does not carry it (see the module docstring), so this is the seam
    the composition root fills with whichever system owns complaints. Returning
    ``None`` is normal: a complaint may have been deleted, or may not have
    reached the store the relay is reading yet, and neither is this module's
    problem to solve.
    """

    def text_for(self, complaint_id: str) -> str | None: ...


@dataclass(frozen=True)
class Intake:
    """What became of one complaint arriving. For the log and for tests."""

    complaint_id: str
    stored: bool
    reason: str = ""

    @property
    def refused(self) -> bool:
        return not self.stored and self.reason == "forbidden_content"


class AutopsyService:
    """Keeps masked complaints as they arrive, and redraws clusters on demand."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory | None = None,
        autopsy: ComplaintAutopsy | None = None,
        reviews: ClusterReviews | None = None,
        source: ComplaintSource | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit
        self._autopsy = autopsy or ComplaintAutopsy()
        self._reviews = reviews or ClusterReviews(clock=clock)
        self._source = source
        self._clock = clock

    @staticmethod
    def _repository(unit: UnitOfWork) -> AutopsyRepository:
        return StoredAutopsyRepository(unit.repository(COMPLAINTS), unit.repository(CLUSTERS))

    # -- the consumer ----------------------------------------------------- #

    def on_complaint_created(self, event: Event) -> None:
        """Consume `complaint.created`. Idempotent, because consumers must be (I7)."""
        payload = event.payload()
        if not isinstance(payload, ComplaintCreatedV1):
            return
        self.accept(payload.complaint_id, channel=payload.channel.value)

    def accept(
        self,
        complaint_id: str,
        *,
        channel: str = "whatsapp",
        text: str | None = None,
    ) -> Intake:
        """Mask one complaint and keep it. The unit of clustering is the re-run.

        Masking happens here and the masked form is what is stored, so no raw
        complaint text ever reaches the repository (I13). A complaint quoting a
        credential is dropped entirely rather than masked, which is the
        pipeline's existing rule and the right one: a message containing a PIN
        is not evidence about a billing pattern.

        ``text`` is for a caller that already holds it and has no store to be
        fetched from, which is the seeded demo path and nothing else. **The
        event path never supplies it**: `on_complaint_created` passes the id
        alone, so the "text comes from whoever owns complaints" rule still
        holds where it matters.
        """
        if text is None and self._source is None:
            return Intake(complaint_id=complaint_id, stored=False, reason="no_source")
        if text is None and self._source is not None:
            text = self._source.text_for(complaint_id)
        if not text:
            # Not an error. The complaint may not have reached the store the
            # relay reads yet, and a redelivery will find it (at least once).
            return Intake(complaint_id=complaint_id, stored=False, reason="no_text")

        try:
            cleaned, _duplicates, refused = self._autopsy.clean(
                [Complaint(complaint_id=complaint_id, text=text, channel=channel)]
            )
        except ForbiddenContent:
            return Intake(complaint_id=complaint_id, stored=False, reason="forbidden_content")
        if refused or not cleaned:
            return Intake(complaint_id=complaint_id, stored=False, reason="forbidden_content")

        with self._open_unit() as unit:
            # `put` by complaint id, so a redelivered event overwrites rather
            # than adding a second copy of the same complaint and inflating a
            # cluster. That is what makes this consumer idempotent (I7).
            self._repository(unit).save_complaint(cleaned[0])
            unit.commit()
        return Intake(complaint_id=complaint_id, stored=True)

    # -- the batch -------------------------------------------------------- #

    def rerun(self) -> AutopsyReport:
        """Redraw the hypotheses over every complaint kept.

        The packaging for the serverless batch job (plan 02 section 3.3) and
        the thing an operator runs after a spike. One code path, so the batch
        and the event feed cannot drift.

        Unreviewed clusters from the previous run are dropped and reviewed ones
        are kept: a re-run may not discard somebody's recorded judgement, and
        leaving the old hypotheses would show a reviewer two overlapping
        guesses about the same complaints.
        """
        with self._open_unit() as unit:
            repository = self._repository(unit)
            kept = repository.all_complaints()
            repository.drop_unreviewed_clusters()
            report = self._autopsy.recluster(kept)
            reviewed = {held.cluster.cluster_id: held for held in repository.all_clusters()}
            for cluster in report.clusters:
                if cluster.cluster_id not in reviewed:
                    repository.save_cluster(ReviewedCluster(cluster=cluster))
            unit.commit()
        return report

    # -- the review surface ---------------------------------------------- #

    def clusters(self) -> list[ReviewedCluster]:
        with self._open_unit() as unit:
            return self._repository(unit).all_clusters()

    def for_staff(self) -> list[dict[str, Any]]:
        """Every cluster, as a person may be shown it (AU01 acceptance 1).

        Goes through `staff_view`, so an unreviewed cluster cannot reach a
        screen without saying that nobody has checked it.
        """
        return [staff_view(held) for held in self.clusters()]

    def review(
        self,
        cluster_id: str,
        *,
        reviewer: str,
        accept: bool,
        note: str = "",
        supersede: bool = False,
    ) -> ReviewedCluster:
        """Record a verdict, and keep it."""
        with self._open_unit() as unit:
            repository = self._repository(unit)
            held = repository.cluster(cluster_id)
            if held is None:
                raise ReviewRefused(f"no cluster {cluster_id}")
            updated = (
                self._reviews.supersede(held, reviewer=reviewer, accept=accept, note=note)
                if supersede
                else self._reviews.record(held, reviewer=reviewer, accept=accept, note=note)
            )
            repository.save_cluster(updated)
            unit.commit()
        return updated


__all__ = ["AutopsyService", "ComplaintSource", "Intake"]
