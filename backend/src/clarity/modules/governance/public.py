"""Public surface of the governance module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.governance.artefacts import (
    Approval,
    ChangeRefused,
    ChangeState,
    PolicyChange,
)
from clarity.modules.governance.governance import PolicyGovernance
from clarity.modules.governance.replay import (
    ImpactReport,
    OutcomeChange,
    PolicyReplay,
    ReplayCase,
    cases_from,
)
from clarity.modules.governance.repository import (
    CHANGES,
    PolicyChangeRepository,
    StoredPolicyChangeRepository,
)

__all__ = [
    "CHANGES",
    "Approval",
    "ChangeRefused",
    "ChangeState",
    "ImpactReport",
    "OutcomeChange",
    "PolicyChange",
    "PolicyChangeRepository",
    "PolicyGovernance",
    "PolicyReplay",
    "ReplayCase",
    "StoredPolicyChangeRepository",
    "cases_from",
]
