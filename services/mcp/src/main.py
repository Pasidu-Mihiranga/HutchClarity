"""clarity-mcp — resource server exposing 16 tools over simple REST."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _result_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def require_bearer(authorization: str | None = Header(default=None)) -> str:
    """OAuth stub: accept Bearer dev-token in lite profile."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = authorization.split(" ", 1)[1].strip()
    if token != "dev-token":
        raise HTTPException(status_code=401, detail="invalid token")
    return token


# --- Tool request models (extra=forbid) ------------------------------------ #


class GetCaseTimelineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    sources: list[str] | None = None
    event_types: list[str] | None = None
    window_hours: int | None = Field(default=None, ge=1, le=720)


class ExplainRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    version: str | None = None
    language: str = "en"


class SubscriberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriber_ref: str | None = None
    case_id: str | None = None


class GetTrustReceiptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str | None = None
    receipt_id: str | None = None


class ProposeActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    action_type: str
    idempotency_key: str = Field(min_length=1)


class GetUsageSummaryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriber_ref: str
    period: str = "current"


class GetPackDetailsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriber_ref: str | None = None
    offering_id: str | None = None


class GetVasSubscriptionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriber_ref: str


class GetTicketStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str | None = None
    ticket_id: str | None = None


class SearchKnowledgeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    language: str = "en"
    source_types: list[str] | None = None


class RunPolicyReplayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    version: str
    cohort: str = "demo"


class GetClusterSummaryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str = "7d"
    filters: dict[str, Any] = Field(default_factory=dict)


class GetShiftHandoverIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str = "cx"
    shift_window_hours: int = Field(default=8, ge=1, le=24)


class SendTemplatedNotificationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    template_id: str
    params: dict[str, str] = Field(default_factory=dict)


class ListOpenCasesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str | None = None
    status: str = "open"
    limit: int = Field(default=20, ge=1, le=100)


class VerifyReceiptChainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    case_id: str | None = None


RULE_CATALOGUE: dict[str, dict[str, Any]] = {
    "vas_silent_renewal": {
        "version": "1.0.0",
        "description": {
            "en": "A VAS renewed and charged without a recent OTP consent.",
            "si": "OTP අනුමතියකින් තොරව VAS අලුත් වී අය කෙරිණි.",
            "ta": "OTP ஒப்புதல் இல்லாமல் VAS புதுப்பிக்கப்பட்டு கட்டணம் வசூலிக்கப்பட்டது.",
        },
        "required_evidence": ["VAS_CHARGED", "subscription.otp_verified_at"],
        "citation": "Gazette T&C §VAS-consent",
    },
    "fup_surprise": {
        "version": "1.0.0",
        "description": {
            "en": "Speed throttled after FUP cap without prior disclosure.",
            "si": "FUP සීමාවෙන් පසු වේගය අඩු විය.",
            "ta": "FUP வரம்புக்குப் பிறகு வேகம் குறைக்கப்பட்டது.",
        },
        "required_evidence": ["USAGE_THRESHOLD", "pack.fup_disclosed"],
        "citation": "Catalogue FUP label",
    },
}


class McpState:
    def __init__(self) -> None:
        self.invocations: list[dict[str, Any]] = []
        self.proposals: dict[str, dict[str, Any]] = {}  # idempotency_key -> proposal
        self.cases: list[dict[str, Any]] = [
            {
                "case_id": "CASE-DEMO-001",
                "status": "open",
                "subscriber_ref": "sub_dilani_demo",
                "cause": "vas_silent_renewal",
                "amount_lkr": "49.00",
                "opened_at": "2026-10-01T14:18:00+00:00",
            }
        ]
        self.timeline: dict[str, list[dict[str, Any]]] = {
            "CASE-DEMO-001": [
                {
                    "id": "EVT-VAS-1",
                    "source": "vas",
                    "type": "VAS_CHARGED",
                    "at": "2026-10-01T14:06:00+00:00",
                    "amount_lkr": "49.00",
                },
                {
                    "id": "EVT-BAL-1",
                    "source": "billing",
                    "type": "BALANCE_DEBIT",
                    "at": "2026-10-01T14:06:00+00:00",
                    "amount_lkr": "49.00",
                },
            ]
        }


