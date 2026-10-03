"""The tool surface a flow may reach (C02), built over the narrow MCP view.

This adapter lives in the composition root because it is the only place that
can see both a domain module and the view it reads through: `conversation` is
L4 and must not import another module (its row in
`tests/architecture/test_module_dependencies.py` is empty), so the flow router
takes a `ToolCaller` protocol and the container supplies this.

**The reason it is built over `MCPCaseView` and not over the resolution service
is capability, not convenience.** That view has read methods and `propose`, and
no execute, confirm or budget capability anywhere on it: the import contract
"AI and MCP cannot reach the tool layer's capabilities" covers
`clarity.app.mcp_view`. So "a flow cannot execute" is a property of the surface
it is handed rather than of the router's good behaviour, and a future change
that tried to give a flow an execution path would have to break an import
contract to do it.
"""

from __future__ import annotations

from typing import Any

from clarity.app.mcp_view import MCPCaseView
from clarity.modules.actions.public import ToolLayerError
from clarity.modules.case.public import CaseNotReady
from clarity.modules.knowledge.public import Audience as KnowledgeAudience
from clarity.modules.knowledge.public import KnowledgeService


class ToolUnavailable(LookupError):
    """A flow asked for a tool this adapter does not implement yet."""


class FlowToolAdapter:
    """Maps a flow's tool name onto the narrow view.

    Only the tools a flow actually reaches today are implemented. The rest
    raise rather than returning an empty result, because a flow state that
    silently got nothing back would report an answer it never had: the bounded
    agent step (C03, #22) is what needs the rest, and it should fail loudly
    until they exist.
    """

    def __init__(
        self,
        view: MCPCaseView,
        *,
        answers: KnowledgeService | None = None,
        created_by: str = "assistant",
    ) -> None:
        self._view = view
        self._answers = answers
        self._created_by = created_by

    def call(self, tool: str, *, case_id: str, **args: Any) -> dict[str, Any]:
        if tool == "propose_action":
            return self._propose(case_id, **args)
        if tool == "get_network_status":
            return dict(self._view.network_status(case_id))
        if tool == "get_trust_receipt":
            return dict(self._view.receipt_public_view(self._view.get(case_id)))
        if tool == "search_knowledge":
            return self._search(**args)
        raise ToolUnavailable(
            f"{tool!r} is named by a flow but not wired into the flow tool adapter"
        )

    def _search(self, **args: Any) -> dict[str, Any]:
        """Answer from the published corpus, cited, or report no source (K03).

        The audience is `customer` and is not taken from ``args``. A flow runs
        on behalf of a customer, and letting a tool argument choose the audience
        would let a planner ask for staff sources (I9, and the same reason the
        HTTP route fixes it).

        Returns `citations` because that is what the router puts in
        `FlowOutcome.citations`, which is what the `answer_found` condition
        reads and what the C01 turn verifier requires for a knowledge state. No
        source means no citations, so the flow takes its `no_source` exit and
        offers a person, which is the honest outcome rather than a failure.
        """
        if self._answers is None:
            raise ToolUnavailable("'search_knowledge' needs the knowledge service; none is wired")
        query = str(args.get("query") or "")
        found = self._answers.ask(query, audience=KnowledgeAudience.CUSTOMER)
        return {
            "citations": list(found.citations),
            "grounded": found.grounded,
            "answer": found.text,
            "needs_person": found.needs_person,
            "chunk_ids": list(found.trace.chunk_ids),
        }

    def _propose(self, case_id: str, **args: Any) -> dict[str, Any]:
        """Create a pending plan. The strongest thing a flow can do (I1).

        Executing it needs a confirmation token minted outside this path
        (ADR-0007), and nothing on this adapter can mint one.
        """
        created_by = str(args.get("created_by") or self._created_by)
        try:
            plan = self._view.propose(case_id, created_by=created_by)
        except (ToolLayerError, CaseNotReady) as refused:
            # A refusal is an answer, not a fault. A flow reaches a proposing
            # state whenever its conditions hold, and the tool layer is still
            # the authority on whether a plan may exist: EXPLAIN_ONLY has no
            # allowed action, a safeguard may be chosen before the case is
            # evaluated, and a budget can be spent. Letting that surface as an
            # error would end the customer's conversation over something the
            # flow is allowed to ask and be told no about.
            #
            # Returned rather than swallowed: the router sees no `plan_id`, so
            # the flow stays where it is, and the code reaches the turn audit.
            return {"refused": getattr(refused, "code", type(refused).__name__)}
        return {
            "plan_id": plan.plan_id,
            "amount_lkr": str(plan.total_amount_lkr),
            "action_types": [action.value for action in plan.action_types],
            "outcome": plan.outcome.value,
            "display_summary": plan.display_summary,
        }


__all__ = ["FlowToolAdapter", "ToolUnavailable"]
