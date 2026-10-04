"""Public surface of the assurance module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.

This module calls no other module: it reacts to the audit trail and raises
alerts (ADR-0029, ADR-0037), so nothing on a money path waits for it.
"""

from __future__ import annotations

from clarity.modules.assurance.alerts import (
    ALERTS,
    SECOND_PERSON_BANDS,
    Alert,
    AlertNotFound,
    AlertRefused,
    AlertState,
    Disposition,
)
from clarity.modules.assurance.rules import RULES, Band, Finding
from clarity.modules.assurance.service import (
    CHAIN_BREAK,
    CHECKPOINT_GAP,
    DETECTOR_SILENT,
    HEARTBEATS,
    PLAYBOOK_SWITCHES,
    TRAIL_LAG,
    AssuranceService,
)

__all__ = [
    "ALERTS",
    "CHAIN_BREAK",
    "CHECKPOINT_GAP",
    "DETECTOR_SILENT",
    "HEARTBEATS",
    "PLAYBOOK_SWITCHES",
    "RULES",
    "SECOND_PERSON_BANDS",
    "TRAIL_LAG",
    "Alert",
    "AlertNotFound",
    "AlertRefused",
    "AlertState",
    "AssuranceService",
    "Band",
    "Disposition",
    "Finding",
]
