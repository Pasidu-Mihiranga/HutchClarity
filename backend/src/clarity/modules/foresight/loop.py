"""Closing the loop: what the clusters say a launch actually did (C7/F10).

Foresight predicts; `autopsy` finds out. Until C7 the two never met, so a
rehearsal could be wrong forever without anybody noticing, and the calibration
gate had no source of evidence other than somebody typing one in.

**Foresight stays a leaf.** It does not import `autopsy` and never will. The
port is declared here and the composition root supplies a driver, exactly as
`AutopsyService(source=_complaint_source())` already does. That is not
squeamishness about an import: a synchronous dependency between two L4 modules
has to be declared in `tests/architecture/test_module_dependencies.py`, plan 21
section 11.2, `docs/modules.md`, `ARCHITECTURE.md` and both `MODULE.md` files,
and it would make foresight unable to run as the batch job plan 21 moves it to.
A container-wired port costs none of that (ADR-0029: calls for answers, events
for side effects).

**A cluster never becomes calibration evidence on its own.** This is the part
worth being careful about. A confirmed cluster is a real observation, but it is
an observation about complaints, not about a theme in a segment: turning
"cluster CL-7 has 40 members" into "the `data stopped at cap` theme was HIGH for
students" is an act of interpretation. So a `cluster.updated` event produces an
:class:`OutcomeCandidate`, and a candidate is inert. A named person reads it,
decides what it means, and records the outcome under their own name. The gate
opens on that, never on the candidate (ADR-0044).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from clarity.contracts.events import ClusterUpdatedV1
from clarity.kernel.ids import new_id
from clarity.modules.foresight.records import RecordedOutcome, StoredLaunch
from clarity.modules.foresight.simulation import ForesightReport, VolumeBand
from clarity.platform.messaging.envelope import Event, EventType
from clarity.platform.persistence import Repository, UnitOfWorkFactory

#: Cluster-derived suggestions, inert until a person confirms one.
#:
#: **Deliberately not append-only**, and it is the second collection in this
#: module that is not. A candidate has exactly one legitimate transition,
#: unconfirmed to confirmed, in the same way `foresight.runs` moves through its
#: status. The evidence a confirmation produces is a `RecordedOutcome`, and
#: *that* is append-only; this row is the note saying somebody looked.
#:
#: The alternative considered and rejected was making it append-only and
#: confirming through `UnitOfWork.as_custodian`. That span is the named
#: exception for restoring a backup and sealing an audit segment (ADR-0038,
#: ADR-0039); spending it on a product note would make it mean nothing.
CANDIDATES = "foresight.candidates"


@dataclass(frozen=True)
class ClusterRate:
    """How many complaints a cluster holds, as the complaint side sees it.

    `cluster_id` and `rule_id` are codes. There is no label here for the same
    reason the event has none: a label is derived from what customers wrote.
    """

    cluster_id: str
    size: int
    status: str
    rule_id: str | None = None


class ClusterRateSource(Protocol):
    """Where foresight reads observed cluster sizes from.

    Declared in foresight and implemented in the composition root, so foresight
    neither imports `autopsy` nor reads its tables (I6).
    """

    def rates(self) -> tuple[ClusterRate, ...]:
        """Every cluster the complaint side currently holds."""
        ...


@dataclass(frozen=True)
class OutcomeCandidate:
    """A cluster that might be evidence about a launch. Inert until confirmed.

    It carries no theme and no segment, and that absence is the design. A
    cluster says "these complaints look like one cause"; it does not say which
    rehearsed theme it corresponds to or which segment complained. Somebody has
    to decide that, and :meth:`AutopsyLoop.confirm` is where they say so under
    their own name.
    """

    candidate_id: str
    cluster_id: str
    status: str
    size: int
    noticed_at: datetime
    rule_id: str | None = None
    reviewed_by: str | None = None
    """Who ruled on the cluster, in autopsy. Not who confirmed it here."""
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    outcome_id: str | None = None
    """The :class:`RecordedOutcome` a person made from it, once they have."""

    @property
    def is_confirmed(self) -> bool:
        return self.outcome_id is not None


@dataclass(frozen=True)
class PairOutcome:
    """One predicted theme-segment pair, beside what was actually recorded."""

    theme: str
    segment: str
    predicted: VolumeBand
    observed: VolumeBand | None
    """``None`` when nothing was recorded for this pair.

    Not a LOW observation. Absence of a record is absence of a record, and the
    backtest already refuses to average it in; the comparison says the same
    thing in the shape a person reads.
    """

    @property
    def agrees(self) -> bool | None:
        return None if self.observed is None else self.predicted is self.observed


@dataclass(frozen=True)
class PostLaunchComparison:
    """What a rehearsal said, beside what the launch produced.

    The point of the whole workstream, and the thing that makes a backtest more
    than an exercise: somebody can look at one launch and see where the method
    was right and where it was not.
    """

    launch_id: str
    scenario_version_id: str
    provenance: str
    pairs: tuple[PairOutcome, ...]
    unpredicted: tuple[tuple[str, str], ...]
    """Observed theme-segment pairs the rehearsal never predicted."""
    cluster_rates: tuple[ClusterRate, ...] = ()
    """What the complaint side currently holds, as context rather than as score.

    Clusters are not keyed by theme or segment, so they cannot be scored against
    a prediction. They are here because a reader asking "was this launch noisy"
    should not have to open another screen to find out.
    """
    caveats: tuple[str, ...] = ()

    @property
    def compared(self) -> int:
        return sum(1 for pair in self.pairs if pair.observed is not None)

    @property
    def agreement_rate(self) -> Decimal | None:
        """``None`` when nothing was comparable, never ``0`` or ``1``."""
        comparable = [pair for pair in self.pairs if pair.agrees is not None]
        if not comparable:
            return None
        agreed = sum(1 for pair in comparable if pair.agrees)
        return (Decimal(agreed) / Decimal(len(comparable))).quantize(Decimal("0.001"))


_CAVEATS = (
    "A cluster-derived candidate is not an outcome. It becomes evidence only "
    "when a named person says what it means and records it (ADR-0044).",
    "Absence of a recorded outcome for a predicted pair is absence of a record, "
    "not a LOW observation.",
    "Cluster sizes are counts of complaint records, not of people: one person "
    "complaining four times is four.",
)


class AutopsyLoop:
    """Turns `cluster.updated` into candidates, and compares a launch afterwards."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory,
        clusters: ClusterRateSource | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._open_unit = open_unit
        self._clusters = clusters
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    # -- the inbound half --------------------------------------------------- #

    def on_cluster_updated(self, event: Event) -> None:
        """Notice a cluster. Writes a candidate; decides nothing.

        Idempotent on the cluster id (I7): a cluster re-reviewed twice is one
        candidate, and a replayed event changes nothing. The candidate is
        **not** updated in place when the cluster changes again, because it is
        append-only and because a person may already have confirmed it; the
        later state is readable from autopsy.
        """
        payload = event.payload()
        if not isinstance(payload, ClusterUpdatedV1):
            return
        with self._open_unit() as unit:
            candidates: Repository[str, OutcomeCandidate] = unit.repository(CANDIDATES)
            if candidates.get(payload.cluster_id) is not None:
                return
            candidates.put(
                payload.cluster_id,
                OutcomeCandidate(
                    candidate_id=new_id("CAN"),
                    cluster_id=payload.cluster_id,
                    status=payload.status,
                    size=payload.size,
                    noticed_at=event.time,
                    rule_id=payload.suggested_rule_id,
                    reviewed_by=payload.reviewed_by,
                ),
            )
            unit.commit()

    def candidates(self) -> list[OutcomeCandidate]:
        with self._open_unit() as unit:
            repository: Repository[str, OutcomeCandidate] = unit.repository(CANDIDATES)
            return repository.values()

    def candidate(self, cluster_id: str) -> OutcomeCandidate | None:
        with self._open_unit() as unit:
            repository: Repository[str, OutcomeCandidate] = unit.repository(CANDIDATES)
            return repository.get(cluster_id)

    def mark_confirmed(
        self, cluster_id: str, *, outcome: RecordedOutcome, by: str
    ) -> OutcomeCandidate:
        """Record that a person turned this candidate into an outcome.

        Takes the outcome rather than making one: the service owns the
        append-only outcome write, and this records who decided and when.
        """
        with self._open_unit() as unit:
            repository: Repository[str, OutcomeCandidate] = unit.repository(CANDIDATES)
            found = repository.get(cluster_id)
            if found is None:
                raise KeyError(cluster_id)
            confirmed = replace(
                found,
                confirmed_by=by,
                confirmed_at=self._clock(),
                outcome_id=outcome.outcome_id,
            )
            repository.put(cluster_id, confirmed)
            unit.commit()
        return confirmed

    # -- the outbound half -------------------------------------------------- #

    def compare(
        self,
        *,
        launch: StoredLaunch,
        report: ForesightReport | None,
        outcomes: list[RecordedOutcome],
    ) -> PostLaunchComparison:
        """What the rehearsal said, beside what was recorded afterwards."""
        observed = {(o.theme, o.segment): o.band for o in outcomes}
        predicted = {} if report is None else {(p.theme, p.segment): p for p in report.predictions}

        pairs = tuple(
            PairOutcome(
                theme=theme,
                segment=segment,
                predicted=prediction.band,
                observed=observed.get((theme, segment)),
            )
            for (theme, segment), prediction in sorted(predicted.items())
        )
        return PostLaunchComparison(
            launch_id=launch.launch_id,
            scenario_version_id=launch.scenario_version_id,
            provenance=launch.provenance.value,
            pairs=pairs,
            unpredicted=tuple(sorted(set(observed) - set(predicted))),
            cluster_rates=self._rates(),
            caveats=_CAVEATS,
        )

    def _rates(self) -> tuple[ClusterRate, ...]:
        """The complaint side's current clusters, or nothing.

        A source that is not wired or that fails leaves the context empty rather
        than failing the comparison: the predicted-versus-actual part stands on
        its own, and losing the whole screen because a side panel could not load
        would be the wrong trade.
        """
        if self._clusters is None:
            return ()
        try:
            return self._clusters.rates()
        except Exception:
            return ()


CONSUMED_EVENTS = (EventType.CLUSTER_UPDATED,)


__all__ = [
    "CANDIDATES",
    "CONSUMED_EVENTS",
    "AutopsyLoop",
    "ClusterRate",
    "ClusterRateSource",
    "OutcomeCandidate",
    "PairOutcome",
    "PostLaunchComparison",
]
