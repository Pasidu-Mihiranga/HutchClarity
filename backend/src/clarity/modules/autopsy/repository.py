"""Where autopsy keeps complaints and clusters (AU01, #13; B02, ADR-0013).

**Only masked complaints are stored.** The pipeline masks before anything else
reads a complaint (I13), and what reaches this repository is the
`CleanComplaint`, never the raw text. A store of raw customer complaints is a
store of customer words, and autopsy exists to find patterns across them rather
than to keep them. A complaint that quoted a credential is refused by the
pipeline and never arrives here at all.

Clusters are stored with their review history, because a verdict is a person's
professional judgement and has to survive the process that recorded it. Before
AU01 a cluster lived in a report object that died with the request, so a review
was lost the moment it was given.
"""

from __future__ import annotations

from typing import Protocol

from clarity.modules.autopsy.pipeline import CleanComplaint
from clarity.modules.autopsy.review import ReviewedCluster
from clarity.platform.persistence import Repository

#: One collection is one table in B05.
COMPLAINTS = "autopsy.complaints"
CLUSTERS = "autopsy.clusters"


class AutopsyRepository(Protocol):
    """Masked complaints, and the clusters drawn from them."""

    def save_complaint(self, complaint: CleanComplaint) -> None: ...

    def complaint(self, complaint_id: str) -> CleanComplaint | None: ...

    def all_complaints(self) -> list[CleanComplaint]: ...

    def save_cluster(self, held: ReviewedCluster) -> None: ...

    def cluster(self, cluster_id: str) -> ReviewedCluster | None: ...

    def all_clusters(self) -> list[ReviewedCluster]: ...

    def drop_unreviewed_clusters(self) -> int:
        """Remove clusters nobody has ruled on. Returns how many went.

        A re-run redraws the hypotheses, and keeping the previous run's
        would leave a reviewer looking at two overlapping guesses about the
        same complaints. A **reviewed** cluster is never dropped: that is
        somebody's recorded judgement and a re-run does not get to discard it.
        """
        ...


class StoredAutopsyRepository:
    """``AutopsyRepository`` over any persistence driver."""

    def __init__(
        self,
        complaints: Repository[str, CleanComplaint],
        clusters: Repository[str, ReviewedCluster],
    ) -> None:
        self._complaints = complaints
        self._clusters = clusters

    def save_complaint(self, complaint: CleanComplaint) -> None:
        self._complaints.put(complaint.complaint_id, complaint)

    def complaint(self, complaint_id: str) -> CleanComplaint | None:
        return self._complaints.get(complaint_id)

    def all_complaints(self) -> list[CleanComplaint]:
        return self._complaints.values()

    def save_cluster(self, held: ReviewedCluster) -> None:
        self._clusters.put(held.cluster.cluster_id, held)

    def cluster(self, cluster_id: str) -> ReviewedCluster | None:
        return self._clusters.get(cluster_id)

    def all_clusters(self) -> list[ReviewedCluster]:
        return self._clusters.values()

    def drop_unreviewed_clusters(self) -> int:
        dropped = 0
        for held in self._clusters.values():
            if not held.reviewed:
                self._clusters.delete(held.cluster.cluster_id)
                dropped += 1
        return dropped


__all__ = ["CLUSTERS", "COMPLAINTS", "AutopsyRepository", "StoredAutopsyRepository"]
