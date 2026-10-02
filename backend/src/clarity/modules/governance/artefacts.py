"""The policy change artefact and its vocabulary.

Separate from the governance gate so the repository protocol can name the
artefact it stores without importing the gate that moves it along.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from clarity.kernel.common import utc_now
from clarity.modules.governance.replay import ImpactReport
from clarity.platform.config.artefacts import ChangeClass, PolicyValue


class ChangeState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    ACTIVE = "active"
    REJECTED = "rejected"


class ChangeRefused(PermissionError):
    """A change cannot move forward. The reason is stable and auditable."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class Approval:
    approver_ref: str
    role: str
    at: datetime
    mfa_step_up: bool


@dataclass
class PolicyChange:
    """One proposed change, from draft to active."""

    change_id: str
    key: str
    candidate: PolicyValue
    change_class: ChangeClass
    maker_ref: str
    state: ChangeState = ChangeState.DRAFT
    approvals: list[Approval] = field(default_factory=list)
    impact: ImpactReport | None = None
    reason: str = ""
    created_at: datetime = field(default_factory=utc_now)
    activated_at: datetime | None = None

    @property
    def approvals_needed(self) -> int:
        return 2 if self.change_class.needs_second_approver else 1

    @property
    def is_approved(self) -> bool:
        return len(self.approvals) >= self.approvals_needed


__all__ = ["Approval", "ChangeRefused", "ChangeState", "PolicyChange"]
