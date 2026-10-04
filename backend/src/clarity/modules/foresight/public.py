"""Public surface of the foresight module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.foresight.backtest import (
    DEMO_LAUNCHES,
    MIN_REAL_LAUNCHES,
    Backtest,
    CalibrationReport,
    CalibrationStatus,
    HistoricLaunch,
    ObservedOutcome,
    Provenance,
)
from clarity.modules.foresight.simulation import (
    ChangeType,
    Foresight,
    ForesightReport,
    Prediction,
    Scenario,
    Segment,
    VolumeBand,
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
    "MIN_REAL_LAUNCHES",
    "Backtest",
    "CalibrationReport",
    "CalibrationStatus",
    "ChangeType",
    "Comparison",
    "Foresight",
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
    "VolumeBand",
]
