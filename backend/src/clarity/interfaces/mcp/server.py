"""The Clarity MCP server (plan §10, §11).

This is the only way an AI agent can reach Clarity, and it is built so that the
most dangerous thing a compromised or confused model can do is *ask for
something and be refused*.

The guarantees, in order of importance:

1. **No execution, ever.** There is no tool that moves money or changes a
   service. The strongest write a model has is ``propose_action``, which
   creates a pending plan. Execution needs a confirmation token minted outside
   this server (plan §10.4-10.5).
2. **No amounts from the model.** ``propose_action`` takes an action type, not
   a sum. The amount comes from the decision record.
3. **Bound to one subject.** A session is tied to a case; a tool call for
   another case is denied, so one customer's agent cannot read another's data.
4. **Allowlisted per profile.** ``customer-assist`` sees fewer tools than
   ``staff-assist``; the model cannot widen its own profile.
5. **Everything audited.** Every call, allowed or denied, writes an
   ``MCPInvocation`` record.

**Prototype note.** Plan §10.6 runs this over the MCP SDK's Streamable HTTP
transport with OAuth and mTLS, and evaluates policy in OPA. Here the tool
registry, profiles, policy checks and audit are real and tested; the transport
and the identity layer are not. The security properties being demonstrated are
the authorization ones, which is where the risk actually sits.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from clarity.ai.pii import Masker
from clarity.app.mcp_view import MCPCaseView
from clarity.contracts.decision import ActionType
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import ActionSafetyLevel, utc_now
from clarity.kernel.ids import new_id
from clarity.modules.actions.public import ToolLayerError
from clarity.modules.case.public import CaseNotFound, CaseNotReady
from clarity.platform.audit.ledger import ActorKind, AuditEventType, AuditLedger


def _words(text: str) -> list[str]:
    return re.findall(r"[\w\u0D80-\u0DFF\u0B80-\u0BFF]+", text)


class Profile(StrEnum):
    """Which tools a session may use (plan §10.3)."""

    CUSTOMER_ASSIST = "customer-assist"
    STAFF_ASSIST = "staff-assist"
    ANALYTICS = "analytics"


class ToolDenied(PermissionError):
    """A tool call was refused. The reason is stable and safe to log."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class Principal:
    """Who is calling. Set by the orchestrator, never by the model."""

    ref: str
    profile: Profile
    case_id: str | None = None
    """Customer sessions are bound to one case."""


@dataclass
class ToolSpec:
    name: str
    level: ActionSafetyLevel
    profiles: frozenset[Profile]
    description: str
    handler: Callable[[Principal, dict[str, Any]], Any]
    required_args: frozenset[str] = frozenset()


@dataclass
class MCPInvocation:
    """Audit record for one tool call (plan §16.2, §10.3)."""

    invocation_id: str
    tool: str
    level: ActionSafetyLevel
    principal_ref: str
    profile: Profile
    case_id: str | None
    args_hash: str
    decision: str
    error_code: str | None = None
    at: datetime = field(default_factory=utc_now)


