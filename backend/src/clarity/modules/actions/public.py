"""Public surface of the actions module: vocabulary only.

Safe for every caller, including AI and MCP: typed refusals and the shapes of
results. The code that executes plans, mints confirmations or spends budget is
in :mod:`clarity.modules.actions.capability`, which only the ``case`` module and
the composition root may import (architecture test + import-linter).
"""

from __future__ import annotations

from clarity.modules.actions.errors import (
    ActionNotAllowed,
    ApprovalRequired,
    BudgetExhausted,
    ConfirmationInvalid,
    ConfirmationRequired,
    ExecutionFailed,
    ExecutionInProgress,
    OutcomeNotExecutable,
    PlanNotFound,
    PlanNotPending,
    ToolLayerError,
)
from clarity.modules.actions.results import (
    EXECUTABLE_OUTCOMES,
    ConfirmationToken,
    ConfirmedBy,
    ExecutionResult,
)

__all__ = [
    "EXECUTABLE_OUTCOMES",
    "ActionNotAllowed",
    "ApprovalRequired",
    "BudgetExhausted",
    "ConfirmationInvalid",
    "ConfirmationRequired",
    "ConfirmationToken",
    "ConfirmedBy",
    "ExecutionFailed",
    "ExecutionInProgress",
    "ExecutionResult",
    "OutcomeNotExecutable",
    "PlanNotFound",
    "PlanNotPending",
    "ToolLayerError",
]
