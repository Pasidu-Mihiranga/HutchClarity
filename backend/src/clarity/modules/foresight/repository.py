"""Where foresight keeps its scenarios, runs and evidence (C2/F05).

Seven collections, modelled on ``modules/autopsy/repository.py``: a protocol
over the module's own record types, and one implementation that delegates to the
platform's :class:`~clarity.platform.persistence.Repository`. The same domain
code then runs on the in-memory driver and on PostgreSQL with no branch (I6,
ADR-0013).

**Six of the seven are append-only.** ``foresight.runs`` is the exception, and
the exception is the point: a run has a lifecycle a caller polls, so its row
moves. Everything else is either something somebody asked for, something the
engine produced, or evidence about a change that shipped, and none of those
three gets to change after the fact. The last group matters most: a launch and
its outcomes are what the plan 02 section 3.4 gate opens on, so they are exactly
the rows somebody would have to rewrite to make an uncalibrated engine look
calibrated. Append-only is backed by database grants, not by this file
remembering.

**Lookups scan.** The platform repository is deliberately small (get, put,
delete, keys, values), so finding a run by its idempotency key or the outcomes
of a launch is a scan over ``values()``. That is what ``autopsy`` does too. It
is fine at the volumes foresight works at - a rehearsal is a human-initiated
act, not a per-request one - and if it stops being fine the answer is an index
in the driver, not a second copy of the data here.
"""

from __future__ import annotations

from typing import Protocol

from clarity.modules.foresight.records import (
    DetectedSpike,
    RecordedOutcome,
    ScenarioRun,
    ScenarioVersion,
    StoredCalibration,
    StoredLaunch,
    StoredReport,
)
from clarity.platform.persistence import Repository, UnitOfWork

#: One collection is one table. The prefix is what `OWNERS` maps to the module,
#: so all seven land in the `clarity_foresight` schema with its own role.
SCENARIOS = "foresight.scenarios"
RUNS = "foresight.runs"
REPORTS = "foresight.reports"
LAUNCHES = "foresight.launches"
OUTCOMES = "foresight.outcomes"
CALIBRATIONS = "foresight.calibrations"
SPIKES = "foresight.spikes"


class ForesightRepository(Protocol):
    """Scenarios and their versions, runs, outputs, and the evidence."""

    # -- scenarios --------------------------------------------------------- #

    def save_version(self, version: ScenarioVersion) -> None: ...

    def version(self, version_id: str) -> ScenarioVersion | None: ...

    def versions_of(self, scenario_id: str) -> list[ScenarioVersion]:
        """Every version of one scenario family, oldest first."""
        ...

    def latest_version(self, scenario_id: str) -> ScenarioVersion | None:
        """The highest-numbered version, or ``None`` for an unknown family."""
        ...

    def all_versions(self) -> list[ScenarioVersion]: ...

    # -- runs -------------------------------------------------------------- #

    def save_run(self, run: ScenarioRun) -> None: ...

    def run(self, run_id: str) -> ScenarioRun | None: ...

    def run_for(self, idempotency_key: str) -> ScenarioRun | None:
        """The run a repeated request should be given back (I8).

        A duplicate request gets the original run, including its original
        outcome, rather than starting a second rehearsal of the same scenario.
        """
        ...

    def all_runs(self) -> list[ScenarioRun]: ...

    # -- outputs ----------------------------------------------------------- #

    def save_report(self, report: StoredReport) -> None: ...

    def report(self, report_id: str) -> StoredReport | None: ...

    def report_of_run(self, run_id: str) -> StoredReport | None: ...

    def all_reports(self) -> list[StoredReport]: ...

    def save_calibration(self, calibration: StoredCalibration) -> None: ...

    def calibration(self, calibration_id: str) -> StoredCalibration | None: ...

    def latest_calibration(self) -> StoredCalibration | None:
        """The most recently computed backtest, or ``None`` if none has run."""
        ...

    def all_calibrations(self) -> list[StoredCalibration]: ...

    # -- evidence ---------------------------------------------------------- #

    def save_launch(self, launch: StoredLaunch) -> None: ...

    def launch(self, launch_id: str) -> StoredLaunch | None: ...

    def all_launches(self) -> list[StoredLaunch]: ...

    def real_launches(self) -> list[StoredLaunch]:
        """Only the launches that actually happened.

        The gate counts these and nothing else, so it is a method rather than a
        filter each caller writes: a caller that forgot the filter would count
        synthetic launches towards calibration.
        """
        ...

    def save_outcome(self, outcome: RecordedOutcome) -> None: ...

    def outcomes_of(self, launch_id: str) -> list[RecordedOutcome]: ...

    def all_outcomes(self) -> list[RecordedOutcome]: ...

    # -- radar ------------------------------------------------------------- #

    def save_spike(self, spike: DetectedSpike) -> None: ...

    def spike(self, spike_id: str) -> DetectedSpike | None: ...

    def all_spikes(self) -> list[DetectedSpike]: ...


