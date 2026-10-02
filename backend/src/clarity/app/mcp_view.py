"""The narrow view of the case service that MCP is allowed to hold.

Improvement plan item 0.3, from the alternative design's ADR-0008: *the MCP
server has no execute capability at all*.

Before this, ``ClarityMCPServer`` received the whole ``CaseService``, which
exposes ``confirm_and_execute``, ``approve_and_execute``, ``auto_fix`` and (via
a ``tools`` accessor) ``ToolLayer.authorise_auto_fix``. Nothing called them, so
the system was safe in practice -- but "the model cannot execute" was a
convention rather than a property, and a single future edit inside the MCP
package could have moved money with every test still green.

:class:`MCPCaseView` is the capability boundary. It offers reads and
``propose`` and nothing else, so the strongest thing reachable from MCP code is
a pending proposal that still needs confirmation minted elsewhere.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from clarity.contracts.decision import ActionPlan, ActionType
from clarity.contracts.timeline import EvidenceSnapshot
from clarity.modules.case.public import CaseRecord, CaseService
from clarity.modules.detection.public import RulePack
from clarity.modules.receipts.public import ReceiptService


@runtime_checkable
class MCPCaseView(Protocol):
    """Everything MCP may do. Deliberately has no execute or confirm method."""

    def get(self, case_id: str) -> CaseRecord: ...

    def all_cases(self) -> list[CaseRecord]: ...

    def build_timeline(self, case_id: str) -> EvidenceSnapshot: ...

    def rule_packs(self) -> list[RulePack]: ...

    def receipt_public_view(self, record: CaseRecord) -> dict[str, object]: ...

    def propose(
        self, case_id: str, *, created_by: str, action_types: list[ActionType] | None = None
    ) -> ActionPlan: ...


class CaseServiceMCPView:
    """Adapts :class:`CaseService` to :class:`MCPCaseView`.

    It holds the service privately and forwards only the permitted calls, so
    the execute methods are not reachable through the object MCP is given.
    """

    def __init__(self, cases: CaseService, receipts: ReceiptService) -> None:
        self.__cases = cases
        self.__receipts = receipts

    def get(self, case_id: str) -> CaseRecord:
        return self.__cases.get(case_id)

    def all_cases(self) -> list[CaseRecord]:
        return self.__cases.all_cases()

    def build_timeline(self, case_id: str) -> EvidenceSnapshot:
        return self.__cases.build_timeline(case_id)

    def rule_packs(self) -> list[RulePack]:
        return self.__cases.rules.packs

    def receipt_public_view(self, record: CaseRecord) -> dict[str, object]:
        if record.receipt is None:
            raise ValueError("no receipt has been issued for this case")
        return self.__receipts.public_view(record.receipt)

    def propose(
        self, case_id: str, *, created_by: str, action_types: list[ActionType] | None = None
    ) -> ActionPlan:
        """Create a pending plan. This is the strongest capability MCP has."""
        return self.__cases.propose(case_id, created_by=created_by, action_types=action_types)
