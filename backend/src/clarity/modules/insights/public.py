"""Public surface of the insights module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py).

Read models folded from the event log (I01, #30): top causes, where the
assistant stops, drop-offs and refunds by rule. Replaying the log rebuilds the
same numbers, which is what makes a dashboard worth reading.
"""

from __future__ import annotations

from clarity.modules.insights.projections import (
    ENDINGS,
    PROJECTED,
    STOP_REASONS,
    CaseFact,
    Insights,
    TurnFact,
    apply,
    rebuild,
)
from clarity.modules.insights.service import CURRENT, PROJECTIONS, InsightsService

__all__ = [
    "CURRENT",
    "ENDINGS",
    "PROJECTED",
    "PROJECTIONS",
    "STOP_REASONS",
    "CaseFact",
    "Insights",
    "InsightsService",
    "TurnFact",
    "apply",
    "rebuild",
]