class StoredForesightRepository:
    """``ForesightRepository`` over any persistence driver."""

    def __init__(
        self,
        scenarios: Repository[str, ScenarioVersion],
        runs: Repository[str, ScenarioRun],
        reports: Repository[str, StoredReport],
        launches: Repository[str, StoredLaunch],
        outcomes: Repository[str, RecordedOutcome],
        calibrations: Repository[str, StoredCalibration],
        spikes: Repository[str, DetectedSpike],
    ) -> None:
        self._scenarios = scenarios
        self._runs = runs
        self._reports = reports
        self._launches = launches
        self._outcomes = outcomes
        self._calibrations = calibrations
        self._spikes = spikes

    @staticmethod
    def of(unit: UnitOfWork) -> StoredForesightRepository:
        """The repository bound to one unit of work.

        Here rather than in every caller so a new collection is added in one
        place, and so nobody half-wires it and silently writes to six tables.
        """
        return StoredForesightRepository(
            scenarios=unit.repository(SCENARIOS),
            runs=unit.repository(RUNS),
            reports=unit.repository(REPORTS),
            launches=unit.repository(LAUNCHES),
            outcomes=unit.repository(OUTCOMES),
            calibrations=unit.repository(CALIBRATIONS),
            spikes=unit.repository(SPIKES),
        )

    # -- scenarios --------------------------------------------------------- #

    def save_version(self, version: ScenarioVersion) -> None:
        self._scenarios.put(version.version_id, version)

    def version(self, version_id: str) -> ScenarioVersion | None:
        return self._scenarios.get(version_id)

    def versions_of(self, scenario_id: str) -> list[ScenarioVersion]:
        return sorted(
            (v for v in self._scenarios.values() if v.scenario_id == scenario_id),
            key=lambda v: v.version,
        )

    def latest_version(self, scenario_id: str) -> ScenarioVersion | None:
        versions = self.versions_of(scenario_id)
        return versions[-1] if versions else None

    def all_versions(self) -> list[ScenarioVersion]:
        return self._scenarios.values()

    # -- runs -------------------------------------------------------------- #

    def save_run(self, run: ScenarioRun) -> None:
        self._runs.put(run.run_id, run)

    def run(self, run_id: str) -> ScenarioRun | None:
        return self._runs.get(run_id)

    def run_for(self, idempotency_key: str) -> ScenarioRun | None:
        for run in self._runs.values():
            if run.idempotency_key == idempotency_key:
                return run
        return None

    def all_runs(self) -> list[ScenarioRun]:
        return self._runs.values()

    # -- outputs ----------------------------------------------------------- #

    def save_report(self, report: StoredReport) -> None:
        self._reports.put(report.report_id, report)

    def report(self, report_id: str) -> StoredReport | None:
        return self._reports.get(report_id)

    def report_of_run(self, run_id: str) -> StoredReport | None:
        for report in self._reports.values():
            if report.run_id == run_id:
                return report
        return None

    def all_reports(self) -> list[StoredReport]:
        return self._reports.values()

    def save_calibration(self, calibration: StoredCalibration) -> None:
        self._calibrations.put(calibration.calibration_id, calibration)

    def calibration(self, calibration_id: str) -> StoredCalibration | None:
        return self._calibrations.get(calibration_id)

    def latest_calibration(self) -> StoredCalibration | None:
        stored = self._calibrations.values()
        if not stored:
            return None
        return max(stored, key=lambda c: c.computed_at)

    def all_calibrations(self) -> list[StoredCalibration]:
        return self._calibrations.values()

    # -- evidence ---------------------------------------------------------- #

    def save_launch(self, launch: StoredLaunch) -> None:
        self._launches.put(launch.launch_id, launch)

    def launch(self, launch_id: str) -> StoredLaunch | None:
        return self._launches.get(launch_id)

    def all_launches(self) -> list[StoredLaunch]:
        return self._launches.values()

    def real_launches(self) -> list[StoredLaunch]:
        return [launch for launch in self._launches.values() if launch.is_real]

    def save_outcome(self, outcome: RecordedOutcome) -> None:
        self._outcomes.put(outcome.outcome_id, outcome)

    def outcomes_of(self, launch_id: str) -> list[RecordedOutcome]:
        return [o for o in self._outcomes.values() if o.launch_id == launch_id]

    def all_outcomes(self) -> list[RecordedOutcome]:
        return self._outcomes.values()

    # -- radar ------------------------------------------------------------- #

    def save_spike(self, spike: DetectedSpike) -> None:
        self._spikes.put(spike.spike_id, spike)

    def spike(self, spike_id: str) -> DetectedSpike | None:
        return self._spikes.get(spike_id)

    def all_spikes(self) -> list[DetectedSpike]:
        return self._spikes.values()


__all__ = [
    "CALIBRATIONS",
    "LAUNCHES",
    "OUTCOMES",
    "REPORTS",
    "RUNS",
    "SCENARIOS",
    "SPIKES",
    "ForesightRepository",
    "StoredForesightRepository",
]
