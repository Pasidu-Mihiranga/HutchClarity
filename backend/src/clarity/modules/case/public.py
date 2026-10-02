"""Public surface of the case module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

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
from clarity.modules.case.service import CaseService

__all__ = [
    "CASES",
    "CASE_SEQUENCE",
    "CaseNotFound",
    "CaseNotReady",
    "CaseRecord",
    "CaseRepository",
    "CaseService",
    "StoredCaseRepository",
]
