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
    "Backtest",
    "Bands",
    "CalibrationReport",
    "CalibrationStatus",
    "CatalogueInvalid",
    "ChangeType",
    "Comparison",
    "Foresight",
    "ForesightCatalogue",
    "ForesightReport",
    "HistoricLaunch",
    "ObservedOutcome",
    "PersonaSimulator",
    "Prediction",
    "Provenance",
    "Scenario",
    "ScenarioRehearsal",
    "SeededPersonaSimulator",
    "Segment",
    "SwarmReport",
    "ThemeCatalogue",
    "ThemeWeight",
    "VolumeBand",
    "as_of_for",
]
