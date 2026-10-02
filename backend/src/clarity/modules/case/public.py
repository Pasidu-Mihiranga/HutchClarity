"""Public surface of the case module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.

The orchestration that used to live here moved to
``clarity.modules.resolution`` (M-CASE, plan 21 section 2.2). What remains is
the aggregate: one case, its evidence, its decision and its state machine.
"""

from __future__ import annotations

from clarity.modules.case.aggregate import (
    NO_CONFIRMATION_CHANNELS,
    CaseAggregate,
)
from clarity.modules.case.records import (
    CaseNotFound,
    CaseNotReady,
    CaseRecord,
)
from clarity.modules.case.repository import (
    CASE_SEQUENCE,
    CASES,
    CaseRepository,
    StoredCaseRepository,
)

__all__ = [
    "CASES",
    "CASE_SEQUENCE",
    "NO_CONFIRMATION_CHANNELS",
    "CaseAggregate",
    "CaseNotFound",
    "CaseNotReady",
    "CaseRecord",
    "CaseRepository",
    "StoredCaseRepository",
]
