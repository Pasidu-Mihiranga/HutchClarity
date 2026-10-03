"""The review workflow, and the labelling that makes it safe (AU01, #13).

Plan 02 section 3.3. The pipeline proposes clusters; this is what a person does
with them, and what callers are allowed to say about one before they have.

**A hypothesis shown as a finding is the failure this guards against.** A
cluster is a machine's guess that forty complaints share one cause. Shown to a
CX engineer labelled as a hypothesis it is useful; shown without that label it
is a finding nobody established, and I16 forbids presenting inferred as
measured. So `staff_view` is the only sanctioned way to put a cluster in front
of a person, and it always carries the label: a caller cannot forget, because
there is nothing to forget.

**The verdict is a record, not a mutation.** The first version of `confirm`
wrote the reviewer's name into the cluster's **label**:

    cluster.label = f"{cluster.label} (reviewed by {reviewer})"

which put audit data in a display string, appended twice if it ran twice, and
kept no time, no note and nothing to look up. A review is evidence about who
decided what and when, so it is its own record.

**A reviewed cluster is not re-reviewed silently.** A second verdict overwrites
the first, and the first was somebody's professional judgement. Changing one
takes `supersede`, which keeps both.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id
from clarity.modules.autopsy.pipeline import Cluster, ClusterStatus

#: What every staff-facing representation of an unreviewed cluster says.
#:
#: A constant rather than a string at each call site, so the wording cannot
#: drift between the API, the console and a batch report, and so a test can
#: assert the exact text reached the surface.
HYPOTHESIS_LABEL = "hypothesis: not reviewed by a person"

#: What a confirmed cluster says. Still not a published change: a confirmed
#: cluster is a cause a person agreed with, and turning that into a rule goes
#: through the policy lifecycle (plan 20).
CONFIRMED_LABEL = "confirmed by a reviewer: not yet a published rule"

REJECTED_LABEL = "rejected by a reviewer"

_STATUS_LABELS: dict[ClusterStatus, str] = {
    ClusterStatus.HYPOTHESIS: HYPOTHESIS_LABEL,
    ClusterStatus.CONFIRMED: CONFIRMED_LABEL,
    ClusterStatus.REJECTED: REJECTED_LABEL,
}


class ReviewRefused(ValueError):
    """The review cannot be recorded as asked."""


@dataclass(frozen=True)
class ClusterReview:
    """One person's verdict on one cluster.

    Immutable and keeps its own id, because this is the audit record for a
    judgement: a reviewer should be able to point at it later and a second
    verdict must not be able to erase it.
    """

    review_id: str
    cluster_id: str
    reviewer: str
    accepted: bool
    at: datetime
    note: str = ""
    supersedes: str | None = None
    """The review this one replaces, when a verdict was deliberately changed."""

    @property
    def verdict(self) -> ClusterStatus:
        return ClusterStatus.CONFIRMED if self.accepted else ClusterStatus.REJECTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "cluster_id": self.cluster_id,
            "reviewer": self.reviewer,
            "accepted": self.accepted,
            "at": self.at.isoformat(),
            "note": self.note,
            "supersedes": self.supersedes,
        }


@dataclass
class ReviewedCluster:
    """A cluster together with the review history behind its status.

    The history is a list rather than a single record, so a changed verdict
    keeps the one it changed. Nothing here deletes.
    """

    cluster: Cluster
    reviews: list[ClusterReview] = field(default_factory=list)

    @property
    def status(self) -> ClusterStatus:
        return self.cluster.status

    @property
    def latest(self) -> ClusterReview | None:
        return self.reviews[-1] if self.reviews else None

    @property
    def reviewed(self) -> bool:
        return self.cluster.status is not ClusterStatus.HYPOTHESIS


class ClusterReviews:
    """Records verdicts on clusters.

    Takes an injected clock (I11): a review's timestamp is evidence about when
    somebody decided something, and a replayed run has to produce the same one.
    """

    def __init__(self, *, clock: Callable[[], datetime] = utc_now) -> None:
        self._clock = clock

    def record(
        self,
        held: ReviewedCluster,
        *,
        reviewer: str,
        accept: bool,
        note: str = "",
    ) -> ReviewedCluster:
        """Record a first verdict on a cluster.

        Refuses a cluster that already has one. A second `record` would
        overwrite a professional judgement with no trace of the first, and the
        caller who wants that has to say so through `supersede`.
        """
        if not reviewer.strip():
            raise ReviewRefused(
                "a review needs a reviewer: an anonymous verdict is not an audit record"
            )
        if held.reviewed:
            raise ReviewRefused(
                f"{held.cluster.cluster_id} was already reviewed by "
                f"{held.latest.reviewer if held.latest else 'someone'}; "
                "use supersede to change a verdict, which keeps both"
            )
        return self._apply(held, reviewer=reviewer, accept=accept, note=note, supersedes=None)

    def supersede(
        self,
        held: ReviewedCluster,
        *,
        reviewer: str,
        accept: bool,
        note: str,
    ) -> ReviewedCluster:
        """Deliberately change a verdict, keeping the one it replaced.

        A note is required here and optional on a first review: changing
        somebody else's decision is the case where the reason matters most, and
        an unexplained reversal is the thing an auditor will ask about.
        """
        if not held.reviewed or held.latest is None:
            raise ReviewRefused(
                f"{held.cluster.cluster_id} has no verdict to supersede; use record"
            )
        if not note.strip():
            raise ReviewRefused("superseding a verdict needs a reason")
        return self._apply(
            held,
            reviewer=reviewer,
            accept=accept,
            note=note,
            supersedes=held.latest.review_id,
        )

    def _apply(
        self,
        held: ReviewedCluster,
        *,
        reviewer: str,
        accept: bool,
        note: str,
        supersedes: str | None,
    ) -> ReviewedCluster:
        review = ClusterReview(
            review_id=new_id("REV"),
            cluster_id=held.cluster.cluster_id,
            reviewer=reviewer.strip(),
            accepted=accept,
            at=self._clock(),
            note=note.strip(),
            supersedes=supersedes,
        )
        # `replace` rather than assignment: the label is display text and the
        # status is the fact, and the first version of this conflated them by
        # writing the reviewer's name into the label.
        return ReviewedCluster(
            cluster=replace(held.cluster, status=review.verdict),
            reviews=[*held.reviews, review],
        )


def staff_view(held: ReviewedCluster) -> dict[str, Any]:
    """The only sanctioned way to show a cluster to a person (acceptance 1).

    Always carries `hypothesis` and `label`, so an unreviewed cluster cannot
    reach a screen without saying that nobody has checked it. A caller that
    built this dict by hand could omit the label; there is one function so that
    there is one thing to get right.

    `suggested_rule_id` travels with `suggested_rule_is_a_guess`, because a
    rule id beside a cluster reads as "this is caused by that" and, on an
    unreviewed cluster, nothing has established it.
    """
    cluster = held.cluster
    unreviewed = cluster.status is ClusterStatus.HYPOTHESIS
    return {
        "cluster_id": cluster.cluster_id,
        "label": cluster.label,
        "size": cluster.size,
        "status": cluster.status.value,
        # The three fields a surface cannot render without.
        "hypothesis": unreviewed,
        "status_label": _STATUS_LABELS[cluster.status],
        # Nothing in this module acts on a cluster. A confirmed cause becomes
        # a rule only through the policy lifecycle (plan 20), so a surface can
        # state this flatly rather than implying a change has been made.
        "acted_on": False,
        "keywords": list(cluster.keywords),
        "languages": dict(cluster.languages),
        "suggested_rule_id": cluster.suggested_rule_id,
        "suggested_rule_is_a_guess": unreviewed,
        "reviews": [review.to_dict() for review in held.reviews],
        "reviewed_by": held.latest.reviewer if held.latest else None,
        "reviewed_at": held.latest.at.isoformat() if held.latest else None,
    }


__all__ = [
    "CONFIRMED_LABEL",
    "HYPOTHESIS_LABEL",
    "REJECTED_LABEL",
    "ClusterReview",
    "ClusterReviews",
    "ReviewRefused",
    "ReviewedCluster",
    "staff_view",
]
