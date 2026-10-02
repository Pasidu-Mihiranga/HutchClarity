"""Typed refusals from the tool layer.

Every refusal carries a stable code. Codes are what the orchestrator maps to
a template or a handoff, and what an LLM is told - never a stack trace, and
never enough detail to help someone probe the guard (plan §10.3).
"""

from __future__ import annotations


class ToolLayerError(RuntimeError):
    """Base class. ``code`` is the stable, loggable identifier."""

    code = "TOOL_ERROR"

    transient = False
    """Whether retrying the same request could succeed later (M-ACT).

    A **final** refusal is a decision: the policy does not allow this action, or
    the maker tried to approve their own plan. Retrying it with the same
    idempotency key must give the same answer, or a caller could get a different
    outcome for one request by asking twice.

    A **transient** failure is a condition: the daily refund budget is spent, or
    an adapter was briefly unreachable. Nothing was applied, so the same plan may
    be executed again under a new attempt number. Treating one of these as final
    is what left a plan stuck forever once its key was burned, which is the
    defect M-ACT fixes.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ActionNotAllowed(ToolLayerError):
    """The decision does not permit this action for this case.

    Raised when a caller proposes something outside ``Decision.allowed_actions``:
    the main guard against a model inventing a remedy.
    """

    code = "ACTION_NOT_ALLOWED_BY_POLICY"


class OutcomeNotExecutable(ToolLayerError):
    """The decision was EXPLAIN_ONLY or HANDOFF, so nothing may be executed."""

    code = "OUTCOME_NOT_EXECUTABLE"


class ConfirmationRequired(ToolLayerError):
    """Execution was attempted without a valid confirmation token."""

    code = "CONFIRMATION_REQUIRED"


class ConfirmationInvalid(ToolLayerError):
    """The token is unknown, expired, already used, or bound to another plan."""

    code = "CONFIRMATION_INVALID"


class ApprovalRequired(ToolLayerError):
    """Staff approval is missing, incomplete, or breaks separation of duties."""

    code = "APPROVAL_REQUIRED"


class BudgetExhausted(ToolLayerError):
    """The refund budget cannot cover this plan (plan §14.4)."""

    code = "BUDGET_EXHAUSTED"

    transient = True
    """The daily budget resets, so tomorrow the same plan can be executed."""


class PlanNotFound(ToolLayerError):
    code = "PLAN_NOT_FOUND"


class PlanNotPending(ToolLayerError):
    """The plan was already executed, rejected or expired."""

    code = "PLAN_NOT_PENDING"


class ExecutionFailed(ToolLayerError):
    """One or more steps failed and the applied steps were compensated."""

    code = "EXECUTION_FAILED"


class ExecutionInProgress(ToolLayerError):
    """An identical request is still running and did not finish in time.

    Raised only when a duplicate waits longer than the agreed window. The
    caller must retry with the **same** idempotency key rather than a new one,
    so the original execution stays the only one.
    """

    code = "EXECUTION_IN_PROGRESS"

    transient = True
    """The original attempt has not finished; asking again later is the answer."""
