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
    PersonaRounds,
    RadarSettings,
    Segment,
    ThemeCatalogue,
    ThemeWeight,
)
from clarity.modules.foresight.personas import (
    LlmPersonaSimulator,
    PersonaInvoke,
    PersonaRouter,
    PersonaRun,
    PersonaSimulator,
    Propensity,
    RoleRouterPersonas,
    RoundBasedPersonaSimulator,
    StatisticalBaseline,
)
from clarity.modules.foresight.radar import (
    OBSERVATIONS as FORESIGHT_OBSERVATIONS,
)
from clarity.modules.foresight.radar import (
    ComplaintObservation,
    ComplaintRadar,
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
from clarity.modules.foresight.rehearsal import (
    PairComparison,
    PersonaRehearsal,
    RehearsalReport,
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
    score_of,
)

__all__ = [
    "DEMO_LAUNCHES",
    "FORESIGHT_CALIBRATIONS",
    "FORESIGHT_LAUNCHES",
    "FORESIGHT_OBSERVATIONS",
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
    "ComplaintObservation",
    "ComplaintRadar",
    "DetectedSpike",
    "Foresight",
    "ForesightCatalogue",
    "ForesightReport",
    "ForesightRepository",
    "ForesightService",
    "HistoricLaunch",
    "LlmPersonaSimulator",
    "ObservedOutcome",
    "PairComparison",
    "PersonaInvoke",
    "PersonaRehearsal",
    "PersonaRounds",
    "PersonaRouter",
    "PersonaRun",
    "PersonaSimulator",
    "Prediction",
    "Propensity",
    "Provenance",
    "RadarSettings",
    "RealLaunchNotPermitted",
    "RecordedOutcome",
    "RehearsalReport",
    "RoleRouterPersonas",
    "RoundBasedPersonaSimulator",
    "RunAlreadyFinished",
    "RunStatus",
    "Scenario",
    "ScenarioRun",
    "ScenarioVersion",
    "Segment",
    "SpikeScope",
    "StatisticalBaseline",
    "StoredCalibration",
    "StoredForesightRepository",
    "StoredLaunch",
    "StoredReport",
    "ThemeCatalogue",
    "ThemeWeight",
    "UnknownRun",
    "UnknownScenario",
    "VolumeBand",
    "as_of_for",
    "score_of",
]
