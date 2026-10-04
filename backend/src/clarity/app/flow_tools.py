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
from clarity.contracts.decision import ActionType
from clarity.modules.actions.public import ToolLayerError
from clarity.modules.case.public import CaseNotReady
from clarity.modules.knowledge.public import Audience as KnowledgeAudience
from clarity.modules.knowledge.public import KnowledgeService


class ToolUnavailable(LookupError):
    """A flow asked for a tool this adapter does not implement yet."""


class FlowToolAdapter:
    """Maps a flow's tool name onto the narrow view.

    All nine tools the flow files name are implemented (A6). They were not,
    and the gap was invisible because the five missing ones are only reachable
    through the bounded agent step (C03), which has never run: no planner is
    configured without a remote provider. So a flow file declared a tool, the
    allowlist validated it, and the first planner to choose it would have got
    `TOOL_REFUSED` for a tool the flow was entitled to use.

    A tool that genuinely cannot be served still raises rather than returning
    an empty result, because a flow state that silently got nothing back would
    report an answer it never had.

    The read tools return the same shapes as the MCP server's handlers over the
    same `MCPCaseView`, deliberately: two surfaces onto one capability that
    disagreed about its shape would be two capabilities.
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
        if tool == "get_case_timeline":
            return self._timeline(case_id)
        if tool == "get_cause_assessment":
            return self._assessment(case_id)
        if tool == "explain_rule":
            return self._rule(**args)
        if tool == "get_customer_safeguards":
            return self._safeguards(case_id)
        if tool == "request_handoff":
            return self._handoff(case_id, **args)
        raise ToolUnavailable(
            f"{tool!r} is named by a flow but not wired into the flow tool adapter"
        )

    def _timeline(self, case_id: str) -> dict[str, Any]:
        """The evidence a decision was made on, by id and hash (I2)."""
        record = self._view.get(case_id)
        snapshot = record.snapshot or self._view.build_timeline(record.case_id)
        return {
            "case_id": record.case_id,
            "snapshot_hash": snapshot.snapshot_hash,
            "events": [
                {
                    "event_id": event.event_id,
                    "source": event.source.value,
                    "event_type": event.event_type.value,
                    "occurred_at": event.occurred_at.isoformat(),
                    "amount_lkr": (None if event.amount_lkr is None else f"{event.amount_lkr:.2f}"),
                }
                for event in snapshot.events
            ],
            "sources": {s.source.value: s.completeness.value for s in snapshot.sources},
        }

    def _assessment(self, case_id: str) -> dict[str, Any]:
        """What the rules concluded. Never what a model thinks (I1).

        An unevaluated case is a refusal rather than an exception: a flow may
        reach an explaining state before the case has been evaluated, and that
        is a thing to be told no about, not a fault.
        """
        record = self._view.get(case_id)
        if record.decision is None:
            return {"refused": "CASE_NOT_EVALUATED"}
        top = record.evaluation.top if record.evaluation else None
        return {
            "case_id": record.case_id,
            "outcome": record.decision.outcome.value,
            "amount_lkr": (
                None if record.decision.amount_lkr is None else f"{record.decision.amount_lkr:.2f}"
            ),
            "cause": (
                {
                    "rule_id": top.assessment.rule_id,
                    "rule_version": top.assessment.rule_version,
                    "confidence": str(top.assessment.confidence),
                }
                if top
                else None
            ),
            "ruled_out": [cause.rule_id for cause in record.decision.ruled_out],
            "allowed_actions": [action.value for action in record.decision.allowed_actions],
            "rationale": record.decision.rationale,
        }

    def _rule(self, **args: Any) -> dict[str, Any]:
        """The published rule, in its own words, so an explanation can cite it."""
        rule_id = str(args.get("rule_id") or "")
        pack = next((p for p in self._view.rule_packs() if p.rule_id == rule_id), None)
        if pack is None:
            return {"refused": "UNKNOWN_RULE"}
        return {
            "rule_id": pack.rule_id,
            "version": pack.version,
            "description": pack.description,
            "legal_basis": pack.legal_basis,
            "required_evidence": [source.value for source in pack.required_evidence],
            "allowed_actions": [action.value for action in pack.allowed_actions],
        }

    def _safeguards(self, case_id: str) -> dict[str, Any]:
        """What now protects this customer, from executed actions only.

        Read from `record.execution`, so it reports what was actually done
        rather than what was offered.
        """
        record = self._view.get(case_id)
        protective = {
            ActionType.BLOCK_MERCHANT_UNTIL_OPTIN,
            ActionType.ENABLE_DATA_STOP,
            ActionType.SET_SPEND_CAP,
            ActionType.ENABLE_FUP_ALERTS,
        }
        return {
            "case_id": record.case_id,
            "safeguards": [
                action.type.value
                for action in (record.execution.actions if record.execution else [])
                if action.type in protective
            ],
        }

    def _handoff(self, case_id: str, **args: Any) -> dict[str, Any]:
        """Ask for a person.

        It records the ask and reports it; it does not route. The desk queue is
        derived from the decision (`STAFF_APPROVAL` or `HANDOFF`, not yet
        executed), so a customer who asks for a person reaches a human through
        `customer_requested_human` on the case, which the decision policy turns
        into `HANDOFF` with `CUSTOMER_REQUESTED`. Having this tool write the
        queue directly would give a flow a second, unreviewed way onto a staff
        member's screen.

        The reason is capped and is the customer's own words, so it is a hint
        for the agent, never evidence (I2).
        """
        record = self._view.get(case_id)
        return {
            "case_id": record.case_id,
            "status": "handoff_requested",
            "reason": str(args.get("reason") or "")[:200],
            "requested_by": self._created_by,
        }

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
