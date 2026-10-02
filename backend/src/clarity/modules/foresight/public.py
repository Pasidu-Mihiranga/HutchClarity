"""Public surface of the foresight module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

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
    "ChangeType",
    "Foresight",
    "ForesightReport",
    "Prediction",
    "Scenario",
    "Segment",
    "VolumeBand",
]