class ClarityMCPServer:
    """Tool registry, policy and audit over the case service."""

    def __init__(self, cases: MCPCaseView, *, ledger: AuditLedger | None = None) -> None:
        # Deliberately typed as the narrow view, not CaseService: this object
        # has no execute, confirm, approve or auto-fix method to call.
        self._cases = cases
        #: This process's own view of calls, kept for the denial-spike check.
        #: It is not the audit trail: ``ledger`` is (ADR-0034). Before W1 this
        #: list was the only record of an MCP call, and it lived and died with
        #: the MCP process where no dashboard could see it.
        self.audit: list[MCPInvocation] = []
        self._ledger = ledger
        self._tools: dict[str, ToolSpec] = {}
        self._register_tools()

    # ------------------------------------------------------------------ #
    # Registry
    # ------------------------------------------------------------------ #

    def _register_tools(self) -> None:
        read = ActionSafetyLevel.L1_READ
        everyone = frozenset({Profile.CUSTOMER_ASSIST, Profile.STAFF_ASSIST})
        staff = frozenset({Profile.STAFF_ASSIST})

        self._add(
            "get_case_timeline",
            read,
            everyone,
            "Evidence collected for a case, with per-source completeness.",
            self._get_case_timeline,
            {"case_id"},
        )
        self._add(
            "get_cause_assessment",
            read,
            everyone,
            "Ranked causes, what was ruled out, and the decision outcome.",
            self._get_cause_assessment,
            {"case_id"},
        )
        self._add(
            "explain_rule",
            read,
            everyone | {Profile.ANALYTICS},
            "What a cause rule checks and the policy basis for it.",
            self._explain_rule,
            {"rule_id"},
        )
        self._add(
            "get_trust_receipt",
            read,
            everyone,
            "The public view of a receipt issued for a case.",
            self._get_trust_receipt,
            {"case_id"},
        )
        self._add(
            "get_customer_safeguards",
            read,
            everyone,
            "Safeguards currently protecting the subscriber.",
            self._get_customer_safeguards,
            {"case_id"},
        )
        self._add(
            "get_network_status",
            read,
            everyone,
            "Coverage and outage state for the case's subscriber (simulated).",
            self._get_network_status,
            {"case_id"},
        )
        self._add(
            "search_knowledge",
            read,
            everyone | {Profile.ANALYTICS},
            (
                "Cited answers from the published rule catalogue. Every chunk "
                "carries its source and version, so an answer can be checked."
            ),
            self._search_knowledge,
            {"query"},
        )
        self._add(
            "request_handoff",
            ActionSafetyLevel.L2_LOW_RISK,
            everyone,
            "Route the case to a person, with a reason code.",
            self._request_handoff,
            {"case_id", "reason"},
        )
        self._add(
            "propose_action",
            ActionSafetyLevel.L3_FINANCIAL,
            everyone,
            (
                "Propose an action the decision already allows. Creates a pending "
                "plan only - it never executes, and it takes no amount."
            ),
            self._propose_action,
            {"case_id", "action_type"},
        )
        self._add(
            "get_desk_queue",
            read,
            staff,
            "Cases waiting for a person, ordered by money at stake.",
            self._get_desk_queue,
        )

    def _add(
        self,
        name: str,
        level: ActionSafetyLevel,
        profiles: frozenset[Profile],
        description: str,
        handler: Callable[[Principal, dict[str, Any]], Any],
        required: set[str] | None = None,
    ) -> None:
        self._tools[name] = ToolSpec(
            name=name,
            level=level,
            profiles=profiles,
            description=description,
            handler=handler,
            required_args=frozenset(required or set()),
        )

    def list_tools(self, profile: Profile) -> list[dict[str, str]]:
        """What a model is told it can do. Nothing outside this is callable."""
        return [
            {"name": spec.name, "level": spec.level.value, "description": spec.description}
            for spec in sorted(self._tools.values(), key=lambda s: s.name)
            if profile in spec.profiles
        ]

    # ------------------------------------------------------------------ #
    # Calling
    # ------------------------------------------------------------------ #

    def call(self, principal: Principal, tool: str, args: dict[str, Any] | None = None) -> Any:
        """Authorize, run and audit one tool call."""
        arguments = dict(args or {})
        spec = self._tools.get(tool)

        try:
            if spec is None:
                raise ToolDenied("UNKNOWN_TOOL", f"no tool named {tool!r}")
            self._authorize(principal, spec, arguments)
            result = spec.handler(principal, arguments)
        except ToolDenied as denied:
            self._record(principal, tool, spec, arguments, "denied", denied.code)
            raise
        except (CaseNotFound, CaseNotReady) as error:
            code = "CASE_NOT_FOUND" if isinstance(error, CaseNotFound) else "CASE_NOT_READY"
            self._record(principal, tool, spec, arguments, "error", code)
            raise ToolDenied(code, str(error)) from error
        except ToolLayerError as error:
            # The tool layer refused - e.g. the decision allows no action. That
            # is a denial like any other and must appear in the audit, because
            # a spike of them is the prompt-injection signal (plan §10.3).
            self._record(principal, tool, spec, arguments, "denied", error.code)
            raise ToolDenied(error.code, str(error)) from error

        self._record(principal, tool, spec, arguments, "allowed")
        return result

    def _authorize(self, principal: Principal, spec: ToolSpec, args: dict[str, Any]) -> None:
        if principal.profile not in spec.profiles:
            raise ToolDenied(
                "NOT_IN_PROFILE",
                f"{spec.name} is not available to the {principal.profile.value} profile",
            )

        missing = spec.required_args - set(args)
        if missing:
            raise ToolDenied("INVALID_ARGUMENTS", f"missing {', '.join(sorted(missing))}")

        if spec.level is ActionSafetyLevel.L4_BULK_ADMIN:
            # Belt and braces: no L4 tool is registered, and if one ever were,
            # it still could not be reached from here (plan §10.4).
            raise ToolDenied("LEVEL_NOT_EXPOSED", "bulk actions are never available over MCP")

        # Subject binding: a customer session may only touch its own case.
        #
        # The binding is required, not merely compared. An earlier version only
        # compared when `principal.case_id` was set, so a customer principal
        # with no binding passed straight through and could read every case in
        # the system. In-process that shape never arose, because the
        # orchestrator set the case on every principal it built; over the
        # network the binding comes from the token, so an external client can
        # present exactly that shape (A04, #8). Deny by default (I9).
        case_id = args.get("case_id")
        if principal.profile is Profile.CUSTOMER_ASSIST and case_id is not None:
            if principal.case_id is None:
                raise ToolDenied(
                    "SESSION_NOT_BOUND",
                    "a customer session must be bound to the case it is asking about",
                )
            if case_id != principal.case_id:
                raise ToolDenied("NOT_AUTHORISED_FOR_CASE", "this session is bound to another case")

        # An amount must never arrive from the model.
        if "amount" in args or "amount_lkr" in args:
            raise ToolDenied(
                "AMOUNT_NOT_ACCEPTED",
                "amounts come from the decision record, not from the caller",
            )

    def _record(
        self,
        principal: Principal,
        tool: str,
        spec: ToolSpec | None,
        args: dict[str, Any],
        decision: str,
        error_code: str | None = None,
    ) -> None:
        invocation = MCPInvocation(
            invocation_id=new_id("MCP"),
            tool=tool,
            level=spec.level if spec else ActionSafetyLevel.L1_READ,
            principal_ref=principal.ref,
            profile=principal.profile,
            case_id=args.get("case_id"),
            args_hash=hash_payload(args),
            decision=decision,
            error_code=error_code,
        )
        self.audit.append(invocation)
        if self._ledger is not None:
            # Arguments are hashed, never stored: an MCP client may put a
            # customer's words in them (I13).
            self._ledger.append(
                AuditEventType.MCP_INVOKED,
                actor_ref=principal.ref,
                actor_kind=ActorKind.AGENT,
                object_ref=tool,
                payload={"invocation_id": invocation.invocation_id, "args": args},
                case_id=invocation.case_id,
                detail={
                    "invocation_id": invocation.invocation_id,
                    "level": str(invocation.level),
                    "profile": str(invocation.profile),
                    "decision": decision,
                    "error_code": error_code,
                    "args_hash": invocation.args_hash,
                },
            )

    @property
    def denials(self) -> list[MCPInvocation]:
        """Watched for spikes: repeated denials can indicate injection (§10.3)."""
        return [row for row in self.audit if row.decision == "denied"]

    # ------------------------------------------------------------------ #
    # Tool handlers - all read from the case service, none execute
    # ------------------------------------------------------------------ #

    def _get_case_timeline(self, _: Principal, args: dict[str, Any]) -> dict[str, Any]:
        record = self._cases.get(str(args["case_id"]))
        snapshot = record.snapshot or self._cases.build_timeline(record.case_id)
        return {
            "case_id": record.case_id,
            "snapshot_hash": snapshot.snapshot_hash,
            "events": [
                {
                    "event_id": e.event_id,
                    "source": e.source.value,
                    "event_type": e.event_type.value,
                    "occurred_at": e.occurred_at.isoformat(),
                    "amount_lkr": None if e.amount_lkr is None else f"{e.amount_lkr:.2f}",
                }
                for e in snapshot.events
            ],
            "sources": {s.source.value: s.completeness.value for s in snapshot.sources},
        }

    def _get_cause_assessment(self, _: Principal, args: dict[str, Any]) -> dict[str, Any]:
        record = self._cases.get(str(args["case_id"]))
        if record.decision is None:
            raise CaseNotReady(f"case {record.case_id} has not been evaluated yet")
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
            "ruled_out": [c.rule_id for c in record.decision.ruled_out],
            "allowed_actions": [a.value for a in record.decision.allowed_actions],
            "rationale": record.decision.rationale,
        }

    def _explain_rule(self, _: Principal, args: dict[str, Any]) -> dict[str, Any]:
        rule_id = str(args["rule_id"])
        pack = next((p for p in self._cases.rule_packs() if p.rule_id == rule_id), None)
        if pack is None:
            raise ToolDenied("UNKNOWN_RULE", f"no rule named {rule_id}")
        return {
            "rule_id": pack.rule_id,
            "version": pack.version,
            "description": pack.description,
            "legal_basis": pack.legal_basis,
            "required_evidence": [s.value for s in pack.required_evidence],
            "allowed_actions": [a.value for a in pack.allowed_actions],
        }

    def _get_trust_receipt(self, _: Principal, args: dict[str, Any]) -> dict[str, Any]:
        record = self._cases.get(str(args["case_id"]))
        if record.receipt is None:
            raise CaseNotReady("no receipt has been issued for this case")
        return self._cases.receipt_public_view(record)

    def _get_customer_safeguards(self, _: Principal, args: dict[str, Any]) -> dict[str, Any]:
        record = self._cases.get(str(args["case_id"]))
        return {
            "case_id": record.case_id,
            "subscriber": record.case.customer.msisdn_masked,
            "safeguards": [
                a.type.value
                for a in (record.execution.actions if record.execution else [])
                if a.type
                in {
                    ActionType.BLOCK_MERCHANT_UNTIL_OPTIN,
                    ActionType.ENABLE_DATA_STOP,
                    ActionType.SET_SPEND_CAP,
                    ActionType.ENABLE_FUP_ALERTS,
                }
            ],
        }

    def _get_network_status(self, _: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """Coverage and outage state. Simulated and labelled as such (I16)."""
        case_id = str(args["case_id"])
        status = dict(self._cases.network_status(case_id))
        return {"case_id": case_id, **status}

    def _search_knowledge(self, _: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """Cited answers from the published rule catalogue.

        **Interim retrieval source.** The tool contract here is the final one
        from plan 07 section 11.1 (query in, cited chunks out), but the corpus
        is today's rule catalogue rather than the RAG service: catalogue, T&C,
        Gazette and help content land with K01-K03. Keeping the contract stable
        now means the backend can be swapped without touching this surface or
        any client.

        Two properties hold whatever the corpus is:

        * **Every chunk is cited.** The citation is the governed artefact,
          `rule_id@version`, which a reader can look up and check the text
          against. A rule's `legal_basis` rides along when the rule states one
          and is ``None`` otherwise, because a legal basis is quoted, never
          inferred (I16). K03 adds the citation verifier.
        * **The query is masked before it is recorded.** The query is text from
          a model, which may carry whatever the customer typed. Masking it here
          keeps an MSISDN or an NIC out of the audit row (I13).
        """
        raw = str(args["query"])
        masked = Masker().mask(raw)
        terms = [term for term in _words(masked.text.casefold()) if len(term) > 2]

        chunks: list[dict[str, Any]] = []
        for pack in self._cases.rule_packs():
            # Only published rules are public text. `load_packs` filters to
            # active, and this re-checks rather than trusting the caller's
            # loader flag, because a draft rule's text is not something to
            # quote to a customer.
            if pack.status.value != "active":
                continue
            if not pack.description:
                continue
            haystack = f"{pack.rule_id} {pack.description} {pack.category}".casefold()
            score = sum(1 for term in terms if term in haystack)
            if not score:
                continue
            chunks.append(
                {
                    "text": pack.description,
                    # The governed artefact is the citation: a reader can pull
                    # `rule_id@version` out of the catalogue and check the text
                    # against it. `legal_basis` is carried through when the rule
                    # states one, and is absent otherwise - a legal basis is
                    # never inferred or filled in (I16).
                    "source_id": f"{pack.rule_id}@{pack.version}",
                    "version": str(pack.version),
                    "legal_basis": pack.legal_basis,
                    "score": score,
                }
            )

        chunks.sort(key=lambda chunk: (-int(chunk["score"]), str(chunk["source_id"])))
        return {
            "query": masked.text,
            "chunks": chunks[:5],
            "corpus": "rule-catalogue",
        }

    def _request_handoff(self, principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        record = self._cases.get(str(args["case_id"]))
        return {
            "case_id": record.case_id,
            "status": "handoff_requested",
            "reason": str(args["reason"])[:200],
            "requested_by": principal.ref,
        }

    def _propose_action(self, principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """The strongest thing a model can do: ask, and wait to be confirmed."""
        case_id = str(args["case_id"])
        try:
            action = ActionType(str(args["action_type"]))
        except ValueError as error:
            raise ToolDenied("UNKNOWN_ACTION", f"no action type {args['action_type']!r}") from error

        plan = self._cases.propose(
            case_id, created_by=f"mcp:{principal.profile.value}", action_types=[action]
        )
        return {
            "plan_id": plan.plan_id,
            "case_id": plan.case_id,
            "status": plan.status.value,
            "summary": plan.display_summary,
            "amount_lkr": f"{plan.total_amount_lkr:.2f}",
            "note": (
                "Pending confirmation. This proposal does nothing until the customer "
                "confirms or a staff member approves it."
            ),
        }

    def _get_desk_queue(self, _: Principal, __: dict[str, Any]) -> list[dict[str, Any]]:
        waiting = [
            r for r in self._cases.all_cases() if r.decision is not None and r.execution is None
        ]
        waiting.sort(key=lambda r: r.case.money_at_stake_lkr or 0, reverse=True)
        return [
            {
                "case_id": r.case_id,
                "case_no": r.case.case_no,
                "outcome": r.decision.outcome.value if r.decision else None,
                "money_at_stake_lkr": (
                    None
                    if r.case.money_at_stake_lkr is None
                    else f"{r.case.money_at_stake_lkr:.2f}"
                ),
            }
            for r in waiting
        ]
