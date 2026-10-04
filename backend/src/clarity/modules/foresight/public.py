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
from clarity.modules.foresight.rehearsal import (
    PairComparison,
    PersonaRehearsal,
    RehearsalReport,
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
    "Backtest",
    "Bands",
    "CalibrationReport",
    "CalibrationStatus",
    "CatalogueInvalid",
    "ChangeType",
    "Foresight",
    "ForesightCatalogue",
    "ForesightReport",
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
    "RehearsalReport",
    "RoleRouterPersonas",
    "RoundBasedPersonaSimulator",
    "Scenario",
    "Segment",
    "StatisticalBaseline",
    "ThemeCatalogue",
    "ThemeWeight",
    "VolumeBand",
    "as_of_for",
    "score_of",
]
