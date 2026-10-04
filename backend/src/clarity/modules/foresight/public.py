"""Public surface of the foresight module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.foresight.backtest import (
    DEMO_LAUNCHES,
    Backtest,
    CalibrationReport,
    CalibrationStatus,
    HistoricLaunch,
    ObservedOutcome,
    Provenance,
)
from clarity.modules.foresight.catalogue import (
    Bands,
    CatalogueInvalid,
    ChangeType,
    ForesightCatalogue,
    Segment,
    ThemeCatalogue,
    ThemeWeight,
)
from clarity.modules.foresight.records import (
    DetectedSpike,
    RecordedOutcome,
    RunStatus,
    ScenarioRun,
    ScenarioVersion,
    SpikeScope,
    StoredCalibration,
    StoredLaunch,
    StoredReport,
)
from clarity.modules.foresight.repository import (
    CALIBRATIONS as FORESIGHT_CALIBRATIONS,
)
from clarity.modules.foresight.repository import (
    LAUNCHES as FORESIGHT_LAUNCHES,
)
from clarity.modules.foresight.repository import (
    OUTCOMES as FORESIGHT_OUTCOMES,
)
from clarity.modules.foresight.repository import (
    REPORTS as FORESIGHT_REPORTS,
)
from clarity.modules.foresight.repository import (
    RUNS as FORESIGHT_RUNS,
)
from clarity.modules.foresight.repository import (
    SCENARIOS as FORESIGHT_SCENARIOS,
)
from clarity.modules.foresight.repository import (
    SPIKES as FORESIGHT_SPIKES,
)
from clarity.modules.foresight.repository import (
    ForesightRepository,
    StoredForesightRepository,
)
from clarity.modules.foresight.service import (
    ForesightService,
    RealLaunchNotPermitted,
    RunAlreadyFinished,
    UnknownRun,
    UnknownScenario,
)
from clarity.modules.foresight.simulation import (
    Foresight,
    ForesightReport,
    Prediction,
    Scenario,
    VolumeBand,
    as_of_for,
)
from clarity.modules.foresight.swarm import (
    Comparison,
    PersonaSimulator,
    ScenarioRehearsal,
    SeededPersonaSimulator,
    SwarmReport,
)

__all__ = [
    "DEMO_LAUNCHES",
    "FORESIGHT_CALIBRATIONS",
    "FORESIGHT_LAUNCHES",
    "FORESIGHT_OUTCOMES",
    "FORESIGHT_REPORTS",
    "FORESIGHT_RUNS",
    "FORESIGHT_SCENARIOS",
    "FORESIGHT_SPIKES",
    "Backtest",
    "Bands",
    "CalibrationReport",
    "CalibrationStatus",
    "CatalogueInvalid",
    "ChangeType",
    "Comparison",
    "DetectedSpike",
    "Foresight",
    "ForesightCatalogue",
    "ForesightReport",
    "ForesightRepository",
    "ForesightService",
    "HistoricLaunch",
    "ObservedOutcome",
    "PersonaSimulator",
    "Prediction",
    "Provenance",
    "RealLaunchNotPermitted",
    "RecordedOutcome",
    "RunAlreadyFinished",
    "RunStatus",
    "Scenario",
    "ScenarioRehearsal",
    "ScenarioRun",
    "ScenarioVersion",
    "SeededPersonaSimulator",
    "Segment",
    "SpikeScope",
    "StoredCalibration",
    "StoredForesightRepository",
    "StoredLaunch",
    "StoredReport",
    "SwarmReport",
    "ThemeCatalogue",
    "ThemeWeight",
    "UnknownRun",
    "UnknownScenario",
    "VolumeBand",
    "as_of_for",
]
