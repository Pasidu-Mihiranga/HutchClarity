"""Public surface of the detection module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.detection.engine import (
    MissingRuleParameter,
    RuleEngine,
    RuleEvaluation,
    RuleParameters,
)
from clarity.modules.detection.pack import (
    RulePack,
    RulePackLoadError,
    load_packs,
)
from clarity.modules.detection.parameters import PolicyRuleParameters
from clarity.modules.detection.predicates import (
    RuleSyntaxError,
)

__all__ = [
    "MissingRuleParameter",
    "PolicyRuleParameters",
    "RuleEngine",
    "RuleEvaluation",
    "RulePack",
    "RulePackLoadError",
    "RuleParameters",
    "RuleSyntaxError",
    "load_packs",
]