def create_app() -> FastAPI:
    app = FastAPI(title="clarity-mcp", version="0.1.0")
    state = McpState()
    app.state.mcp = state

    def audit(tool: str, args: dict[str, Any], result: Any, *, decision: str = "allow") -> dict[str, Any]:
        record = {
            "invocation_id": str(uuid.uuid4()),
            "tool": tool,
            "args_hash": _result_hash(args),
            "result_hash": _result_hash(result),
            "decision": decision,
            "at": _utcnow(),
        }
        state.invocations.append(record)
        return record

    def tool_endpoint(name: str, model: type[BaseModel], handler: Callable[[Any], Any]) -> None:
        def _route(
            payload: dict[str, Any] = Body(...),
            _token: str = Depends(require_bearer),
        ) -> dict[str, Any]:
            try:
                body = model.model_validate(payload)
            except ValidationError as exc:
                audit(name, payload, {"error": exc.errors()}, decision="deny")
                raise HTTPException(status_code=422, detail=exc.errors()) from exc
            args = body.model_dump()
            try:
                result = handler(body)
            except HTTPException as exc:
                audit(name, args, {"error": exc.detail}, decision="deny")
                raise
            inv = audit(name, args, result)
            return {"ok": True, "tool": name, "result": result, "invocation": inv}

        _route.__name__ = f"tool_{name}"
        _route.__doc__ = f"MCP tool {name}"
        app.add_api_route(f"/tools/{name}", _route, methods=["POST"], tags=["tools"])

    # --- Handlers ---------------------------------------------------------- #

    def get_case_timeline(body: GetCaseTimelineIn) -> dict[str, Any]:
        events = list(state.timeline.get(body.case_id, []))
        if body.sources:
            events = [e for e in events if e.get("source") in body.sources]
        if body.event_types:
            events = [e for e in events if e.get("type") in body.event_types]
        sources_seen = {e.get("source") for e in events}
        completeness = {s: "complete" for s in sources_seen} or {"none": "empty"}
        return {
            "case_id": body.case_id,
            "events": events,
            "completeness": completeness,
            "snapshot_hash": _result_hash(events),
        }

    def explain_rule(body: ExplainRuleIn) -> dict[str, Any]:
        rule = RULE_CATALOGUE.get(body.rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="unknown rule_id")
        version = body.version or rule["version"]
        desc = rule["description"].get(body.language) or rule["description"]["en"]
        return {
            "rule_id": body.rule_id,
            "version": version,
            "language": body.language,
            "description": desc,
            "required_evidence": rule["required_evidence"],
            "citation": rule["citation"],
        }

    def get_customer_safeguards(body: SubscriberIn) -> dict[str, Any]:
        return {
            "subscriber_ref": body.subscriber_ref or "bound",
            "safeguards": [
                {"type": "spend_cap", "value": "500", "currency": "LKR"},
                {"type": "data_on_expiry", "value": "stop"},
            ],
        }

    def get_trust_receipt(body: GetTrustReceiptIn) -> dict[str, Any]:
        rid = body.receipt_id or f"TR-{ (body.case_id or 'DEMO')[-6:] }"
        return {
            "receipt_id": rid,
            "case_id": body.case_id or "CASE-DEMO-001",
            "status": "issued",
            "public": {
                "cause": "vas_silent_renewal",
                "amount_lkr": "49.00",
                "verification": "pending_chain_check",
            },
        }

    def propose_action(body: ProposeActionIn) -> dict[str, Any]:
        existing = state.proposals.get(body.idempotency_key)
        if existing:
            return existing
        proposal = {
            "proposal_id": f"PROP-{uuid.uuid4().hex[:8].upper()}",
            "case_id": body.case_id,
            "action_type": body.action_type,
            "status": "pending",
            "idempotency_key": body.idempotency_key,
            "display": f"Propose {body.action_type} for {body.case_id}",
        }
        state.proposals[body.idempotency_key] = proposal
        return proposal

    def get_usage_summary(body: GetUsageSummaryIn) -> dict[str, Any]:
        return {
            "subscriber_ref": body.subscriber_ref,
            "period": body.period,
            "buckets": [
                {"name": "data_gb", "used": "9.2", "cap": "10.0"},
                {"name": "voice_min", "used": "12", "cap": None},
            ],
            "thresholds_crossed": ["data_80pct"],
            "throttle_state": "none",
        }

    def get_pack_details(body: GetPackDetailsIn) -> dict[str, Any]:
        return {
            "offerings": [
                {
                    "offering_id": body.offering_id or "PKG-ANY-10",
                    "name": "Anytime 10GB",
                    "cap": "10GB",
                    "after_cap_speed": "512 kbps",
                    "apps": ["any"],
                    "validity": "30d",
                    "catalogue_version": "2027.08",
                    "truth_label": "FUP disclosed at purchase",
                }
            ]
        }

    def get_vas_subscriptions(body: GetVasSubscriptionsIn) -> dict[str, Any]:
        return {
            "subscriber_ref": body.subscriber_ref,
            "subscriptions": [
                {
                    "merchant": "GameHub",
                    "product": "Daily game subscription",
                    "price_lkr": "49.00",
                    "consent": {"otp_verified": False, "at": None, "channel": None},
                }
            ],
        }

    def get_ticket_status(body: GetTicketStatusIn) -> dict[str, Any]:
        case_id = body.case_id or body.ticket_id or "CASE-DEMO-001"
        match = next((c for c in state.cases if c["case_id"] == case_id), None)
        if match is None and body.ticket_id:
            match = {"case_id": case_id, "status": "unknown"}
        if match is None:
            raise HTTPException(status_code=404, detail="case not found")
        return {
            "case_id": match["case_id"],
            "status": match.get("status", "open"),
            "owner_role": "auto",
            "sla": "P1-4h",
            "last_update": match.get("opened_at") or _utcnow(),
        }

    def search_knowledge(body: SearchKnowledgeIn) -> dict[str, Any]:
        chunks = [
            {
                "text": "VAS renewals require OTP consent within the policy window.",
                "source_id": "tc-vas-consent",
                "version": "2026.09",
                "effective_date": "2026-09-01",
                "url": "https://example.invalid/tc/vas",
            }
        ]
        if body.source_types:
            chunks = [c for c in chunks if c["source_id"].split("-")[0] in body.source_types or True]
        return {"query": body.query, "language": body.language, "chunks": chunks}

    def run_policy_replay(body: RunPolicyReplayIn) -> dict[str, Any]:
        return {
            "rule_id": body.rule_id,
            "version": body.version,
            "cohort": body.cohort,
            "outcome_deltas": {"auto_fix": 2, "handoff": -1},
            "sample_cases": ["CASE-DEMO-001"],
        }

    def get_cluster_summary(body: GetClusterSummaryIn) -> dict[str, Any]:
        return {
            "period": body.period,
            "filters": body.filters,
            "clusters": [
                {
                    "label": "VAS no-OTP",
                    "size": 14,
                    "trend": "up",
                    "linked_rules": ["vas_silent_renewal"],
                }
            ],
        }

    def get_shift_handover_data(body: GetShiftHandoverIn) -> dict[str, Any]:
        return {
            "team": body.team,
            "shift_window_hours": body.shift_window_hours,
            "open_cases": [c for c in state.cases if c.get("status") == "open"],
            "promises": [],
            "owners": [{"role": "supervisor", "ref": "desk-lead-1"}],
        }

    def send_templated_notification(body: SendTemplatedNotificationIn) -> dict[str, Any]:
        # Template-only: free text not allowed (params are scalar strings).
        return {
            "message_id": f"MSG-{uuid.uuid4().hex[:8].upper()}",
            "case_id": body.case_id,
            "template_id": body.template_id,
            "params": body.params,
            "status": "queued",
        }

    def list_open_cases(body: ListOpenCasesIn) -> dict[str, Any]:
        if body.case_id:
            match = next((c for c in state.cases if c["case_id"] == body.case_id), None)
            if match is None:
                raise HTTPException(status_code=404, detail="case not found")
            return {"case": match}
        cases = [c for c in state.cases if c.get("status") == body.status][: body.limit]
        return {"cases": cases}

    def verify_receipt_chain(body: VerifyReceiptChainIn) -> dict[str, Any]:
        return {
            "receipt_id": body.receipt_id,
            "case_id": body.case_id,
            "chain_valid": True,
            "links_checked": 2,
            "alg": "Ed25519",
            "note": "stub verification against in-memory chain",
        }

    tool_endpoint("get_case_timeline", GetCaseTimelineIn, get_case_timeline)
    tool_endpoint("explain_rule", ExplainRuleIn, explain_rule)
    tool_endpoint("get_customer_safeguards", SubscriberIn, get_customer_safeguards)
    tool_endpoint("get_trust_receipt", GetTrustReceiptIn, get_trust_receipt)
    tool_endpoint("propose_action", ProposeActionIn, propose_action)
    tool_endpoint("get_usage_summary", GetUsageSummaryIn, get_usage_summary)
    tool_endpoint("get_pack_details", GetPackDetailsIn, get_pack_details)
    tool_endpoint("get_vas_subscriptions", GetVasSubscriptionsIn, get_vas_subscriptions)
    tool_endpoint("get_ticket_status", GetTicketStatusIn, get_ticket_status)
    tool_endpoint("search_knowledge", SearchKnowledgeIn, search_knowledge)
    tool_endpoint("run_policy_replay", RunPolicyReplayIn, run_policy_replay)
    tool_endpoint("get_cluster_summary", GetClusterSummaryIn, get_cluster_summary)
    tool_endpoint("get_shift_handover_data", GetShiftHandoverIn, get_shift_handover_data)
    tool_endpoint("send_templated_notification", SendTemplatedNotificationIn, send_templated_notification)
    tool_endpoint("list_open_cases", ListOpenCasesIn, list_open_cases)
    tool_endpoint("verify_receipt_chain", VerifyReceiptChainIn, verify_receipt_chain)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "mcp",
            "tools": 16,
            "invocations": len(state.invocations),
        }

    @app.get("/v1/invocations")
    def invocations(_token: str = Depends(require_bearer)) -> dict[str, Any]:
        return {"invocations": state.invocations}

    @app.get("/resources/ui/why-card")
    def why_card(_token: str = Depends(require_bearer)) -> dict[str, Any]:
        return {
            "type": "ui/why-card",
            "title": "Why was I charged?",
            "fields": ["cause", "amount_lkr", "evidence", "safeguard"],
            "template": "why-card-v1",
        }

    @app.get("/resources/ui/receipt")
    def receipt_card(_token: str = Depends(require_bearer)) -> dict[str, Any]:
        return {
            "type": "ui/receipt",
            "title": "Trust receipt",
            "fields": ["receipt_id", "cause", "actions", "verification"],
            "template": "receipt-card-v1",
        }

    return app


app = create_app()
