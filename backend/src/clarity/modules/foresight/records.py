"""What foresight stores (C2/F05).

Before C2 a foresight run was built, returned and discarded. Nothing could be
cited later, no two people could look at the same rehearsal, and the calibration
gate had nowhere to keep the evidence it is supposed to open on. These are the
records that fix that.

Four shapes of thing are kept, and the difference between them is what decides
which collection is append-only:

1. **What somebody asked for.** A :class:`ScenarioVersion` is a frozen scenario
   with an author and a version number. A change is a new version, never an
   edit, so a run that cites version 2 still means what it meant.
2. **What the system did about it.** A :class:`ScenarioRun` is the only record
   here that changes: it moves queued to running to succeeded or failed, which
   is what C4's ``202`` and poll URL are made of.
3. **What came out.** A :class:`StoredReport` and a :class:`StoredCalibration`
   are outputs. They are written once and never touched again.
4. **What actually happened.** A :class:`StoredLaunch` and its
   :class:`RecordedOutcome` rows are the evidence the gate reads. These are the
   records somebody would have to rewrite to make an uncalibrated engine look
   calibrated, which is exactly why they are append-only.

**Two identifiers, deliberately.** ``ScenarioRun.run_id`` is the *job*: what a
caller polls. ``ForesightReport.run_id`` is the engine's own identifier for one
computation, and it is carried here as ``StoredReport.report_id``. They are
different things and a reader who conflates them will look for a report under a
job id and not find one.

**Nothing here is customer-scoped**, by construction rather than by omission.
Foresight reads aggregates only (deck S8), so there is no ``subscriber_ref`` to
bind a row to, and inventing one to satisfy a pattern would be the opposite of
the invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from clarity.kernel.ids import new_id
from clarity.modules.foresight.backtest import CalibrationReport, Provenance
from clarity.modules.foresight.simulation import ForesightReport, Scenario, VolumeBand


class RunStatus(StrEnum):
    """Where a run has got to.

    ``FAILED`` carries a reason rather than disappearing: a rehearsal that could
    not be computed is a thing a product manager needs to see, and a job that
    vanishes reads as one that was never asked for.
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @property
    def is_finished(self) -> bool:
        return self in {RunStatus.SUCCEEDED, RunStatus.FAILED}


@dataclass(frozen=True)
class ScenarioVersion:
    """One version of a scenario, as somebody drafted it.

    ``scenario.scenario_id`` is the family: every version of one rehearsal
    shares it. ``version_id`` is this row. A new version is a new row because
    editing version 1 would silently change what an already-stored run claims to
    have rehearsed.
    """

    version_id: str
    scenario: Scenario
    version: int
    created_at: datetime
    created_by: str
    supersedes: str | None = None
    """The ``version_id`` this one replaces, or ``None`` for the first."""

    @property
    def scenario_id(self) -> str:
        """The family this version belongs to."""
        return self.scenario.scenario_id

    @staticmethod
    def first(scenario: Scenario, *, at: datetime, by: str) -> ScenarioVersion:
        return ScenarioVersion(
            version_id=new_id("SCV"),
            scenario=scenario,
            version=1,
            created_at=at,
            created_by=by,
        )

    def next(self, scenario: Scenario, *, at: datetime, by: str) -> ScenarioVersion:
        """The next version of this family, keeping the family id.

        The replacement keeps ``scenario_id`` because it is the same rehearsal
        being refined; a genuinely different change is a different scenario.
        """
        if scenario.scenario_id != self.scenario_id:
            raise ValueError(
                f"{scenario.scenario_id} is a different scenario from {self.scenario_id}; "
                "a new version keeps the family id"
            )
        return ScenarioVersion(
            version_id=new_id("SCV"),
            scenario=scenario,
            version=self.version + 1,
            created_at=at,
            created_by=by,
            supersedes=self.version_id,
        )


@dataclass
class ScenarioRun:
    """A requested rehearsal, and how far it got.

    The one mutable record in the module. Everything else here is written once;
    this one has a lifecycle because a caller polls it.
    """

    run_id: str
    scenario_version_id: str
    status: RunStatus
    requested_at: datetime
    requested_by: str
    idempotency_key: str
    """What makes a repeated request return the first run rather than a second.

    Required rather than optional: a run is cheap, but two runs of one scenario
    reported as two findings is how a rehearsal gets counted twice.
    """
    started_at: datetime | None = None
    finished_at: datetime | None = None
    report_id: str | None = None
    """``StoredReport.report_id`` once the run succeeds."""
    failure: str | None = None

    def running(self, *, at: datetime) -> None:
        self.status = RunStatus.RUNNING
        self.started_at = at

    def succeeded(self, *, report_id: str, at: datetime) -> None:
        self.status = RunStatus.SUCCEEDED
        self.report_id = report_id
        self.finished_at = at

    def failed(self, *, reason: str, at: datetime) -> None:
        self.status = RunStatus.FAILED
        self.failure = reason
        self.finished_at = at


