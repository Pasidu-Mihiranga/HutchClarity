"""Public surface of the decision module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.decision.assessor import (
    build_decision_input,
    build_risk_signals,
)
from clarity.modules.decision.policy import (
    DecisionPolicy,
    PolicyThresholds,
)
from clarity.modules.decision.zen import (
    DecisionTable,
    DecisionTableInvalid,
    ZenDecisionPolicy,
)

__all__ = [
    "DecisionPolicy",
    "DecisionTable",
    "DecisionTableInvalid",
    "PolicyThresholds",
    "ZenDecisionPolicy",
    "build_decision_input",
    "build_risk_signals",
]
