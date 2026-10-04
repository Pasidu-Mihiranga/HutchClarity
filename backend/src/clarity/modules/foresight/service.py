"""Foresight's stored operations (C2/F05).

C1 made the engine a pure function of a scenario and the policy in force. This
is the part that remembers: drafting a scenario, asking for a run, recording
what a change actually did, and keeping the backtest that reads it all back.

**Why a run is a record rather than a return value.** A rehearsal is slow enough
and important enough that a caller should be able to ask for one, go away, and
come back to the answer, which is the ``202`` plus poll URL C4 puts on top of
this. It also means two people can look at the same run, and that a run which
failed says so instead of vanishing.

**Idempotency (I8).** ``request_run`` takes a key and returns the original run
for a repeat. Foresight moves no money, so the risk is not a double charge; it
is a double *finding*. Two runs of one scenario, reported twice, is how a
rehearsal gets counted as two pieces of evidence.

**What this file deliberately does not do.** It will not record a real launch.
``Provenance.REAL`` is the only thing that can open the plan 02 section 3.4
calibration gate, and the locks that make recording one safe (a container
injected capability, a required external ``evidence_ref``) are C6's. Until they
exist the method refuses rather than leaving the path open and trusting a
caller, because an ungated way to write the evidence is worth more to somebody
wanting a green gate than the gate itself is worth to anybody else.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from clarity.kernel.ids import new_id
from clarity.modules.foresight.backtest import (
    Backtest,
    CalibrationReport,
    HistoricLaunch,
    ObservedOutcome,
    Provenance,
)
from clarity.modules.foresight.catalogue import ForesightCatalogue
from clarity.modules.foresight.records import (
    DetectedSpike,
    RecordedOutcome,
    RunStatus,
    ScenarioRun,
    ScenarioVersion,
    StoredCalibration,
    StoredLaunch,
    StoredReport,
)
from clarity.modules.foresight.repository import StoredForesightRepository
from clarity.modules.foresight.simulation import Foresight, Scenario, VolumeBand
from clarity.platform.persistence import UnitOfWork, UnitOfWorkFactory


class UnknownScenario(KeyError):
    """A version id nothing stored. Refused rather than treated as a new draft."""


class UnknownRun(KeyError):
    """A run id nothing stored."""


class RunAlreadyFinished(RuntimeError):
    """A finished run cannot be executed again.

    Its report is append-only, so a second execution would either fail at the
    write or replace an output somebody has already read.
    """


class RealLaunchNotPermitted(PermissionError):
    """Recording a real launch was refused.

    Deliberately an error rather than a silent downgrade to ``SYNTHETIC``: a
    caller who meant to record real evidence and got a synthetic row would have
    their evidence quietly not count, and would find out at the gate.
    """


class RealLaunchCapability(Protocol):
    """Permission to record a launch that actually happened (C6, lock 3).

    A capability the composition root supplies, not a flag a caller passes and
    not a permission a role carries. The difference matters: a permission says
    *who* may write the row, and this says whether this **deployment** has real
    launch records at all. In the prototype none exists (REQUIRES HUTCH
    CONFIRMATION), so no profile wires one and the path is closed everywhere,
    whatever role a caller holds.

    ``describe`` is recorded on the launch, so a report that reaches CALIBRATED
    can say which source of truth let it.
    """

    def permits(self) -> bool: ...

    def describe(self) -> str: ...


class ForesightService:
    """Drafts, runs, evidence and backtests, over the module's repository."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory,
        catalogue: ForesightCatalogue,
        clock: Callable[[], datetime] | None = None,
        real_launches: RealLaunchCapability | None = None,
    ) -> None:
        self._open_unit = open_unit
        self._catalogue = catalogue
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        # Absent in every shipped profile: the prototype has no real launch
        # records to describe (I16). A deployment that has them wires one here,
        # which is the single place that decision is made.
        self._real_launches = real_launches

    @staticmethod
    def _repository(unit: UnitOfWork) -> StoredForesightRepository:
        return StoredForesightRepository.of(unit)

    # -- scenarios --------------------------------------------------------- #

    def draft(self, scenario: Scenario, *, by: str) -> ScenarioVersion:
        """Store the first version of a scenario family."""
        version = ScenarioVersion.first(scenario, at=self._clock(), by=by)
        with self._open_unit() as unit:
            self._repository(unit).save_version(version)
            unit.commit()
        return version

    def revise(self, scenario: Scenario, *, by: str) -> ScenarioVersion:
        """Store the next version of an existing family.

        Takes the whole scenario rather than a patch: :class:`Scenario` is
        frozen, so a caller builds the revision with ``dataclasses.replace``,
        which keeps the family id and makes the diff explicit at the call site.
        """
        with self._open_unit() as unit:
            repository = self._repository(unit)
            previous = repository.latest_version(scenario.scenario_id)
            if previous is None:
                raise UnknownScenario(scenario.scenario_id)
            version = previous.next(scenario, at=self._clock(), by=by)
            repository.save_version(version)
            unit.commit()
        return version

    def version(self, version_id: str) -> ScenarioVersion | None:
        with self._open_unit() as unit:
            return self._repository(unit).version(version_id)

    def versions_of(self, scenario_id: str) -> list[ScenarioVersion]:
        with self._open_unit() as unit:
            return self._repository(unit).versions_of(scenario_id)

    def scenarios(self) -> list[ScenarioVersion]:
        """The latest version of every family, newest first."""
        with self._open_unit() as unit:
            repository = self._repository(unit)
            families = {v.scenario_id for v in repository.all_versions()}
            latest = [repository.latest_version(f) for f in families]
        return sorted(
            (v for v in latest if v is not None),
            key=lambda v: v.created_at,
            reverse=True,
        )

    # -- runs -------------------------------------------------------------- #

    def request_run(
        self, version_id: str, *, by: str, idempotency_key: str
    ) -> tuple[ScenarioRun, bool]:
        """Queue a rehearsal. Returns the run and whether it is new (I8).

        The flag is what lets C4 answer ``202`` for a new run and point a repeat
        at the original rather than pretending it just created one.
        """
        with self._open_unit() as unit:
            repository = self._repository(unit)
            existing = repository.run_for(idempotency_key)
            if existing is not None:
                return existing, False
            if repository.version(version_id) is None:
                raise UnknownScenario(version_id)
            run = ScenarioRun(
                run_id=new_id("RUN"),
                scenario_version_id=version_id,
                status=RunStatus.QUEUED,
                requested_at=self._clock(),
                requested_by=by,
                idempotency_key=idempotency_key,
            )
            repository.save_run(run)
            unit.commit()
        return run, True

    def execute(self, run_id: str) -> StoredReport:
        """Run the engine for a queued run and store its report.

        The calibration the report rests on is the latest stored one, attached
        here rather than passed in: a report that chose its own backtest could
        be made to look decision-ready by handing it a friendlier one.
        """
        with self._open_unit() as unit:
            repository = self._repository(unit)
            run = repository.run(run_id)
            if run is None:
                raise UnknownRun(run_id)
            if run.status.is_finished:
                raise RunAlreadyFinished(run_id)
            version = repository.version(run.scenario_version_id)
            if version is None:  # pragma: no cover - a run cannot be queued without one
                raise UnknownScenario(run.scenario_version_id)
            calibration = repository.latest_calibration()
            run.running(at=self._clock())
            repository.save_run(run)
            unit.commit()

        engine = Foresight(self._catalogue, clock=self._clock)
        try:
            report = engine.run(
                version.scenario,
                calibration=calibration.report if calibration is not None else None,
            )
        except Exception as error:
            with self._open_unit() as unit:
                repository = self._repository(unit)
                failed = repository.run(run_id)
                if failed is not None:
                    failed.failed(reason=str(error), at=self._clock())
                    repository.save_run(failed)
                unit.commit()
            raise

        stored = StoredReport.of(
            report,
            run_id=run_id,
            scenario_version_id=version.version_id,
            at=self._clock(),
        )
        with self._open_unit() as unit:
            repository = self._repository(unit)
            repository.save_report(stored)
            succeeded = repository.run(run_id)
            if succeeded is not None:
                succeeded.succeeded(report_id=stored.report_id, at=self._clock())
                repository.save_run(succeeded)
            unit.commit()
        return stored

    def run(self, run_id: str) -> ScenarioRun | None:
        with self._open_unit() as unit:
            return self._repository(unit).run(run_id)

    def report_of_run(self, run_id: str) -> StoredReport | None:
        with self._open_unit() as unit:
            return self._repository(unit).report_of_run(run_id)

    def runs(self) -> list[ScenarioRun]:
        with self._open_unit() as unit:
            return self._repository(unit).all_runs()

    # -- evidence ---------------------------------------------------------- #

    def record_launch(
        self,
        *,
        scenario_version_id: str,
        provenance: Provenance,
        by: str,
        evidence_ref: str | None = None,
        note: str = "",
    ) -> StoredLaunch:
        """Record that a rehearsed change shipped.

        Refuses ``REAL`` until C6 wires the capability and the evidence check.
        """
        if provenance is Provenance.REAL:
            self._check_real_launch(evidence_ref)
        with self._open_unit() as unit:
            repository = self._repository(unit)
            if repository.version(scenario_version_id) is None:
                raise UnknownScenario(scenario_version_id)
            launch = StoredLaunch(
                launch_id=new_id("LNC"),
                scenario_version_id=scenario_version_id,
                provenance=provenance,
                recorded_at=self._clock(),
                recorded_by=by,
                evidence_ref=evidence_ref,
                note=note,
                authority=(
                    self._real_launches.describe()
                    if provenance is Provenance.REAL and self._real_launches is not None
                    else ""
                ),
            )
            repository.save_launch(launch)
            unit.commit()
        return launch

    def _check_real_launch(self, evidence_ref: str | None) -> None:
        """Both keys, or nothing (C6, lock 3).

        Checked before anything is written, so a refusal leaves no partial row
        and no evidence that half-counts.
        """
        if self._real_launches is None or not self._real_launches.permits():
            raise RealLaunchNotPermitted(
                "this deployment has no real launch records, so no launch may be "
                "recorded as REAL. The capability is supplied by the composition "
                "root, not by a caller or a role."
            )
        if not (evidence_ref or "").strip():
            raise RealLaunchNotPermitted(
                "a real launch needs an external evidence reference somebody can "
                "go and check. Without one the record is an assertion, and an "
                "assertion is what the calibration gate exists to refuse."
            )

    def record_outcome(
        self, *, launch_id: str, theme: str, segment: str, band: VolumeBand, by: str
    ) -> RecordedOutcome:
        """Record one observed theme-segment band for a launch."""
        with self._open_unit() as unit:
            repository = self._repository(unit)
            if repository.launch(launch_id) is None:
                raise KeyError(launch_id)
            outcome = RecordedOutcome(
                outcome_id=new_id("OUT"),
                launch_id=launch_id,
                theme=theme,
                segment=segment,
                band=band,
                recorded_at=self._clock(),
                recorded_by=by,
            )
            repository.save_outcome(outcome)
            unit.commit()
        return outcome

    def launches(self) -> list[StoredLaunch]:
        with self._open_unit() as unit:
            return self._repository(unit).all_launches()

    def outcomes_of(self, launch_id: str) -> list[RecordedOutcome]:
        with self._open_unit() as unit:
            return self._repository(unit).outcomes_of(launch_id)

    # -- calibration ------------------------------------------------------- #

    def backtest(self, *, by: str) -> StoredCalibration:
        """Replay every stored launch through the baseline and keep the result.

        A launch whose scenario version has gone is skipped rather than guessed
        at: scoring a prediction against a scenario nobody can read is a number
        with no basis.
        """
        with self._open_unit() as unit:
            repository = self._repository(unit)
            historic: list[HistoricLaunch] = []
            for stored in repository.all_launches():
                version = repository.version(stored.scenario_version_id)
                if version is None:  # pragma: no cover - append-only, so unreachable today
                    continue
                historic.append(
                    HistoricLaunch(
                        launch_id=stored.launch_id,
                        scenario=version.scenario,
                        observed=tuple(
                            ObservedOutcome(o.theme, o.segment, o.band)
                            for o in repository.outcomes_of(stored.launch_id)
                        ),
                        provenance=stored.provenance,
                    )
                )

        report = Backtest(self._catalogue, clock=self._clock).run(tuple(historic))
        stored_calibration = StoredCalibration.of(
            report,
            launch_ids=tuple(launch.launch_id for launch in historic),
            at=self._clock(),
            by=by,
        )
        with self._open_unit() as unit:
            self._repository(unit).save_calibration(stored_calibration)
            unit.commit()
        return stored_calibration

    def latest_calibration(self) -> StoredCalibration | None:
        with self._open_unit() as unit:
            return self._repository(unit).latest_calibration()

    def calibrations(self) -> list[StoredCalibration]:
        with self._open_unit() as unit:
            return self._repository(unit).all_calibrations()

    # -- radar ------------------------------------------------------------- #

    def record_spike(self, spike: DetectedSpike) -> None:
        """Keep a detected spike. C5 supplies the detector that makes them."""
        with self._open_unit() as unit:
            self._repository(unit).save_spike(spike)
            unit.commit()

    def spikes(self) -> list[DetectedSpike]:
        with self._open_unit() as unit:
            return self._repository(unit).all_spikes()


__all__ = [
    "CalibrationReport",
    "ForesightService",
    "RealLaunchCapability",
    "RealLaunchNotPermitted",
    "RunAlreadyFinished",
    "UnknownRun",
    "UnknownScenario",
]