@dataclass(frozen=True)
class StoredReport:
    """One engine output, kept against the run that produced it."""

    report_id: str
    """The report's own id. This is ``ForesightReport.run_id``, not the job id."""
    run_id: str
    """The :class:`ScenarioRun` that produced it."""
    scenario_version_id: str
    report: ForesightReport
    stored_at: datetime

    @staticmethod
    def of(
        report: ForesightReport, *, run_id: str, scenario_version_id: str, at: datetime
    ) -> StoredReport:
        return StoredReport(
            report_id=report.run_id,
            run_id=run_id,
            scenario_version_id=scenario_version_id,
            report=report,
            stored_at=at,
        )


@dataclass(frozen=True)
class StoredLaunch:
    """A change that shipped, and whose complaints were counted.

    This is the evidence the plan 02 section 3.4 gate opens on, which is why
    ``provenance`` and ``evidence_ref`` are fields on the record rather than
    something a caller asserts at read time. C6 adds the check that a ``REAL``
    launch cannot be recorded without both an injected capability and an
    external ``evidence_ref``; C2 gives that check somewhere to be enforced
    against.
    """

    launch_id: str
    scenario_version_id: str
    """What was predicted. A launch with no prediction cannot score anything."""
    provenance: Provenance
    recorded_at: datetime
    recorded_by: str
    evidence_ref: str | None = None
    """A reference outside this system for a ``REAL`` launch.

    ``None`` is correct for a synthetic launch and is what makes a real one
    checkable: somebody has to be able to go and look at the thing it names.
    """
    note: str = ""
    authority: str = ""
    """Which capability permitted a ``REAL`` launch (C6).

    Empty for a synthetic one. Recorded so a report that reaches CALIBRATED can
    say what let it, rather than leaving a reader to trust that something did.
    """

    @property
    def is_real(self) -> bool:
        return self.provenance is Provenance.REAL


@dataclass(frozen=True)
class RecordedOutcome:
    """What one launch actually produced, for one theme in one segment.

    Stored one row per observation rather than as a list on the launch, so an
    outcome recorded late is an insert rather than a rewrite of the launch. An
    append-only collection cannot take the rewrite, and a launch that had to be
    replaced to add an observation would lose who recorded the earlier ones.
    """

    outcome_id: str
    launch_id: str
    theme: str
    segment: str
    band: VolumeBand
    recorded_at: datetime
    recorded_by: str


@dataclass(frozen=True)
class StoredCalibration:
    """One backtest, kept so a report can cite the calibration it rested on."""

    calibration_id: str
    report: CalibrationReport
    launch_ids: tuple[str, ...]
    computed_at: datetime
    computed_by: str

    @staticmethod
    def of(
        report: CalibrationReport,
        *,
        launch_ids: tuple[str, ...],
        at: datetime,
        by: str,
    ) -> StoredCalibration:
        return StoredCalibration(
            calibration_id=report.run_id,
            report=report,
            launch_ids=launch_ids,
            computed_at=at,
            computed_by=by,
        )


class SpikeScope(StrEnum):
    """What a spike was counted over.

    Channel first, and alone for now, because ``complaint.created`` carries a
    channel code and no cluster: a cluster-scoped spike would need a field the
    event does not have, and inventing it in the consumer would be guessing.
    """

    CHANNEL = "channel"


@dataclass(frozen=True)
class DetectedSpike:
    """An early warning: more complaints in a window than the baseline expects.

    **Codes only.** ``contracts/events.py::_FORBIDDEN_SEGMENTS`` rejects any
    payload field whose name contains a ``name`` or ``card`` segment, so the
    event this becomes can carry a channel code and never a channel name. The
    record keeps the same discipline, so the two cannot drift.
    """

    spike_id: str
    scope: SpikeScope
    scope_ref: str
    """A code, never a name."""
    window_start: datetime
    window_end: datetime
    observed: int
    baseline: Decimal
    detected_at: datetime
    basis: str = ""
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ratio(self) -> Decimal | None:
        """How many times the baseline was seen. ``None`` when there is none.

        A zero baseline with any observation is not "infinitely bad", it is a
        window with nothing to compare against, and dividing would report a
        number that means neither.
        """
        if self.baseline <= 0:
            return None
        return Decimal(self.observed) / self.baseline


__all__ = [
    "DetectedSpike",
    "RecordedOutcome",
    "RunStatus",
    "ScenarioRun",
    "ScenarioVersion",
    "SpikeScope",
    "StoredCalibration",
    "StoredLaunch",
    "StoredReport",
]
