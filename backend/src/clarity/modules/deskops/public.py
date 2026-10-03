"""Public surface of the deskops module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py).

Desk operations (D01, #26): a bulk fix with a dry run and four-eyes, merchant
watch scores, a regulator pack and a shift handover. Nothing here decides or
moves anything on its own: a bulk fix executes each case's own existing plan
through the single-case path, and the three views are counted reads.
"""

from __future__ import annotations

from clarity.modules.deskops.bulk import (
    BatchApproval,
    BatchStatus,
    BulkFix,
    BulkFixes,
    BulkFixRefused,
    CaseFixer,
    CasePreview,
    CaseResult,
    DryRun,
    Eligibility,
)
from clarity.modules.deskops.service import BATCHES, DeskCases, DeskOps
from clarity.modules.deskops.watch import (
    DEFAULT_WINDOW,
    WEIGHTS,
    DeskCase,
    Handover,
    MerchantScore,
    RegulatorPack,
    handover,
    merchant_watch,
    regulator_pack,
)

__all__ = [
    "BATCHES",
    "DEFAULT_WINDOW",
    "WEIGHTS",
    "BatchApproval",
    "BatchStatus",
    "BulkFix",
    "BulkFixRefused",
    "BulkFixes",
    "CaseFixer",
    "CasePreview",
    "CaseResult",
    "DeskCase",
    "DeskCases",
    "DeskOps",
    "DryRun",
    "Eligibility",
    "Handover",
    "MerchantScore",
    "RegulatorPack",
    "handover",
    "merchant_watch",
    "regulator_pack",
]
