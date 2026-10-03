"""Public surface of the foresight module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.foresight.backtest import (
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

__all__ = [
    "MIN_REAL_LAUNCHES",
    "Backtest",
    "CalibrationReport",
    "CalibrationStatus",
    "ChangeType",
    "Foresight",
    "ForesightReport",
    "HistoricLaunch",
    "ObservedOutcome",
    "Prediction",
    "Provenance",
    "Scenario",
    "Segment",
    "VolumeBand",
]
