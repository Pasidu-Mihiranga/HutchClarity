"""The Clarity HTTP API (plan §17).

Serves the customer **Why?** journey, the public receipt verification page and
the Clarity Desk queue from one core, so every channel gets the same answer:
the point of the whole system (deck S2: "The same answer on every channel").

Two deliberate differences from plan §17.2, both tightening rather than
loosening it:

- **Confirmation tokens never leave the server.** §17.2 shows an
  ``X-Confirmation-Token`` header for a channel that mints its own. Here the
  authenticated tap is the confirmation, and the token is minted and spent
  inside the request, so it cannot be captured or replayed.
- **Amounts are never accepted from a client.** They come from the decision.

Authentication is **not implemented**: the prototype trusts the caller
(Guidelines §4). Production puts customer OTP/JWT and staff SSO in front of
these routes exactly as plan §19 describes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.responses import Response as RawResponse
from pydantic import TypeAdapter
from starlette.exceptions import HTTPException as StarletteHTTPException

from clarity.app.container import Clarity, Profile
from clarity.contracts.case import CaseState
from clarity.contracts.decision import Outcome, PlanStatus
from clarity.contracts.timeline import EventType
from clarity.integration.drivers.mock.world import CATALOGUE, ref_for
from clarity.interfaces.http import autopsy_api, csrf, staff_sso, trail
from clarity.interfaces.http.auth import (
    ANONYMOUS,
    CurrentPrincipal,
    Permission,
    Principal,
    authorize_action,
    authorize_case_access,
    customer_can_act,
    principal_from,
    public,
    requires,
)
from clarity.interfaces.http.cookies import CUSTOMER_COOKIE
from clarity.interfaces.http.deps import ClarityDep, get_clarity, set_clarity
from clarity.interfaces.http.headers import security_headers
from clarity.interfaces.http.schemas import (
    ActionView,
    AlertDisposal,
    ApproveRequest,
    AuditGrantRequest,
    AuditGrantRevoke,
    BreakGlassRequest,
    CandidateConfirmRequest,
    CaseSummary,
    CauseView,
    ConfirmRequest,
    DecisionView,
    DemoSubscriber,
    ExecutionView,
    FamilyRequest,
    ForesightRunRequest,
    LaunchRecordRequest,
    MerchantSuspendRequest,
    OpenCaseRequest,
    OtpRequest,
    OtpVerify,
    OutcomeRecordRequest,
    PendingApprovalView,
    PlanView,
    PolicyDraftRequest,
    PolicyReviewRequest,
    PolicyRollbackRequest,
    PolicyScheduleRequest,
    PreferencesRequest,
    ProposeRequest,
    QueueItem,
    RefreshRequest,
    ReloadRequest,
    RuledOutView,
    SafeguardRequest,
    ScenarioDraftRequest,
    ScenarioReviseRequest,
    SessionView,
    SourceStatusView,
    StaffLogin,
    StaffSignIn,
    SwitchFlipRequest,
    TimelineEventView,
    TimelineView,
    VerificationView,
)
from clarity.interfaces.http.throttle import (
    ANONYMOUS_FALLBACK,
    ANONYMOUS_KEY,
    FALLBACK_LIMIT,
    rate_limit,
)
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import Language, mask_msisdn, normalise_msisdn, utc_now
from clarity.kernel.ids import new_id
from clarity.modules.actions.public import ToolLayerError
from clarity.modules.assurance.public import (
    Alert,
    AlertNotFound,
    AlertRefused,
    Disposition,
)
from clarity.modules.case.public import CaseNotFound, CaseNotReady, CaseRecord
from clarity.modules.foresight.public import (
    AlreadyConfirmed,
    CatalogueInvalid,
    ChangeType,
    DetectedSpike,
    ForesightReport,
    OutcomeCandidate,
    PostLaunchComparison,
    Provenance,
    RealLaunchNotPermitted,
    RunAlreadyFinished,
    Scenario,
    ScenarioRun,
    ScenarioVersion,
    StoredCalibration,
    StoredLaunch,
    UnknownScenario,
    VolumeBand,
)
from clarity.modules.governance.public import ChangeRefused, ImpactReport, PolicyChange
from clarity.modules.iam.public import (
    AuditGrant,
    GrantNotFound,
    GrantRefused,
    HttpSmsDeliveryFailed,
    LoginRefused,
    OtpRefused,
    RoutedOtpDelivery,
    SimulatedInbox,
    SubjectKind,
    TokenInvalid,
)
from clarity.modules.knowledge.public import Audience as KnowledgeAudience
from clarity.platform.audit.checkpoints import anchor_verifies, checkpoint_document
from clarity.platform.audit.export import AuditExport, export_document
from clarity.platform.audit.ledger import ActorKind, AuditEventType, record_hash
from clarity.platform.config.artefacts import PolicyValue, Scope
from clarity.platform.config.switches import Switch
from clarity.platform.messaging.correlation import correlated
from clarity.platform.observability import current_trace_id, span
from clarity.platform.security.principal import Assurance, Role

#: HTTP status per tool-layer refusal. Refusals are expected outcomes of a
#: guard working, not server faults, so none of them are 5xx.
_STATUS_FOR_CODE = {
    "ACTION_NOT_ALLOWED_BY_POLICY": 403,
    "OUTCOME_NOT_EXECUTABLE": 409,
    "CONFIRMATION_REQUIRED": 403,
    "CONFIRMATION_INVALID": 403,
    "APPROVAL_REQUIRED": 403,
    "BUDGET_EXHAUSTED": 409,
    "PLAN_NOT_FOUND": 404,
    "PLAN_NOT_PENDING": 409,
    "EXECUTION_FAILED": 502,
}

#: ISO 8601 durations in request bodies, such as ``P30D``.
_DURATION_ADAPTER: TypeAdapter[timedelta] = TypeAdapter(timedelta)

_log = logging.getLogger("clarity.audit.grants")
_throttle_log = logging.getLogger("clarity.http.throttle")
_stream_log = logging.getLogger("clarity.conversation.stream")

# `get_clarity` and `ClarityDep` live in `deps` so the sign-in router can ask
# for the core without importing this module, which imports it.


#: The header a caller may send to join its own trace, and the one every
#: response carries back so a support agent can quote it.
CORRELATION_HEADER = "X-Correlation-Id"


async def _trace_requests(request: Request, call_next: Any) -> Response:
    """One span per request, and one correlation id for everything it causes.

    The id comes from the caller when it sends one, so a trace can start in the
    app or the channel gateway and continue here, and is returned on the
    response so the id in a customer's support ticket is the id in the trace.
    """
    correlation_id = request.headers.get(CORRELATION_HEADER) or new_id("REQ")
    with (
        correlated(correlation_id),
        span(
            "http.request",
            **{
                "http.method": request.method,
                "http.route": request.url.path,
                "clarity.correlation_id": correlation_id,
            },
        ) as current,
    ):
        response: Response = await call_next(request)
        current.set_attribute("http.status_code", response.status_code)
        response.headers[CORRELATION_HEADER] = correlation_id
        if trace_id := current_trace_id():
            response.headers["X-Trace-Id"] = trace_id
        return response


async def _audit_requests(request: Request, call_next: Any) -> Response:
    """Record who made every state-changing request, and which staff read whom.

    Runs after the handler, when routing has filled in the route template and
    path parameters, so the record names ``POST /v1/cases/{case_id}/approve``
    and the case rather than a raw URL. 401 and 403 are left to the refusal
    handler, which records them with the reason.

    A staff ``GET`` on a route naming one subject is recorded too, as
    ``data.read`` (audit assurance plan 5.5): without it nothing distinguishes
    an agent working their queue from one reading a neighbour's bill, which is
    what the ``snooping`` rule counts. ``trail.records_data_read`` says which
    reads qualify and why the rest are left out.

    **Not fail closed.** This record is written after the handler committed,
    so a failure here turns the response into an error but cannot undo the
    change. The domain events a money path publishes are atomic with it
    (ADR-0034); this record adds who asked, which they cannot carry.
    """
    response: Response = await call_next(request)
    route = getattr(request.scope.get("route"), "path", None)
    if route is None or response.status_code in {401, 403}:
        return response

    writes = trail.records_request(request.method, route)
    if not writes and request.method != "GET":
        return response

    token = trail.bearer_token(request)
    principal = ANONYMOUS
    if token:
        try:
            principal = principal_from(request, request.headers.get("authorization"))
        except StarletteHTTPException:
            principal = ANONYMOUS
    if not writes and not trail.records_data_read(request.method, route, principal):
        return response

    trail.record(
        get_clarity(),
        AuditEventType.REQUEST_PERFORMED if writes else AuditEventType.DATA_READ,
        actor_ref=principal.ref,
        actor_kind=trail.actor_kind_of(principal),
        session_ref=trail.session_ref_for(token),
        object_ref=f"{request.method} {route}",
        detail={
            "status": response.status_code,
            "roles": sorted(role.value for role in principal.roles),
            "assurance": principal.assurance.value,
            "path_params": dict(request.path_params),
        },
        case_id=request.path_params.get("case_id"),
    )
    return response


async def _sweep_grant_endings(stop: asyncio.Event) -> None:
    """Record expired and lapsed grants on a schedule (audit assurance Phase 3).

    The trail's own scheduler, with no new infrastructure: one loop per server
    process, on ``audit.grant.sweep_interval``. Every authenticated request
    also records endings first, so this loop is what covers the quiet hours
    when nobody signs in. A failed sweep is logged and retried on the next
    tick: it must never take the server down, and a claim it could not record
    is released for the next attempt.
    """
    while not stop.is_set():
        try:
            interval = get_clarity().grant_sweep_interval().total_seconds()
        except Exception:  # policy unreadable: fall back, keep sweeping
            _log.exception("could not resolve audit.grant.sweep_interval; using 60s")
            interval = 60.0
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(interval, 1.0))
            return
        except TimeoutError:
            pass
        try:
            await run_in_threadpool(get_clarity().audit_grants.record_endings)
        except Exception:
            _log.exception("recording grant endings failed; retrying next sweep")


async def _run_detection(stop: asyncio.Event) -> None:
    """Run risk detection over the trail on a schedule (Phase 4, ADR-0037).

    Liveness is checked *before* each run, not inside it: a loop that has
    stopped cannot report that it stopped, so the check has to see the
    heartbeat from the outside. One failed run is logged and retried on the
    next tick; a run that keeps failing stops the heartbeat, and the liveness
    check turns that silence into a critical alert.
    """
    while not stop.is_set():
        try:
            interval = get_clarity().assurance.sweep_interval().total_seconds()
        except Exception:
            _log.exception("could not resolve assurance.detection.interval; using 300s")
            interval = 300.0
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(interval, 1.0))
            return
        except TimeoutError:
            pass
        try:
            await run_in_threadpool(get_clarity().assurance.check_liveness)
            await run_in_threadpool(get_clarity().assurance.run)
        except Exception:
            _log.exception("risk detection failed; retrying next interval")


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    stop = asyncio.Event()
    background = [
        asyncio.create_task(_sweep_grant_endings(stop)),
        asyncio.create_task(_run_detection(stop)),
    ]
    try:
        yield
    finally:
        stop.set()
        for task in background:
            await task


def create_app(clarity: Clarity | None = None) -> FastAPI:
    if clarity is not None:
        set_clarity(clarity)

    app = FastAPI(
        lifespan=_lifespan,
        title="Hutch Clarity API",
        version="0.1.0",
        description=(
            "Explain every rupee. Fix it by rule. Prove it won't happen again. "
            "PROTOTYPE: all HUTCH systems are mocked and all data is synthetic."
        ),
    )
    # Pinned to the origins this deployment actually serves, and credentials
    # are allowed, because the staff console now authenticates with a cookie
    # (B1). `allow_origins=["*"]` cannot carry credentials at all under the
    # CORS spec, so the wildcard was not merely loose, it would have silently
    # broken cookie-borne sign-in. A deployment sets CLARITY_ALLOWED_ORIGINS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(clarity or get_clarity()),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(_audit_requests)
    app.middleware("http")(_trace_requests)
    # Outermost, so it also covers error responses and static files (X01).
    app.middleware("http")(security_headers)
    # Authentication and authorization are profile-selected drivers. Lite uses
    # local JWT/Python drivers; full may use Keycloak and OPA.
    core = clarity or get_clarity()

    # Rate limiting (A8). Inside the security headers and the trace, so a 429
    # is still a recorded, header-complete response, and outside the route so
    # the pipeline is never entered for a refused call.
    def _limit_for(policy_key: str, at: datetime) -> int:
        try:
            return int(core.policies.resolve(policy_key, as_of=at))
        except Exception:
            _throttle_log.warning("rate limit %s unresolved; using the default", policy_key)
            return ANONYMOUS_FALLBACK if policy_key == ANONYMOUS_KEY else FALLBACK_LIMIT

    app.middleware("http")(rate_limit(core.rate_limiter, _limit_for, core.case_aggregate._now))

    # CSRF, for requests relying on a cookie (B4). Inside the rate limiter, so
    # a flood of forged requests is still throttled before it is inspected.
    app.middleware("http")(csrf.enforce())

    app.state.token_verifier = core.token_verifier
    app.state.authorization_policy = core.authorization
    app.state.audit_grants = core.audit_grants
    _register_handlers(app)
    _register_routes(app)
    return app


# --------------------------------------------------------------------------- #
# Error handling (RFC 9457 problem details, plan §17.1)
# --------------------------------------------------------------------------- #


def _problem(status: int, title: str, detail: str, code: str | None = None) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if code:
        body["code"] = code
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


def _register_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _audited_refusal(request: Request, error: StarletteHTTPException) -> Response:
        """Record refusals in the trail, then answer exactly as before (W2).

        403 always: a signed-in caller was refused something. 401 only when a
        token was presented and rejected: forged, expired or revoked. An
        anonymous request with no token is the ordinary state of the public
        internet and would bury the signal.
        """
        token = trail.bearer_token(request)
        if error.status_code == 403 or (error.status_code == 401 and token):
            principal = ANONYMOUS
            if token:
                try:
                    principal = principal_from(request, request.headers.get("authorization"))
                except StarletteHTTPException:
                    principal = ANONYMOUS
            known = principal is not ANONYMOUS
            trail.record(
                get_clarity(),
                AuditEventType.ACCESS_DENIED
                if error.status_code == 403
                else AuditEventType.TOKEN_REJECTED,
                actor_ref=principal.ref if known else "unknown",
                actor_kind=trail.actor_kind_of(principal),
                session_ref=trail.session_ref_for(token),
                object_ref=trail.route_of(request),
                detail={
                    "status": error.status_code,
                    "reason": str(error.detail),
                    "roles": sorted(role.value for role in principal.roles),
                    "assurance": principal.assurance.value,
                },
                case_id=request.path_params.get("case_id"),
            )
        return await http_exception_handler(request, error)

    @app.exception_handler(ToolLayerError)
    async def _tool_error(_: Request, error: ToolLayerError) -> JSONResponse:
        status = _STATUS_FOR_CODE.get(error.code, 409)
        return _problem(status, "Action refused", str(error), error.code)

    @app.exception_handler(CaseNotFound)
    async def _case_missing(_: Request, error: CaseNotFound) -> JSONResponse:
        return _problem(404, "Case not found", str(error), "CASE_NOT_FOUND")

    @app.exception_handler(CaseNotReady)
    async def _case_not_ready(_: Request, error: CaseNotReady) -> JSONResponse:
        return _problem(409, "Case not ready", str(error), "CASE_NOT_READY")

    @app.exception_handler(ChangeRefused)
    async def _policy_refused(_: Request, error: ChangeRefused) -> JSONResponse:
        return _problem(409, "Policy change refused", str(error), error.code)


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #


def _case_summary(record: CaseRecord) -> CaseSummary:
    case = record.case
    return CaseSummary(
        case_id=case.case_id,
        case_no=case.case_no,
        state=case.state.value,
        channel=case.origin_channel,
        language=case.language,
        msisdn_masked=case.customer.msisdn_masked,
        money_at_stake_lkr=case.money_at_stake_lkr,
        opened_at=case.opened_at,
    )


def _policy_change_view(change: PolicyChange) -> dict[str, Any]:
    return {
        "change_id": change.change_id,
        "key": change.key,
        "candidate": change.candidate.model_dump(mode="json"),
        "change_class": change.change_class.value,
        "maker_ref": change.maker_ref,
        "state": change.state.value,
        "reason": change.reason,
        "approvals_needed": change.approvals_needed,
        "approvals": [
            {
                "approver_ref": approval.approver_ref,
                "role": approval.role,
                "at": approval.at.isoformat(),
                "mfa_step_up": approval.mfa_step_up,
            }
            for approval in change.approvals
        ],
        "impact": None
        if change.impact is None
        else {
            "cases_evaluated": change.impact.cases_evaluated,
            "changed": change.impact.changed,
            "money_delta_lkr": str(change.impact.money_delta_lkr),
            "candidate_summary": change.impact.candidate_summary,
        },
        "scheduled_for": change.scheduled_for,
        "activated_at": change.activated_at,
        "supersedes": change.supersedes,
    }


def _decision_view(record: CaseRecord, clarity: Clarity | None = None) -> DecisionView:
    decision = record.decision
    if decision is None:
        raise CaseNotReady(f"case {record.case_id} has not been evaluated yet")

    evaluation = record.evaluation
    top = evaluation.top if evaluation else None

    # The wording is generated last, from the decision that is already made,
    # and is verified before it is returned (deck S7).
    answer = (
        clarity.ai.explain(
            decision,
            rule_id=top.assessment.rule_id if top else None,
            language=record.case.language,
        )
        if clarity is not None
        else None
    )

    return DecisionView(
        case_id=record.case_id,
        decision_id=decision.decision_id,
        outcome=decision.outcome,
        amount_lkr=decision.amount_lkr,
        cause=(
            CauseView(
                rule_id=top.assessment.rule_id,
                rule_version=top.assessment.rule_version,
                confidence=float(top.assessment.confidence),
                category=top.assessment.category,
                money_effect_lkr=top.assessment.money_effect_lkr,
                evidence_refs=top.assessment.evidence_refs,
            )
            if top
            else None
        ),
        ruled_out=[RuledOutView(rule_id=c.rule_id, reason=c.reason) for c in decision.ruled_out],
        unknown=[
            RuledOutView(rule_id=c.rule_id, reason=c.reason)
            for c in (evaluation.indeterminate if evaluation else [])
        ],
        allowed_actions=decision.allowed_actions,
        rationale=decision.rationale,
        handoff_reason=decision.handoff_reason.value if decision.handoff_reason else None,
        policy_version=decision.policy_version,
        explanation=answer.text if answer else "",
        explanation_source=answer.tier.value if answer else "template",
        requires_confirmation=decision.requires_customer_confirmation,
        requires_approval=decision.requires_staff_approval,
    )


def _allowed_origins(clarity: Clarity) -> list[str]:
    """Which browser origins may call this API with credentials.

    The console and the customer app are separate origins from the API, so
    there has to be a list. It is configuration rather than a constant because
    the three apps move between ports in development and hosts in deployment,
    and a hardcoded origin is how a deployment ends up adding the wildcard
    back.
    """
    configured = clarity.settings.allowed_origins
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    console = clarity.settings.console_base_url.rstrip("/")
    if console and console not in origins:
        origins.append(console)
    return origins


def demo_only(clarity: ClarityDep) -> None:
    """Refuse a prototype-only route outside synthetic profiles.

    `/v1/demo/inbox` hands out OTP codes, so it must not exist where subscribers
    are real. DEMO and FULL both run synthetic Hutch data; only PROD is gated.
    """
    if clarity.profile is Profile.PROD:
        raise HTTPException(status_code=404, detail="not found")


def _authorize_receipt_access(principal: Principal, receipt: Any) -> None:
    """Subject binding for receipts.

    A receipt holds only a hash of the subscriber reference, so ownership is
    checked by hashing the principal's own reference the same way rather than
    by storing the number on the receipt.
    """
    if principal.has(Permission.RECEIPT_READ_ANY):
        return
    owned = {principal.subscriber_ref, *principal.delegations} - {None}
    if receipt.payload.subject.subscriber_ref_hash not in {hash_payload(ref) for ref in owned}:
        raise HTTPException(status_code=403, detail="this account may not read that receipt")


#: Context keys a client may contribute to a turn's facts.
#:
#: Deliberately no figures. The facts a turn is composed from are also the set
#: the verifier checks the reply against, so a client that could add
#: `amount_lkr` could have its own number quoted back to it as though Clarity
#: had agreed to it. These three are UI selections (which product is being
#: discussed, which chip was tapped, which safeguard was chosen), not money.
_CLIENT_CONTEXT_KEYS = frozenset({"product", "chat_intent", "safeguard"})


def _client_context(facts: dict[str, Any]) -> dict[str, Any]:
    """The part of a client's facts that may influence a turn."""
    return {
        key: value
        for key, value in facts.items()
        if key in _CLIENT_CONTEXT_KEYS and isinstance(value, str)
    }


def _case_facts(record: Any) -> dict[str, Any]:
    """The authoritative facts for a turn, read from the case itself.

    This is what the flow's conditions are evaluated against and what the
    verifier checks the reply's figures against, so every value here comes from
    a system record (I2) and none of it from the request.
    """
    decision = record.decision
    pending = [
        plan_id
        for plan_id, plan in (record.plans or {}).items()
        if plan.status is PlanStatus.PENDING_CONFIRMATION
    ]
    facts: dict[str, Any] = {
        "case_id": record.case_id,
        "decision_outcome": decision.outcome.value if decision is not None else None,
        "plan_id": pending[0] if pending else None,
        "receipt_id": record.receipt.receipt_id if record.receipt is not None else None,
        "citations": [],
    }
    if decision is not None:
        # The amount the decision settled on, which is the only amount a reply
        # may quote (I1).
        amount = getattr(decision, "amount_lkr", None)
        if amount is not None:
            facts["amount_lkr"] = str(amount)
        if decision.top_cause_ref is not None:
            facts["rule_id"] = decision.top_cause_ref
    return facts


def _plan_view(plan: Any) -> PlanView:
    return PlanView(
        plan_id=plan.plan_id,
        case_id=plan.case_id,
        outcome=plan.outcome,
        summary=plan.display_summary,
        actions=plan.action_types,
        total_amount_lkr=plan.total_amount_lkr,
        status=plan.status.value,
    )


def _execution_view(record: CaseRecord, plan_id: str) -> ExecutionView:
    execution = record.execution
    assert execution is not None
    return ExecutionView(
        case_id=record.case_id,
        plan_id=plan_id,
        status=execution.status.value,
        confirmed_by=execution.confirmed_by.value,
        actions=[
            ActionView(
                action_id=a.action_id,
                type=a.type,
                amount_lkr=a.amount_lkr,
                before={k: str(v) for k, v in a.before_state.items()},
                after={k: str(v) for k, v in a.after_state.items()},
                status=a.status.value,
            )
            for a in execution.actions
        ],
        receipt_id=record.receipt.receipt_id if record.receipt else None,
        verify_url=record.receipt.verify_url if record.receipt else None,
    )


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


def _register_routes(app: FastAPI) -> None:
    @app.get("/health", tags=["ops"])
    def health(clarity: ClarityDep) -> dict[str, Any]:
        return {
            "status": "ok",
            "rules": [p.ref for p in clarity.rules.packs],
            "policy_version": clarity.policy.thresholds.version,
            "driver_mode": clarity.registry.mode.value,
            "data": "SYNTHETIC - all HUTCH systems are mocked",
        }

    @app.get("/.well-known/clarity-keys.json", tags=["receipts"])
    def public_keys(clarity: ClarityDep) -> dict[str, Any]:
        """Public keys anyone can verify a receipt with (plan §15.2)."""
        return {"keys": clarity.signing.public_keys(), "alg": "Ed25519"}

    @app.get("/.well-known/clarity-audit-checkpoint.json", tags=["audit"])
    def audit_checkpoint(clarity: ClarityDep) -> dict[str, Any]:
        """The latest signed audit checkpoint, for anyone to fetch and keep (ADR-0035).

        Public on purpose. A copy held outside the database is what catches an
        insider who rewrites the trail *and* deletes the stored checkpoints:
        their trail will no longer reach this ``seq`` with this head. It holds
        a sequence number, two hashes, a time and a signature, nothing personal.
        """
        latest = clarity.audit_checkpoints.latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="no audit checkpoint has been issued yet")
        return checkpoint_document(latest, clarity.audit_checkpoints.public_keys())

    # ------------------------------------------------------------------ #
    # Audit trail and audit duties (audit assurance plan Phase 3)
    # ------------------------------------------------------------------ #

    @app.get("/v1/audit", tags=["audit"])
    def read_audit_trail(
        request: Request,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_READ))],
        actor_ref: str | None = None,
        event_type: str | None = None,
        case_id: str | None = None,
        after_seq: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Read the trail: hashes and masked detail only, never a payload.

        **The read is itself recorded** (rule 5): who looked, with which
        filters, and how many records they saw. Who watched the watchers is
        part of what is watched.
        """
        if limit < 1 or limit > 200:
            raise HTTPException(status_code=422, detail="limit is between 1 and 200")
        matching = [
            record
            for record in clarity.audit.records
            if record.seq > after_seq
            and (actor_ref is None or record.actor_ref == actor_ref)
            and (event_type is None or str(record.event_type) == event_type)
            and (case_id is None or record.case_id == case_id)
        ]
        page = matching[:limit]
        verification = clarity.audit_checkpoints.verify()
        filters = {
            "actor_ref": actor_ref,
            "event_type": event_type,
            "case_id": case_id,
            "after_seq": after_seq,
            "limit": limit,
        }
        trail.record(
            clarity,
            AuditEventType.AUDIT_READ,
            actor_ref=principal.ref,
            actor_kind=trail.actor_kind_of(principal),
            session_ref=trail.session_ref_for(trail.bearer_token(request)),
            object_ref="GET /v1/audit",
            detail={"filters": filters, "returned": len(page)},
            case_id=case_id,
        )
        return {
            "records": [record.model_dump(mode="json") for record in page],
            "next_after_seq": page[-1].seq if len(matching) > limit else None,
            "verification": {
                "intact": verification.intact,
                "length": verification.length,
                "checkpoints": verification.checkpoints,
                "last_checkpoint_seq": verification.last_checkpoint_seq,
                "broken_at": verification.broken_at,
                "reason": verification.reason,
                "lost_from": verification.lost_from,
                "lost_to": verification.lost_to,
            },
        }

    @app.get("/v1/audit/health", tags=["audit"])
    def audit_health(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_READ))],
    ) -> dict[str, Any]:
        """The chain health panel (plan 5.8): is the trail sound, and is it fresh.

        **Deliberately not recorded as ``audit.read``.** A dashboard polls this,
        and recording every poll would make the console trip the
        ``mass_audit_read`` rule within minutes: the monitor would raise alerts
        about the act of monitoring. It reads no record contents, only aggregates
        and the verification verdict, so there is nothing here to read about a
        person. Reading the trail *itself* is recorded, on ``GET /v1/audit``.

        The verification is **incremental** for the same reason: a full recompute
        on every poll turns the dashboard into the most expensive thing in the
        system. ``AuditLedger.verify`` is explicit about what that does and does
        not cover; the full recompute runs at startup and on the policy interval.
        """
        verification = clarity.audit_checkpoints.verify(incremental=True)
        latest = clarity.audit_checkpoints.latest()
        now = clarity.now()
        last_detection = clarity.assurance.last_run()
        pending = clarity.pending_event_count()
        floor = clarity.audit.floor
        return {
            "intact": verification.intact,
            "length": verification.length,
            "verified_from": verification.verified_from,
            "broken_at": verification.broken_at,
            "reason": verification.reason,
            "lost_from": verification.lost_from,
            "lost_to": verification.lost_to,
            "checkpoints": verification.checkpoints,
            "last_checkpoint_seq": verification.last_checkpoint_seq,
            "last_checkpoint_at": latest.recorded_at.isoformat() if latest else None,
            "last_checkpoint_age_seconds": (
                int((now - latest.recorded_at).total_seconds()) if latest else None
            ),
            "detection_last_ran_at": last_detection.isoformat() if last_detection else None,
            "writer_lag_events": pending,
            "archived_below_seq": int(floor["seq"]) if floor else 0,
            "witness_url": "/.well-known/clarity-audit-checkpoint.json",
            "simulated": True,
        }

    @app.get("/v1/audit/recovery", tags=["audit"])
    def audit_recovery(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_READ))],
    ) -> dict[str, Any]:
        """The recovery panel: the last backup, the last restore, and its loss report.

        Read out of the trail rather than from a separate status table, which is
        the point of recording them there: a status table can disagree with what
        happened, and the trail is what happened.
        """

        def latest(event: AuditEventType) -> dict[str, Any] | None:
            found = clarity.audit.of_type(event)
            if not found:
                return None
            record = found[-1]
            return {
                "seq": record.seq,
                "at": record.recorded_at.isoformat(),
                "actor_ref": record.actor_ref,
                **record.detail,
            }

        return {
            "last_backup": latest(AuditEventType.BACKUP_CREATED),
            "last_backup_read": latest(AuditEventType.BACKUP_READ),
            "last_restore": latest(AuditEventType.RESTORE_PERFORMED),
            "last_segment_sealed": latest(AuditEventType.SEGMENT_SEALED),
            "last_erasure": latest(AuditEventType.ERASURE_PERFORMED),
            "backups_configured": clarity.settings.audit_backup_key is not None,
            "simulated": True,
        }

    @app.post("/v1/audit/records/{seq}/verify", tags=["audit"])
    def verify_audit_record(
        seq: int,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_READ))],
    ) -> dict[str, Any]:
        """Recompute one record's hashes, for the trail explorer's "verify" action.

        It answers a narrow question honestly: does this row hash to what it says,
        and does it link to the row before it. It cannot confirm the payload,
        because the ledger never stored one: ``proves()`` does that, and it needs
        the document the caller is holding, which is not something a console has.
        """
        record = next((r for r in clarity.audit.records if r.seq == seq), None)
        if record is None:
            raise HTTPException(status_code=404, detail=f"no audit record at seq {seq}")
        previous = next((r for r in clarity.audit.records if r.seq == seq - 1), None)
        detail_matches = hash_payload(record.detail) == record.detail_hash
        hash_matches = record_hash(record) == record.chain_hash
        links = record.prev_hash == (previous.chain_hash if previous else None)
        if previous is None and seq > 1:
            # Archived: the row before it is in a segment, so the link cannot be
            # checked from here. Said, not assumed either way.
            links = record.prev_hash is not None
        return {
            "seq": seq,
            "detail_matches_its_hash": detail_matches,
            "record_hash_matches_its_contents": hash_matches,
            "follows_its_predecessor": links,
            "predecessor_available": previous is not None or seq == 1,
            "intact": detail_matches and hash_matches and links,
            "hash_version": record.hash_version,
            "chain_hash": record.chain_hash,
        }

    @app.get("/v1/audit/export", tags=["audit"])
    def export_audit_trail(
        request: Request,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_EXPORT))],
        case_id: str | None = None,
    ) -> dict[str, Any]:
        """A bundle a regulator can verify without trusting Clarity (Phase 7).

        Records, the signed checkpoints that cover them, the public keys, and the
        instructions for recomputing both. ``backend/scripts/verify_audit_export.py``
        does exactly that with nothing from Clarity imported, which is the point:
        a verifier that imports the code it checks proves only that the code
        agrees with itself.

        With ``case_id`` the export is a **selection**, and says so: a chain of
        only one case's records is not contiguous, and a verifier that read a
        selection as the whole trail would accept a redacted export as complete.

        Exporting is recorded like any other read of the trail, and needs
        ``audit:export``, which costs its holder every money permission.
        """
        records = clarity.audit.for_case(case_id) if case_id else clarity.audit.records
        export = AuditExport(
            created_at=clarity.now(),
            scope=f"case {case_id}" if case_id else "the whole trail",
            contiguous=case_id is None,
            records=records,
            checkpoints=clarity.audit_checkpoints.all(),
            public_keys=clarity.audit_checkpoints.public_keys(),
        )
        trail.record(
            clarity,
            AuditEventType.AUDIT_READ,
            actor_ref=principal.ref,
            actor_kind=trail.actor_kind_of(principal),
            session_ref=trail.session_ref_for(trail.bearer_token(request)),
            object_ref="GET /v1/audit/export",
            detail={
                "scope": export.scope,
                "records": len(records),
                "contiguous": export.contiguous,
                "digest": export.digest,
            },
            case_id=case_id,
        )
        return export_document(export)

    def _grant_call(call: Callable[[], AuditGrant]) -> dict[str, Any]:
        """Run one grant operation and map its refusals onto HTTP.

        Separation-of-duties refusals are 403s, so the refusal handler records
        them in the trail as ``access.denied`` with the rule that refused them.
        """
        try:
            return call().model_dump(mode="json")
        except GrantNotFound as error:
            raise HTTPException(status_code=404, detail="no such grant") from error
        except GrantRefused as error:
            status = {
                "NOT_PERMITTED": 403,
                "SELF_GRANT": 403,
                "FOUR_EYES": 403,
                "NOT_PENDING": 409,
                "NOT_ACTIVE": 409,
            }.get(error.code, 422)
            raise HTTPException(status_code=status, detail=f"{error.code}: {error}") from error

    def _permission(value: str) -> Permission:
        try:
            return Permission(value)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"unknown permission {value!r}") from error

    @app.get("/v1/audit/grants", tags=["audit"])
    def list_audit_grants(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_ASSIGN))],
    ) -> dict[str, Any]:
        """Every audit grant, active or not, for review and recertification."""
        return {"grants": [grant.model_dump(mode="json") for grant in clarity.audit_grants.all()]}

    @app.post("/v1/audit/grants", tags=["audit"], status_code=201)
    def request_audit_grant(
        body: AuditGrantRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_ASSIGN))],
    ) -> dict[str, Any]:
        """Ask for an audit duty for a named person or a role. Someone else approves."""
        try:
            kind = SubjectKind(body.subject_kind)
            duration = _DURATION_ADAPTER.validate_python(body.duration)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        permission = _permission(body.permission)
        return _grant_call(
            lambda: clarity.audit_grants.request(
                principal,
                subject_kind=kind,
                subject_ref=body.subject_ref,
                permission=permission,
                reason=body.reason,
                duration=duration,
            )
        )

    @app.post("/v1/audit/grants/{grant_id}/approve", tags=["audit"])
    def approve_audit_grant(
        grant_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_ASSIGN))],
    ) -> dict[str, Any]:
        """The second pair of eyes. The requester cannot approve their own request."""
        return _grant_call(lambda: clarity.audit_grants.approve(principal, grant_id))

    @app.post("/v1/audit/grants/{grant_id}/revoke", tags=["audit"])
    def revoke_audit_grant(
        grant_id: str,
        body: AuditGrantRevoke,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_ASSIGN))],
    ) -> dict[str, Any]:
        return _grant_call(
            lambda: clarity.audit_grants.revoke(principal, grant_id, reason=body.reason)
        )

    @app.post("/v1/audit/grants/{grant_id}/recertify", tags=["audit"])
    def recertify_audit_grant(
        grant_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_ASSIGN))],
    ) -> dict[str, Any]:
        """Keep a grant alive one more review interval. Unreviewed grants lapse."""
        return _grant_call(lambda: clarity.audit_grants.recertify(principal, grant_id))

    @app.post("/v1/audit/break-glass", tags=["audit"], status_code=201)
    def break_glass(
        body: BreakGlassRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.ADMIN_MANAGE))],
    ) -> dict[str, Any]:
        """An admin's immediate audit duty for an incident: short, and always recorded."""
        permission = _permission(body.permission)
        return _grant_call(
            lambda: clarity.audit_grants.break_glass(
                principal, permission=permission, reason=body.reason
            )
        )

    # ------------------------------------------------------------------ #
    # Assurance: alerts raised from the trail (audit assurance plan Phase 4)
    # ------------------------------------------------------------------ #

    def _alert_call(call: Callable[[], Alert]) -> dict[str, Any]:
        """Run one lifecycle move and map its refusals onto HTTP.

        Rule refusals are 403s, so the refusal handler records each one in the
        trail with the rule that refused it.
        """
        try:
            return call().model_dump(mode="json")
        except AlertNotFound as error:
            raise HTTPException(status_code=404, detail="no such alert") from error
        except AlertRefused as error:
            status = {
                "NOT_PERMITTED": 403,
                "SELF_DISPOSAL": 403,
                "SECOND_PERSON": 403,
            }.get(error.code, 409)
            raise HTTPException(status_code=status, detail=f"{error.code}: {error}") from error

    @app.get("/v1/assurance/alerts", tags=["assurance"])
    def list_alerts(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.AUDIT_READ))],
        open_only: bool = False,
    ) -> dict[str, Any]:
        """The alert queue. Each alert cites the trail records that justify it."""
        alerts = clarity.assurance.alerts(open_only=open_only)
        last = clarity.assurance.last_run()
        return {
            "alerts": [alert.model_dump(mode="json") for alert in alerts],
            "detection_last_ran_at": last.isoformat() if last else None,
        }

    @app.post("/v1/assurance/alerts/{alert_id}/acknowledge", tags=["assurance"])
    def acknowledge_alert(
        alert_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.ALERT_DISPOSE))],
    ) -> dict[str, Any]:
        return _alert_call(lambda: clarity.assurance.acknowledge(principal, alert_id))

    @app.post("/v1/assurance/alerts/{alert_id}/investigate", tags=["assurance"])
    def investigate_alert(
        alert_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.ALERT_DISPOSE))],
    ) -> dict[str, Any]:
        return _alert_call(lambda: clarity.assurance.investigate(principal, alert_id))

    @app.post("/v1/assurance/alerts/{alert_id}/dispose", tags=["assurance"])
    def dispose_alert(
        alert_id: str,
        body: AlertDisposal,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.ALERT_DISPOSE))],
    ) -> dict[str, Any]:
        """Close an alert with a disposition and a reason.

        Never by its own subject, and a high or critical alert is closed by
        someone other than whoever acknowledged it.
        """
        try:
            disposition = Disposition(body.disposition)
        except ValueError as error:
            raise HTTPException(
                status_code=422, detail=f"unknown disposition {body.disposition!r}"
            ) from error
        return _alert_call(
            lambda: clarity.assurance.dispose(
                principal, alert_id, disposition=disposition, reason=body.reason
            )
        )

    @app.post("/v1/demo/reset", tags=["demo"], dependencies=[Depends(demo_only)])
    def demo_reset() -> dict[str, Any]:
        """Rebuild the synthetic world so the demo can be run again cleanly.

        Running a journey refunds balances and switches subscriptions off, so a
        second run would start from the first run's state. Prototype only: there
        is no such thing in production.
        """
        set_clarity(get_clarity().reset())
        return {"status": "reset", "detail": "synthetic world and all cases rebuilt"}

    # ------------------------------------------------------------------ #
    # Sign in
    # ------------------------------------------------------------------ #

    # Staff sign-in through the provider (B1, B2, B3). Its own module: the
    # flow is four routes and a cookie, and it has nothing to do with the rest
    # of this file.
    staff_sso.register(app)

    # The Complaint Autopsy reviewer workspace (D1). Its own module for the
    # same reason as the sign-in flow: it is a coherent surface with its own
    # permissions, and it has nothing to do with the rest of this file.
    autopsy_api.register(app)

    @app.post("/v1/auth/otp/request", tags=["auth"])
    def request_otp(body: OtpRequest, clarity: ClarityDep) -> dict[str, Any]:
        """Start customer sign-in. The code goes to the delivery port only.

        In the demo that port is a labelled simulated inbox, so the UI can show
        the code. It is never returned from this endpoint, because possession
        of the phone is what proves identity.
        """
        try:
            msisdn = normalise_msisdn(body.msisdn)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        account = clarity.world.account_by_msisdn(msisdn)
        # Who asked, without the number: the pseudonym when it is a customer,
        # the masked form when it matches nobody (I13).
        who = account.ref if account is not None else f"unknown:{mask_msisdn(msisdn)}"

        def requested(outcome: str, challenge: str | None = None) -> None:
            trail.record(
                clarity,
                AuditEventType.OTP_REQUESTED,
                actor_ref=who,
                actor_kind=ActorKind.CUSTOMER,
                object_ref=challenge or "otp",
                detail={"outcome": outcome, "channel": "sms"},
            )

        # The same answer whether or not the number is a subscriber. A 404 here
        # let anyone test which numbers are HUTCH customers, one request at a
        # time, with no credentials: `OtpRefused` states the rule for the module
        # ("a specific one would tell an attacker whether a number exists") and
        # the channel gateway already keeps it. A challenge is issued either
        # way, so the body, the timing and the rate limit are the same for both;
        # an unknown number then fails `verify` like any wrong code. The trail
        # still records which it was, because the trail is not the attacker.
        try:
            challenge_id = clarity.otp.request(msisdn)
        except HttpSmsDeliveryFailed as error:
            requested("delivery_failed")
            raise HTTPException(status_code=502, detail=str(error)) from error
        except OtpRefused as error:
            requested("refused")
            raise HTTPException(status_code=429, detail=str(error)) from error

        requested("sent" if account is not None else "unknown_number", challenge_id)
        # A linked phone gets a real SMS. Every other number, known or not,
        # gets the same answer, so the response never says who is a customer.
        delivery = clarity.otp.delivery
        by_sms = isinstance(delivery, RoutedOtpDelivery) and delivery.channel_for(msisdn) == "sms"
        if not isinstance(delivery, (RoutedOtpDelivery, SimulatedInbox)):
            by_sms = True
        return {
            "challenge_id": challenge_id,
            "sent_to": mask_msisdn(msisdn),
            "simulated": not by_sms,
            "detail": (
                "A sign-in code was sent by SMS."
                if by_sms
                else (
                    "SMS delivery is not connected for this number; "
                    "the code is shown on the sign-in page."
                )
            ),
        }

    @app.get("/v1/demo/inbox", tags=["demo"], dependencies=[Depends(demo_only)])
    def demo_inbox(clarity: ClarityDep, msisdn: str) -> dict[str, Any]:
        """The simulated SMS inbox. Prototype only, and labelled everywhere."""
        delivery = clarity.otp.delivery
        inbox = delivery.inbox if isinstance(delivery, RoutedOtpDelivery) else delivery
        message = inbox.latest_for(msisdn) if isinstance(inbox, SimulatedInbox) else None
        if message is None:
            raise HTTPException(status_code=404, detail="no simulated message for that number")
        return message

    @app.post("/v1/auth/otp/verify", response_model=SessionView, tags=["auth"])
    def verify_otp(body: OtpVerify, clarity: ClarityDep) -> JSONResponse:
        """Exchange a correct code for a short-lived customer token."""
        try:
            msisdn = clarity.otp.verify(body.challenge_id, body.code)
        except OtpRefused as error:
            # The challenge, never the code that was tried.
            trail.record(
                clarity,
                AuditEventType.OTP_FAILED,
                actor_ref=f"challenge:{body.challenge_id}",
                actor_kind=ActorKind.CUSTOMER,
                object_ref=body.challenge_id,
                detail={"reason": str(error)},
            )
            raise HTTPException(status_code=401, detail=str(error)) from error

        account = clarity.world.account_by_msisdn(msisdn)
        if account is None:
            raise HTTPException(status_code=404, detail="We could not find this Hutch number.")

        issued = clarity.tokens.for_customer(
            account.ref, assurance=Assurance.OTP, channel=body.channel.value
        )
        trail.record(
            clarity,
            AuditEventType.OTP_VERIFIED,
            actor_ref=account.ref,
            actor_kind=ActorKind.CUSTOMER,
            session_ref=trail.session_ref_for(issued.value),
            object_ref=body.challenge_id,
            detail={
                "assurance": issued.principal.assurance.value,
                "channel": body.channel.value,
            },
        )
        # The session also goes in an `HttpOnly` cookie (B4). The body still
        # carries the token, because the WhatsApp gateway and the MCP server
        # are not browsers and have nowhere to put a cookie; what changes is
        # that a browser no longer has to keep one where scripts can read it.
        view = SessionView(
            token=issued.value,
            refresh_token=issued.refresh_token,
            expires_at=issued.expires_at,
            subject=account.masked,
            roles=["customer"],
            assurance=issued.principal.assurance.value,
        )
        payload = JSONResponse(content=view.model_dump(mode="json"))
        payload.set_cookie(
            CUSTOMER_COOKIE,
            issued.value,
            max_age=max(0, int((issued.expires_at - utc_now()).total_seconds())),
            httponly=True,
            secure=clarity.settings.cookie_secure,
            samesite="lax",
            path="/",
        )
        csrf.issue(payload, secure=clarity.settings.cookie_secure)
        return payload

    @app.post(
        "/v1/auth/staff/login",
        response_model=SessionView,
        tags=["auth"],
        dependencies=[Depends(demo_only)],
    )
    def staff_login(body: StaffLogin, clarity: ClarityDep) -> SessionView:
        """Sign in against the staff directory. The server assigns the role.

        **Simulated** accounts, for the synthetic profiles. Production federates
        HUTCH SSO and this route answers 404 (I9). A wrong password and a wrong
        step-up code return the same refusal.
        """
        directory = clarity.staff_directory
        if directory is None:
            raise HTTPException(status_code=401, detail="sign-in failed")
        try:
            identity = directory.authenticate(body.username, body.password, body.step_up_code)
        except LoginRefused as error:
            raise HTTPException(status_code=401, detail="sign-in failed") from error
        issued = clarity.tokens.for_staff(
            identity.user_ref,
            roles={identity.role},
            assurance=identity.assurance,
        )
        trail.record(
            clarity,
            AuditEventType.STAFF_SESSION_STARTED,
            actor_ref=identity.user_ref,
            actor_kind=ActorKind.STAFF,
            session_ref=trail.session_ref_for(issued.value),
            object_ref=identity.user_ref,
            detail={
                "roles": [identity.role.value],
                "step_up": identity.assurance is Assurance.MFA_RECENT,
                "assurance": issued.principal.assurance.value,
                "simulated": True,
            },
        )
        return SessionView(
            token=issued.value,
            refresh_token=issued.refresh_token,
            expires_at=issued.expires_at,
            subject=identity.user_ref,
            roles=[identity.role.value],
            assurance=issued.principal.assurance.value,
            permissions=sorted(p.value for p in issued.principal.permissions),
        )

    @app.post(
        "/v1/auth/staff/session",
        response_model=SessionView,
        tags=["auth"],
        # A role picker with no password must not exist outside the demo (D3).
        dependencies=[Depends(demo_only)],
    )
    def staff_session(body: StaffSignIn, clarity: ClarityDep) -> SessionView:
        """Development staff sign-in.

        **Simulated.** Production federates HUTCH SSO (Keycloak over AD/Entra).
        When a staff directory is configured this route is gone: the browser
        cannot choose a role.
        """
        if clarity.staff_directory is not None:
            raise HTTPException(status_code=404, detail="not found")
        try:
            roles = {Role(name) for name in body.roles}
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"unknown role: {error}") from error
        if Role.CUSTOMER in roles:
            raise HTTPException(status_code=422, detail="customer is not a staff role")

        issued = clarity.tokens.for_staff(
            body.user_ref,
            roles=roles,
            assurance=Assurance.MFA_RECENT if body.step_up else Assurance.MFA,
        )
        # The moment a session *becomes* a supervisor with step-up. Every
        # approval later made with this token carries the same session_ref.
        trail.record(
            clarity,
            AuditEventType.STAFF_SESSION_STARTED,
            actor_ref=body.user_ref,
            actor_kind=ActorKind.STAFF,
            session_ref=trail.session_ref_for(issued.value),
            object_ref=body.user_ref,
            detail={
                "roles": sorted(role.value for role in roles),
                "step_up": body.step_up,
                "assurance": issued.principal.assurance.value,
                "simulated": True,
            },
        )
        return SessionView(
            token=issued.value,
            refresh_token=issued.refresh_token,
            expires_at=issued.expires_at,
            subject=body.user_ref,
            roles=sorted(role.value for role in roles),
            assurance=issued.principal.assurance.value,
            permissions=sorted(p.value for p in issued.principal.permissions),
        )

    @app.post("/v1/auth/refresh", response_model=SessionView, tags=["auth"])
    def refresh_session(body: RefreshRequest, clarity: ClarityDep) -> SessionView:
        """Rotate a refresh token. Reuse and revoked sessions are refused."""
        try:
            issued = clarity.tokens.refresh(body.refresh_token)
        except TokenInvalid as error:
            trail.record(
                clarity,
                AuditEventType.TOKEN_REJECTED,
                actor_ref="unknown",
                actor_kind=ActorKind.SYSTEM,
                session_ref=trail.session_ref_for(body.refresh_token),
                object_ref="POST /v1/auth/refresh",
                detail={"kind": "refresh", "reason": str(error)},
            )
            raise HTTPException(status_code=401, detail=str(error)) from error
        trail.record(
            clarity,
            AuditEventType.TOKEN_REFRESHED,
            actor_ref=issued.principal.ref,
            actor_kind=trail.actor_kind_of(issued.principal),
            session_ref=trail.session_ref_for(issued.value),
            object_ref=issued.principal.ref,
            detail={"roles": sorted(role.value for role in issued.principal.roles)},
        )
        return SessionView(
            token=issued.value,
            refresh_token=issued.refresh_token,
            expires_at=issued.expires_at,
            subject=issued.principal.ref,
            roles=sorted(role.value for role in issued.principal.roles),
            assurance=issued.principal.assurance.value,
            permissions=sorted(permission.value for permission in issued.principal.permissions),
        )

    @app.get("/v1/auth/me", response_model=SessionView, tags=["auth"])
    def whoami(principal: CurrentPrincipal) -> SessionView:
        """Who the current token says you are, and what it lets you do."""
        if not principal.roles:
            raise HTTPException(status_code=401, detail="sign in to continue")
        return SessionView(
            token="",
            expires_at=None,
            subject=principal.ref,
            roles=sorted(role.value for role in principal.roles),
            assurance=principal.assurance.value,
            permissions=sorted(p.value for p in principal.permissions),
        )

    @app.get("/.well-known/jwks.json", tags=["auth"])
    def jwks(clarity: ClarityDep) -> dict[str, Any]:
        """The public key a separate validator would use."""
        # The whole ring, not just the active key. A validator that is not
        # this process must be able to check a token signed by a key that is
        # rotating out, or every rotation breaks it (B5).
        return {"keys": clarity.tokens.public_keys()}

    @app.get(
        "/v1/demo/subscribers",
        response_model=list[DemoSubscriber],
        tags=["demo"],
        dependencies=[Depends(demo_only)],
    )
    def demo_subscribers(clarity: ClarityDep) -> list[DemoSubscriber]:
        """Prototype only: the synthetic customers shipped with the demo."""
        scenarios = {
            "+94781234567": "VAS charged with no consent",
            "+94782223333": "Reload taken twice",
            "+94783334444": "'Unlimited' hit a fair-use cap",
            "+94784445555": "Large reload not credited, recent SIM swap",
        }
        return [
            DemoSubscriber(
                name=scenarios.get(account.msisdn, "synthetic subscriber"),
                msisdn=account.msisdn,
                masked=account.masked,
                language=account.language,
                balance_lkr=account.balance_lkr,
                scenario=scenarios.get(account.msisdn, ""),
            )
            for account in clarity.world.accounts()
        ]

    @app.post("/v1/cases", response_model=CaseSummary, status_code=201, tags=["cases"])
    def open_case(
        body: OpenCaseRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CASE_EVALUATE))],
    ) -> CaseSummary:
        try:
            msisdn = normalise_msisdn(body.msisdn)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        account = clarity.world.account_by_msisdn(msisdn)
        if account is None:
            raise HTTPException(status_code=404, detail="no such subscriber in the demo data")

        # A customer may only open a case about their own number. Staff may
        # open one for any subscriber.
        authorize_case_access(principal, account.ref)

        case = clarity.cases.open_case(
            subscriber_ref=ref_for(msisdn),
            msisdn_masked=account.masked,
            channel=body.channel,
            language=body.language,
            charge_ref=body.charge_ref,
        )
        return _case_summary(clarity.cases.get(case.case_id))

    @app.get("/v1/cases/{case_id}", response_model=CaseSummary, tags=["cases"])
    def get_case(
        case_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CASE_READ))],
    ) -> CaseSummary:
        record = clarity.cases.get(case_id)
        authorize_case_access(principal, record.subscriber_ref)
        return _case_summary(record)

    @app.get("/v1/cases/{case_id}/transcript", tags=["conversation"])
    def get_transcript(
        case_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CASE_READ))],
    ) -> dict[str, Any]:
        """What was said on this case, oldest first (A4, ADR-0040).

        Subject bound like every other case route (I9): the transcript is the
        most personal thing the conversation holds, so the case id alone must
        not open it. Staff with `case:read:any` see it because that is what
        makes a handoff workable: the agent picking the case up can read what
        the customer already explained instead of asking them again.

        The text is masked, as it was when it was stored. Retention is applied
        on read, so a line past its window is gone here even if the table has
        not been swept.
        """
        record = clarity.cases.get(case_id)
        authorize_case_access(principal, record.subscriber_ref)
        entries = clarity.conversation.transcript.for_case(case_id)
        return {
            "case_id": case_id,
            "entries": [entry.to_dict() for entry in entries],
            "masked": True,
            "retention_days": clarity.conversation.transcript.retention.days,
        }

    @app.get("/v1/cases/{case_id}/timeline", response_model=TimelineView, tags=["cases"])
    def get_timeline(
        case_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CASE_READ))],
    ) -> TimelineView:
        record = clarity.cases.get(case_id)
        authorize_case_access(principal, record.subscriber_ref)
        snapshot = record.snapshot or clarity.cases.build_timeline(case_id)
        return TimelineView(
            case_id=case_id,
            window_from=snapshot.window_from,
            window_to=snapshot.window_to,
            snapshot_hash=snapshot.snapshot_hash,
            events=[
                TimelineEventView(
                    event_id=e.event_id,
                    source=e.source,
                    event_type=e.event_type.value,
                    occurred_at=e.occurred_at,
                    amount_lkr=e.amount_lkr,
                    attributes=e.attributes,
                )
                for e in snapshot.events
            ],
            sources=[
                SourceStatusView(
                    source=s.source,
                    completeness=s.completeness,
                    event_count=s.event_count,
                    note=s.note,
                )
                for s in snapshot.sources
            ],
        )

    @app.post("/v1/cases/{case_id}/evaluate", response_model=DecisionView, tags=["cases"])
    def evaluate(
        case_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CASE_EVALUATE))],
        human: bool = False,
    ) -> DecisionView:
        """Run the rules and the policy. Changes nothing on the account."""
        authorize_case_access(principal, clarity.cases.get(case_id).subscriber_ref)
        clarity.cases.evaluate(case_id, customer_requested_human=human)
        return _decision_view(clarity.cases.get(case_id), clarity)

    @app.post(
        "/v1/cases/{case_id}/proposals", response_model=PlanView, status_code=201, tags=["actions"]
    )
    def propose(
        case_id: str,
        body: ProposeRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.ACTION_PROPOSE))],
    ) -> PlanView:
        """Create a plan. Still changes nothing - confirmation comes next."""
        authorize_case_access(principal, clarity.cases.get(case_id).subscriber_ref)
        plan = clarity.cases.propose(
            case_id, created_by=body.created_by, action_types=body.action_types
        )
        return _plan_view(plan)

    @app.post("/v1/cases/{case_id}/confirm", response_model=ExecutionView, tags=["actions"])
    def confirm(
        case_id: str,
        body: ConfirmRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.ACTION_CONFIRM_OWN))],
    ) -> ExecutionView:
        """The customer tapped Confirm (deck S5, step 3)."""
        record = clarity.cases.get(case_id)
        authorize_case_access(principal, record.subscriber_ref)
        # A claimed number is enough to be told things, not to change them.
        customer_can_act(principal)
        clarity.cases.confirm_and_execute(case_id, body.plan_id)
        return _execution_view(clarity.cases.get(case_id), body.plan_id)

    @app.post("/v1/cases/{case_id}/auto-fix", response_model=ExecutionView, tags=["actions"])
    def auto_fix(
        case_id: str,
        body: ConfirmRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.ACTION_PROPOSE))],
    ) -> ExecutionView:
        """Zero-contact execution of a whitelisted AUTO_FIX (deck S5)."""
        authorize_case_access(principal, clarity.cases.get(case_id).subscriber_ref)
        clarity.cases.auto_fix(case_id, body.plan_id, triggered_by=principal.ref)
        return _execution_view(clarity.cases.get(case_id), body.plan_id)

    @app.post("/v1/cases/{case_id}/approve", tags=["desk"])
    def approve(
        case_id: str,
        body: ApproveRequest,
        clarity: ClarityDep,
        response: Response,
        principal: Annotated[Principal, Depends(requires(Permission.ACTION_APPROVE))],
    ) -> Any:
        """Staff approval. Four-eyes cases need a second, different approver."""
        record = clarity.cases.get(case_id)
        # Above the cap needs the high-value permission *and* recent MFA.
        authorize_action(
            principal,
            amount_lkr=record.decision.amount_lkr if record.decision else None,
            cap=clarity.policy.thresholds.one_tap_cap_lkr,
        )
        # The approver is whoever the token says, and they may only approve in
        # a role they actually hold. Taking either from the request body would
        # let one person approve twice under two names, which is exactly what
        # maker-is-not-checker exists to prevent (plan §19 TH7).
        if body.role not in {role.value for role in principal.roles}:
            raise HTTPException(
                status_code=403, detail=f"this account does not hold the role '{body.role}'"
            )
        outcome = clarity.cases.approve_and_execute(
            case_id,
            body.plan_id,
            approver_ref=principal.ref,
            role=body.role,
            # Recorded from the session, not claimed by the caller: an audit
            # trail that takes the client's word for step-up proves nothing.
            mfa_step_up=principal.assurance.is_step_up,
        )
        if outcome is None:
            response.status_code = 202
            return PendingApprovalView(
                case_id=case_id,
                plan_id=body.plan_id,
                detail="a second approver with a different role is required",
            )
        return _execution_view(clarity.cases.get(case_id), body.plan_id)

    @app.post("/v1/cases/{case_id}/receipt", response_model=VerificationView, tags=["receipts"])
    def issue_explanation_receipt(
        case_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CASE_EVALUATE))],
    ) -> VerificationView:
        """Receipt for an explain-only outcome: proof that nothing was owed."""
        receipt = clarity.cases.issue_explanation_receipt(case_id)
        return _verification_view(clarity, receipt.receipt_id)

    @app.get("/v1/receipts/{receipt_id}", tags=["receipts"])
    def get_receipt(
        receipt_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.RECEIPT_READ))],
    ) -> Any:
        """The full signed document. The public page shows the masked view."""
        receipt = clarity.receipts.get(receipt_id)
        if receipt is None:
            raise HTTPException(status_code=404, detail="no such receipt")
        _authorize_receipt_access(principal, receipt)
        return receipt.model_dump(mode="json")

    @app.post(
        "/v1/receipts/{receipt_id}/verify", response_model=VerificationView, tags=["receipts"]
    )
    def verify_receipt(receipt_id: str, clarity: ClarityDep) -> VerificationView:
        """What the QR code resolves to. Public, and safe to be public."""
        return _verification_view(clarity, receipt_id)

    @app.get("/v1/receipts/{receipt_id}/qr.svg", tags=["receipts"])
    def receipt_qr(receipt_id: str, clarity: ClarityDep) -> RawResponse:
        """QR code for the verification page (deck S6: "Scan to verify").

        Encodes only the public verify URL - no PII, and nothing that grants
        access to the case (plan §15.2).
        """
        receipt = clarity.receipts.get(receipt_id)
        if receipt is None:
            raise HTTPException(status_code=404, detail="no such receipt")

        import io

        import qrcode
        import qrcode.image.svg

        image = qrcode.make(
            receipt.verify_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2
        )
        buffer = io.BytesIO()
        image.save(buffer)
        return RawResponse(
            content=buffer.getvalue(),
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get("/v1/ai/usage", tags=["ops"])
    def ai_usage(clarity: ClarityDep) -> dict[str, Any]:
        """Measured token usage, for the AI disclosure (Guidelines §6.2)."""
        return {
            "provider": clarity.ai.provider.name,
            "note": (
                "No language model is configured in this prototype. Explanations come "
                "from CX-approved templates, which is the deck's 'works without the "
                "LLM' path. Token counts are therefore measured, and zero."
            ),
            **clarity.ai.usage_summary,
        }

    @app.get("/v1/mcp/tools", tags=["ops"])
    def mcp_tools(clarity: ClarityDep, profile: str = "customer-assist") -> dict[str, Any]:
        """What an AI agent is allowed to call, and at what safety level."""
        from clarity.interfaces.mcp.server import ClarityMCPServer, Profile

        try:
            chosen = Profile(profile)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"unknown profile {profile!r}") from error
        return {
            "profile": chosen.value,
            "tools": ClarityMCPServer(clarity.mcp_view).list_tools(chosen),
            "guarantee": (
                "No tool executes a financial or service-changing action. The strongest "
                "is propose_action, which creates a pending plan requiring confirmation "
                "minted outside the model."
            ),
        }

    @app.get("/v1/receipts/{receipt_id}/render", tags=["receipts"])
    def render_receipt(
        receipt_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.RECEIPT_READ))],
        language: str = "en",
        format: str = "png",
    ) -> RawResponse:
        """A receipt as PNG or PDF, in si/ta/en (deck S6).

        Returns 503 rather than a broken file if the renderer is unavailable; the
        SMS form and the verify page still work without it.
        """
        from clarity.modules.receipts.public import (
            RendererUnavailable,
            RenderFormat,
        )
        from clarity.modules.receipts.public import (
            render as render_receipt_file,
        )

        receipt = clarity.receipts.get(receipt_id)
        if receipt is None:
            raise HTTPException(status_code=404, detail="no such receipt")
        _authorize_receipt_access(principal, receipt)
        try:
            chosen_language = Language(language)
            chosen_format = RenderFormat(format)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        try:
            rendered = render_receipt_file(receipt, language=chosen_language, format=chosen_format)
        except RendererUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

        return RawResponse(
            content=rendered.content,
            media_type=rendered.media_type,
            headers={
                "Content-Disposition": f'inline; filename="{receipt_id}.{chosen_format.value}"'
            },
        )

    @app.get("/v1/desk/queue", response_model=list[QueueItem], tags=["desk"])
    def desk_queue(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.DESK_QUEUE_READ))],
    ) -> list[QueueItem]:
        """Cases needing a person, biggest money at stake first (deck S9)."""
        waiting = [
            record
            for record in clarity.cases.all_cases()
            if record.decision is not None
            and record.decision.outcome in {Outcome.STAFF_APPROVAL, Outcome.HANDOFF}
            and record.execution is None
        ]
        waiting.sort(key=lambda r: r.case.money_at_stake_lkr or 0, reverse=True)
        return [
            QueueItem(
                case_id=r.case_id,
                case_no=r.case.case_no,
                state=r.case.state.value,
                outcome=r.decision.outcome if r.decision else None,
                cause=r.decision.top_cause_ref if r.decision else None,
                money_at_stake_lkr=r.case.money_at_stake_lkr,
                msisdn_masked=r.case.customer.msisdn_masked,
                channel=r.case.origin_channel,
                reason=(r.decision.rationale[0] if r.decision and r.decision.rationale else None),
                plan_id=next(iter(r.plans), None),
            )
            for r in waiting
        ]

    @app.get("/v1/finance/reconciliation", tags=["finance"])
    def reconciliation_queue(
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.RECONCILIATION_READ))],
    ) -> list[dict[str, Any]]:
        """Persisted T+1 mismatches for finance investigation."""
        return [
            {
                "mismatch_id": item.mismatch_id,
                "action_id": item.action_id,
                "plan_id": item.plan_id,
                "expected_lkr": str(item.expected_lkr),
                "confirmed_lkr": (
                    str(item.confirmed_lkr) if item.confirmed_lkr is not None else None
                ),
                "reason": item.reason,
                "detected_at": item.detected_at.isoformat(),
            }
            for item in clarity.reconciliation.queue()
        ]

    @app.get("/v1/admin/policy/changes", tags=["policy-studio"])
    def list_policy_changes(
        clarity: ClarityDep,
        principal: CurrentPrincipal,
    ) -> list[dict[str, Any]]:
        """Policy Studio catalogue and lifecycle timeline."""
        if principal is ANONYMOUS or not principal.roles:
            raise HTTPException(status_code=401, detail="sign in to continue")
        if not (principal.has(Permission.CONFIG_DRAFT) or principal.has(Permission.CONFIG_APPROVE)):
            raise HTTPException(status_code=403, detail="this account may not read policy")
        clarity.governance.activate_due()
        return [_policy_change_view(change) for change in clarity.governance.all_changes()]

    @app.post("/v1/admin/policy/changes", tags=["policy-studio"])
    def draft_policy_change(
        body: PolicyDraftRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CONFIG_DRAFT))],
    ) -> dict[str, Any]:
        artefact = clarity.policies.key(body.key)
        candidate = PolicyValue(
            value=body.value,
            scope=Scope.model_validate(body.scope),
            version=body.version,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
        )
        change = clarity.governance.draft(
            key=body.key,
            candidate=candidate,
            computed_class=artefact.change_class,
            maker_ref=principal.ref,
            reason=body.reason,
        )
        return _policy_change_view(change)

    @app.post("/v1/admin/policy/changes/{change_id}/review", tags=["policy-studio"])
    def review_policy_change(
        change_id: str,
        body: PolicyReviewRequest,
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.CONFIG_DRAFT))],
    ) -> dict[str, Any]:
        change = clarity.governance.get(change_id)
        report = ImpactReport(
            key=change.key,
            change_class=change.change_class,
            cases_evaluated=body.cases_evaluated,
            candidate_summary=body.candidate_summary,
        )
        return _policy_change_view(clarity.governance.attach_impact(change_id, report))

    @app.post("/v1/admin/policy/changes/{change_id}/approve", tags=["policy-studio"])
    def approve_policy_change(
        change_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CONFIG_APPROVE))],
    ) -> dict[str, Any]:
        role = sorted(role.value for role in principal.roles)[0]
        change = clarity.governance.approve(
            change_id,
            approver_ref=principal.ref,
            role=role,
            mfa_step_up=principal.assurance.is_step_up,
        )
        return _policy_change_view(change)

    @app.post("/v1/admin/policy/changes/{change_id}/schedule", tags=["policy-studio"])
    def schedule_policy_change(
        change_id: str,
        body: PolicyScheduleRequest,
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.CONFIG_APPROVE))],
    ) -> dict[str, Any]:
        return _policy_change_view(
            clarity.governance.schedule(change_id, effective_from=body.effective_from)
        )

    @app.post("/v1/admin/policy/changes/{change_id}/activate", tags=["policy-studio"])
    def activate_policy_change(
        change_id: str,
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.CONFIG_APPROVE))],
    ) -> dict[str, Any]:
        return _policy_change_view(clarity.governance.activate(change_id))

    @app.post("/v1/admin/policy/changes/{change_id}/rollback", tags=["policy-studio"])
    def rollback_policy_change(
        change_id: str,
        body: PolicyRollbackRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.CONFIG_APPROVE))],
    ) -> dict[str, Any]:
        return _policy_change_view(
            clarity.governance.rollback(change_id, maker_ref=principal.ref, reason=body.reason)
        )

    @app.get("/v1/admin/switches", tags=["admin"])
    def list_switches(
        clarity: ClarityDep,
        principal: CurrentPrincipal,
    ) -> dict[str, Any]:
        """Kill-switch state. Readable with kill_switch or admin:manage."""
        if principal is ANONYMOUS or not principal.roles:
            raise HTTPException(status_code=401, detail="sign in to continue")
        if not (principal.has(Permission.KILL_SWITCH) or principal.has(Permission.ADMIN_MANAGE)):
            raise HTTPException(status_code=403, detail="this account may not read switches")
        named = [s.value for s in Switch]
        disabled = set(clarity.switches.disabled)
        return {
            "switches": [{"key": key, "enabled": key not in disabled} for key in named]
            + [{"key": key, "enabled": False} for key in sorted(disabled) if key not in named],
            "disabled": list(clarity.switches.disabled),
            "history": [
                {
                    "name": flip.name,
                    "enabled": flip.enabled,
                    "actor_ref": flip.actor_ref,
                    "reason": flip.reason,
                    "at": flip.at.isoformat(),
                }
                for flip in clarity.switches.history[-20:]
            ],
        }

    @app.post("/v1/admin/switches", tags=["admin"])
    def flip_switch(
        body: SwitchFlipRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.KILL_SWITCH))],
    ) -> dict[str, Any]:
        """Flip a kill switch. Audited. Needs ``flags:kill_switch`` (+ step-up)."""
        if body.enabled:
            clarity.switches.turn_on(body.key, actor_ref=principal.ref, reason=body.reason)
        else:
            clarity.switches.turn_off(body.key, actor_ref=principal.ref, reason=body.reason)
        named = [s.value for s in Switch]
        disabled = set(clarity.switches.disabled)
        return {
            "switches": [{"key": key, "enabled": key not in disabled} for key in named]
            + [{"key": key, "enabled": False} for key in sorted(disabled) if key not in named],
            "disabled": list(clarity.switches.disabled),
            "history": [
                {
                    "name": flip.name,
                    "enabled": flip.enabled,
                    "actor_ref": flip.actor_ref,
                    "reason": flip.reason,
                    "at": flip.at.isoformat(),
                }
                for flip in clarity.switches.history[-20:]
            ],
        }

    @app.post("/v1/admin/merchants/suspend", tags=["admin"])
    def suspend_merchant(
        body: MerchantSuspendRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.MERCHANT_SUSPEND))],
    ) -> dict[str, Any]:
        """Block a merchant on a demo subscriber (simulated). Needs step-up."""
        msisdn = body.subscriber_msisdn or "0781234567"
        try:
            normalised = normalise_msisdn(msisdn)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        account = clarity.world.account_by_msisdn(normalised)
        if account is None:
            raise HTTPException(status_code=404, detail="subscriber not found")
        newly = clarity.world.block_merchant(account.ref, body.merchant_id)
        return {
            "merchant_id": body.merchant_id,
            "subscriber_ref": account.ref,
            "blocked": True,
            "newly_blocked": newly,
            "reason": body.reason,
            "actor_ref": principal.ref,
            "simulated": True,
        }

    @app.get("/v1/me/home", tags=["customer"])
    def my_home(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_READ))],
    ) -> dict[str, Any]:
        """Balance, pack, activity and alerts for the signed-in number."""
        return _home_for(clarity, _customer_ref(principal))

    @app.get("/v1/me/app", tags=["customer"])
    def my_app(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_READ))],
    ) -> dict[str, Any]:
        """The only customer read. Every screen renders this payload."""
        return _app_for(clarity, _customer_ref(principal))

    @app.post("/v1/me/reload", tags=["customer"])
    def my_reload(
        body: ReloadRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_TRANSACT))],
    ) -> dict[str, Any]:
        ref = _customer_ref(principal)
        try:
            amount = Decimal(body.amount_lkr)
        except InvalidOperation as error:
            raise HTTPException(status_code=422, detail="enter a reload amount") from error
        allowed_amounts = {
            Decimal("100"),
            Decimal("200"),
            Decimal("500"),
            Decimal("1000"),
            Decimal("2000"),
        }
        if amount not in allowed_amounts:
            raise HTTPException(status_code=422, detail="choose a listed reload amount")
        clarity.world.reload(ref, amount)
        return _app_for(clarity, ref)

    @app.post("/v1/me/packages/{offering_id}/purchase", tags=["customer"])
    def my_purchase(
        offering_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_TRANSACT))],
    ) -> dict[str, Any]:
        ref = _customer_ref(principal)
        try:
            clarity.world.purchase_pack(ref, offering_id)
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="that pack is not in the catalogue"
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _app_for(clarity, ref)

    @app.post("/v1/me/subscriptions/{subscription_id}/cancel", tags=["customer"])
    def my_cancel(
        subscription_id: str,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_TRANSACT))],
    ) -> dict[str, Any]:
        ref = _customer_ref(principal)
        if not clarity.world.deactivate_subscription(ref, subscription_id):
            raise HTTPException(status_code=404, detail="that subscription is not active")
        return _app_for(clarity, ref)

    @app.post("/v1/me/safeguards", tags=["customer"])
    def my_safeguard(
        body: SafeguardRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_SETTINGS))],
    ) -> dict[str, Any]:
        ref = _customer_ref(principal)
        allowed = {"data_on_expiry", "spend_cap", "vas_confirm", "usage_alerts", "merchant_block"}
        if body.kind not in allowed:
            raise HTTPException(status_code=422, detail="unknown safeguard")
        if body.kind == "merchant_block" and body.value:
            clarity.world.block_merchant(ref, body.value)
        clarity.world.set_safeguard(ref, body.kind, {"value": body.value})
        return _app_for(clarity, ref)

    @app.post("/v1/me/family", tags=["customer"])
    def my_family(
        body: FamilyRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_SETTINGS))],
    ) -> dict[str, Any]:
        ref = _customer_ref(principal)
        try:
            clarity.world.add_family(ref, body.msisdn)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="We could not find this Hutch number."
            ) from error
        return _app_for(clarity, ref)

    @app.post("/v1/me/preferences", tags=["customer"])
    def my_preferences(
        body: PreferencesRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_SETTINGS))],
    ) -> dict[str, Any]:
        ref = _customer_ref(principal)
        account = clarity.world.account(ref)
        if account is None:
            raise HTTPException(status_code=404, detail="no such account")
        if body.notify not in {"all", "important", "none"}:
            raise HTTPException(status_code=422, detail="choose a notification preference")
        account.language = body.language
        account.notify = body.notify
        account.large_text = body.large_text
        account.onboarded = True
        clarity.world._flush(account)
        return _app_for(clarity, ref)

    @app.get("/v1/me/cases", tags=["customer"])
    def my_cases(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_READ))],
    ) -> list[dict[str, Any]]:
        """Cases opened for the signed-in number."""
        ref = _customer_ref(principal)
        rows = [record for record in clarity.cases.all_cases() if record.subscriber_ref == ref]
        rows.sort(key=lambda record: record.case.opened_at, reverse=True)
        return [
            {
                "case_id": record.case_id,
                "case_no": record.case.case_no,
                "state": record.case.state.value,
                "channel": record.case.origin_channel,
                "opened_at": record.case.opened_at.isoformat(),
                "outcome": record.decision.outcome.value if record.decision else None,
            }
            for record in rows
        ]

    @app.get("/v1/me/receipts", tags=["customer"])
    def my_receipts(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.SELF_READ))],
    ) -> list[dict[str, Any]]:
        """Trust Receipts already issued for the signed-in number."""
        ref = _customer_ref(principal)
        mine = {
            record.case_id for record in clarity.cases.all_cases() if record.subscriber_ref == ref
        }
        rows = []
        ref_hash = hash_payload(ref)
        for receipt in reversed(clarity.receipts.issued()):
            belongs = receipt.case_id in mine or (
                receipt.payload.subject.subscriber_ref_hash == ref_hash
            )
            if not belongs:
                continue
            corrected = receipt.payload.total_corrected_lkr
            rows.append(
                {
                    "receipt_id": receipt.receipt_id,
                    "issued_at": receipt.payload.issued_at.isoformat(),
                    "corrected_lkr": str(corrected) if corrected is not None else "0.00",
                    "summary": receipt.payload.what_happened.summary,
                    "case_id": receipt.case_id,
                }
            )
        return rows

    @app.get("/v1/knowledge/search", tags=["knowledge"])
    def knowledge_search(clarity: ClarityDep, q: str = "") -> dict[str, Any]:
        """Grounded search over the published corpus. Never opens a charge case.

        Served by `clarity.modules.knowledge` since K03 (#33), where it used to
        read the mock store directly. The module applies the effective-date and
        audience filters, ranks, composes a cited answer and verifies every
        citation against what was actually retrieved.

        **The response is additive.** `articles` keeps its shape and its place,
        because `/v1/clarity/route` and `/v1/conversation/turn` both read it and
        the frontend SDK is generated from this schema. `answer`, `citations`,
        `grounded` and `needs_person` are new keys.

        The audience is `customer` and is not a parameter. A staff caller would
        need a staff permission and a different route; accepting an audience
        from the query string would let anyone ask for staff sources (I9).
        """
        from clarity.integration.drivers.mock.store.knowledge import classify_intent

        found = clarity.answers.ask(q, audience=KnowledgeAudience.CUSTOMER)
        articles = [
            {
                "article_id": hit.chunk.source_id,
                "title": hit.chunk.title,
                "body": hit.chunk.text,
                "language": hit.chunk.language.value,
                "citation": hit.citation,
                "owner": hit.chunk.owner,
            }
            for hit in found.trace.hits
        ]
        return {
            "query": q,
            "intent": classify_intent(q),
            "articles": articles,
            "answer": found.text,
            "citations": list(found.citations),
            "grounded": found.grounded,
            "needs_person": found.needs_person,
        }

    @app.post("/v1/clarity/route", tags=["knowledge"])
    def clarity_route(body: dict[str, Any], clarity: ClarityDep) -> dict[str, Any]:
        """Server intent: account vs knowledge vs both (legacy) + chat taxonomy."""
        from clarity.integration.drivers.mock.store.knowledge import classify_intent
        from clarity.modules.conversation.public import handle_turn

        question = str(body.get("question") or "")
        legacy = classify_intent(question)
        articles: list[dict[str, Any]] = []
        if legacy in {"knowledge", "both"}:
            articles = knowledge_search(clarity, question).get("articles") or []
        turn = handle_turn(question, language_hint=str(body.get("language") or "") or None)
        return {
            "question": question,
            "intent": turn.intake.route if turn.intake.route != "handoff" else legacy,
            "articles": articles,
            "turn": turn.to_dict(),
            "client_intent": turn.intake.client_intent,
            "chat_intent": turn.intake.intent,
        }

    @app.post("/v1/conversation/turn", tags=["conversation"])
    def conversation_turn(
        body: dict[str, Any],
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(public())],
    ) -> dict[str, Any]:
        """One assistant turn.

        With a `case_id` the turn goes through the stateful pipeline (C01): the
        conversation resumes wherever it was left, on whatever channel, and the
        turn is guarded, verified and recorded. Without one there is nothing to
        attach state to, so the stateless path answers and keeps no state.

        The response is a superset either way: every field the stateless shape
        carried is still there, with `state`, `verifier` and `refused` added
        when a case is in play.
        """
        return {"turn": _run_turn(body, clarity, principal)}

    def _run_turn(
        body: dict[str, Any],
        clarity: Clarity,
        principal: Principal,
        on_stage: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """One turn, shared by the JSON route and the streaming one (A5).

        `on_stage` is passed to the orchestrator, which calls it with a stage
        code as each step finishes. It is ignored on the stateless path, which
        has no pipeline to report on.
        """
        from clarity.kernel.common import Channel
        from clarity.modules.conversation.public import handle_turn

        text = str(body.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="text is required")
        raw_facts = body.get("facts")
        facts: dict[str, Any] = dict(raw_facts) if isinstance(raw_facts, dict) else {}
        case_id = body.get("case_id")

        if case_id:
            try:
                channel = Channel(str(body.get("channel") or Channel.APP.value))
            except ValueError:
                raise HTTPException(status_code=422, detail="unknown channel") from None

            # Conversation state is case scoped, so this path is subject bound
            # like any other case route (I9). Without it the case id alone
            # would read and extend another customer's conversation, which is
            # the hole A04 found on the MCP side.
            if not principal.has(Permission.CASE_READ):
                raise HTTPException(
                    status_code=401, detail="continuing a case conversation needs a session"
                )
            record = clarity.cases.get(str(case_id))
            authorize_case_access(principal, record.subscriber_ref)

            turn = clarity.conversation.handle(
                str(case_id),
                text,
                channel=channel,
                # From the case, never from the body: the caller does not get
                # to choose who the audit records as the actor.
                subscriber_ref=record.subscriber_ref,
                language_hint=body.get("language"),
                intent_override=body.get("intent"),
                facts=_case_facts(record) | _client_context(facts),
                on_stage=on_stage,
            )
            payload = turn.to_dict()
            route = turn.intake.route
        else:
            result = handle_turn(
                text,
                case_id=None,
                # The same filter as the stateful branch above (A3). This used
                # to pass the body's `facts` straight through, and
                # `compose_reply` quotes `amount_lkr` for two intents, so an
                # anonymous caller could post a figure and have Clarity read it
                # back as though it had found it. There is no case here, so
                # there is no amount anything decided, and none may be quoted.
                facts=_client_context(facts),
                language_hint=body.get("language"),
                intent_override=body.get("intent"),
            )
            payload = result.to_dict()
            route = result.intake.route

        # Attach knowledge articles when route needs them.
        if route in {"knowledge", "both"}:
            payload["articles"] = knowledge_search(clarity, text).get("articles") or []
        return payload

    @app.post("/v1/conversation/turn/stream", tags=["conversation"])
    async def conversation_turn_stream(
        body: dict[str, Any],
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(public())],
    ) -> RawResponse:
        """The same turn, as Server-Sent Events (A5).

        The chat used to animate a `setTimeout` with a hardcoded English label
        while one request ran to completion, so the progress it showed
        reflected nothing: a fast turn still waited, and a hung one looked
        exactly like a slow one.

        Two event types, and only two:

        - `stage`, one per completed pipeline step, carrying a code from the
          closed `STAGES` vocabulary. **No customer content travels on a stage
          event**, which is why the orchestrator is handed a code rather than a
          message: a progress channel that can carry text is a second answer
          channel that nothing verifies.
        - `turn`, the identical payload the JSON route returns, once, at the
          end. Composed, verified and recorded before it is sent. Streaming
          reports progress; it does not stream a reply into the customer's view
          before the verifier has seen it.

        An error ends the stream with an `error` event carrying a status and no
        detail, because the response has already begun with a 200 and cannot
        become a 4xx.
        """
        queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def report(stage_name: str) -> None:
            # Called from the worker thread, so hop back onto the loop.
            loop.call_soon_threadsafe(queue.put_nowait, ("stage", {"stage": stage_name}))

        async def work() -> None:
            try:
                payload = await run_in_threadpool(_run_turn, body, clarity, principal, report)
                await queue.put(("turn", {"turn": payload}))
            except HTTPException as refused:
                await queue.put(("error", {"status": refused.status_code}))
            except Exception:
                _stream_log.exception("conversation turn stream failed")
                await queue.put(("error", {"status": 500}))
            finally:
                await queue.put(None)

        async def events() -> AsyncIterator[str]:
            task = loop.create_task(work())
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    name, data = item
                    yield f"event: {name}\ndata: {json.dumps(data)}\n\n"
            finally:
                task.cancel()

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                # nginx buffers a proxied response by default, which would hold
                # every stage back until the turn finished and make the stream
                # pointless in the deployed profile.
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/v1/conversation/suggestions", tags=["conversation"])
    def conversation_suggestions(body: dict[str, Any]) -> dict[str, Any]:
        from clarity.modules.conversation.public import suggest_for_snapshot

        snapshot = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else {}
        language = str(body.get("language") or "en")
        limit = int(body.get("limit") or 6)
        return suggest_for_snapshot(snapshot, language=language, limit=limit)

    @app.get("/v1/conversation/suggestions", tags=["conversation"])
    def conversation_suggestions_get(
        language: str = "en",
        limit: int = 6,
    ) -> dict[str, Any]:
        """Suggestions from the caller's session world when authenticated; else defaults."""
        from clarity.modules.conversation.public import suggest_for_snapshot

        snapshot: dict[str, Any] = {}
        # Optional auth: if customer token present, enrich from me/app shape later.
        return suggest_for_snapshot(snapshot, language=language, limit=min(max(limit, 1), 10))

    @app.get(
        "/v1/insights/dashboards",
        tags=["insights"],
        dependencies=[Depends(requires(Permission.DESK_QUEUE_READ))],
    )
    def insights_dashboards(clarity: ClarityDep) -> dict[str, Any]:
        """Console dashboards, folded from the event log (D2).

        The projection has existed since I01 and had no surface of its own:
        the only way to read it was `GET /v1/demo/ops`, a route tagged `demo`,
        which is not where an operations dashboard belongs. That route is gone
        as of D4, and the numbers are unchanged; what changed is that the
        console no longer reads a demonstration endpoint to run a desk.

        Folded from the log rather than read from live objects, which is the
        property that matters: a restart does not lose the numbers, two
        replicas agree, and a replay of the log rebuilds them exactly. Money
        stays `Decimal` and serialises as a string, because a figure a desk
        acts on has to be the figure the ledger holds (I3).
        """
        boards = clarity.insights.dashboards()
        return {
            **boards,
            "note": (
                "Folded from the event log, not read from live objects. A replay "
                "of the log rebuilds these numbers exactly; `events_folded` counts "
                "the events this projection used."
            ),
        }

    # ----------------------------------------------------------------- #
    # Foresight (C4, F06)
    #
    # `/v1/foresight`, not `/v1/simulation`. Plan 10 section 250 says the
    # latter and everything else, including the module, says foresight; plan 10
    # is a chapter 01-17 document and therefore lowest precedence, so the plan
    # is what changes (AGENTS.md section 1).
    #
    # Four permissions, and the separation between them is the point.
    # `foresight:scenario:draft` and `foresight:run` belong to product;
    # `foresight:outcome:record` deliberately does not, because the person who
    # wants the calibration gate open must not be the one recording the evidence
    # that opens it.
    # ----------------------------------------------------------------- #

    @app.post("/v1/foresight/scenarios", tags=["foresight"], status_code=201)
    def draft_scenario(
        body: ScenarioDraftRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.FORESIGHT_SCENARIO_DRAFT))],
    ) -> dict[str, Any]:
        """Draft a scenario. Drafting predicts nothing on its own."""
        version = clarity.foresight_service.draft(_scenario_from(body), by=principal.ref)
        return _scenario_view(version)

    @app.post("/v1/foresight/scenarios/{scenario_id}/versions", tags=["foresight"], status_code=201)
    def revise_scenario(
        scenario_id: str,
        body: ScenarioReviseRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.FORESIGHT_SCENARIO_DRAFT))],
    ) -> dict[str, Any]:
        """Add a version. The previous one stays readable, so a stored run
        still cites what it actually rehearsed."""
        try:
            version = clarity.foresight_service.revise(
                _scenario_from(body, scenario_id=scenario_id), by=principal.ref
            )
        except UnknownScenario as missing:
            raise HTTPException(status_code=404, detail="no such scenario") from missing
        return _scenario_view(version)

    @app.get("/v1/foresight/scenarios", tags=["foresight"])
    def list_scenarios(
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        """The latest version of every scenario family, newest first."""
        return {"scenarios": [_scenario_view(v) for v in clarity.foresight_service.scenarios()]}

    @app.get("/v1/foresight/scenarios/{scenario_id}", tags=["foresight"])
    def read_scenario(
        scenario_id: str,
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        """Every version of one family, oldest first."""
        versions = clarity.foresight_service.versions_of(scenario_id)
        if not versions:
            raise HTTPException(status_code=404, detail="no such scenario")
        return {
            "scenario_id": scenario_id,
            "versions": [_scenario_view(version) for version in versions],
        }

    @app.post("/v1/foresight/runs", tags=["foresight"], status_code=202)
    def request_foresight_run(
        body: ForesightRunRequest,
        response: Response,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.FORESIGHT_RUN))],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
    ) -> dict[str, Any]:
        """Ask for a rehearsal. Answers 202 with a poll URL.

        `Idempotency-Key` is required, not optional (I8). Foresight moves no
        money, so the risk is not a double charge; it is a double finding. Two
        runs of one scenario, reported twice, is how a rehearsal gets counted as
        two pieces of evidence.
        """
        try:
            run, is_new = clarity.foresight_service.request_run(
                body.scenario_version_id, by=principal.ref, idempotency_key=idempotency_key
            )
        except UnknownScenario as missing:
            raise HTTPException(status_code=404, detail="no such scenario version") from missing

        if is_new:
            # The rehearsal runs inline: it is milliseconds of arithmetic, and a
            # queue the prototype has no worker for would leave every run
            # queued forever. The 202 and the poll URL are the contract a
            # serverless batch job keeps when plan 21 moves it (R6/R7), so a
            # caller written today does not change.
            try:
                clarity.foresight_service.execute(run.run_id)
            except RunAlreadyFinished:  # pragma: no cover - just claimed it
                pass
            except CatalogueInvalid as broken:
                raise HTTPException(
                    status_code=503, detail=f"foresight is misconfigured: {broken}"
                ) from broken
            run = clarity.foresight_service.run(run.run_id) or run

        response.headers["Location"] = f"/v1/foresight/runs/{run.run_id}"
        return _run_view(clarity, run, replayed=not is_new)

    @app.get("/v1/foresight/runs", tags=["foresight"])
    def list_foresight_runs(
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        return {"runs": [_run_view(clarity, run) for run in clarity.foresight_service.runs()]}

    @app.get("/v1/foresight/runs/{run_id}", tags=["foresight"])
    def read_foresight_run(
        run_id: str,
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        """The run, and its report once it succeeded. The poll URL."""
        run = clarity.foresight_service.run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="no such run")
        return _run_view(clarity, run, with_report=True)

    @app.post("/v1/foresight/launches", tags=["foresight"], status_code=201)
    def record_launch(
        body: LaunchRecordRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.FORESIGHT_OUTCOME_RECORD))],
    ) -> dict[str, Any]:
        """Record that a rehearsed change shipped.

        A real launch is refused with 403 until C6 lands the capability and the
        evidence check. The refusal is deliberate: an ungated way to write the
        evidence is worth more to somebody wanting a green gate than the gate is
        worth to anybody else.
        """
        try:
            provenance = Provenance(body.provenance)
        except ValueError as bad:
            raise HTTPException(status_code=422, detail="unknown provenance") from bad
        try:
            launch = clarity.foresight_service.record_launch(
                scenario_version_id=body.scenario_version_id,
                provenance=provenance,
                by=principal.ref,
                evidence_ref=body.evidence_ref,
                note=body.note,
            )
        except RealLaunchNotPermitted as refused:
            raise HTTPException(status_code=403, detail=str(refused)) from refused
        except UnknownScenario as missing:
            raise HTTPException(status_code=404, detail="no such scenario version") from missing
        return _launch_view(launch)

    @app.get("/v1/foresight/launches", tags=["foresight"])
    def list_launches(
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        return {"launches": [_launch_view(item) for item in clarity.foresight_service.launches()]}

    @app.post("/v1/foresight/launches/{launch_id}/outcomes", tags=["foresight"], status_code=201)
    def record_outcome(
        launch_id: str,
        body: OutcomeRecordRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.FORESIGHT_OUTCOME_RECORD))],
    ) -> dict[str, Any]:
        """Record one observed theme-segment band. Append-only."""
        try:
            band = VolumeBand(body.band)
        except ValueError as bad:
            raise HTTPException(status_code=422, detail="unknown band") from bad
        try:
            outcome = clarity.foresight_service.record_outcome(
                launch_id=launch_id,
                theme=body.theme,
                segment=body.segment,
                band=band,
                by=principal.ref,
            )
        except KeyError as missing:
            raise HTTPException(status_code=404, detail="no such launch") from missing
        return {
            "outcome_id": outcome.outcome_id,
            "launch_id": outcome.launch_id,
            "theme": outcome.theme,
            "segment": outcome.segment,
            "band": outcome.band.value,
            "recorded_at": outcome.recorded_at.isoformat(),
            "recorded_by": outcome.recorded_by,
        }

    @app.get("/v1/foresight/candidates", tags=["foresight"])
    def list_candidates(
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        """Cluster-derived suggestions, inert until a person confirms one (C7).

        A candidate is not an outcome. A cluster says "these complaints look
        like one cause"; it does not say which rehearsed theme that is or which
        segment complained. Somebody decides that, under their own name.
        """
        return {
            "candidates": [_candidate_view(item) for item in clarity.foresight_loop.candidates()]
        }

    @app.post("/v1/foresight/candidates/{cluster_id}/confirm", tags=["foresight"], status_code=201)
    def confirm_candidate(
        cluster_id: str,
        body: CandidateConfirmRequest,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.FORESIGHT_OUTCOME_RECORD))],
    ) -> dict[str, Any]:
        """Turn a candidate into a recorded outcome, under the caller's name.

        The theme, segment and band come from the person, not from the cluster.
        This is the only way a cluster becomes evidence the calibration gate
        reads, and it needs `foresight:outcome:record`, which `PRODUCT` does not
        hold.
        """
        try:
            band = VolumeBand(body.band)
        except ValueError as bad:
            raise HTTPException(status_code=422, detail="unknown band") from bad
        try:
            outcome = clarity.foresight_service.confirm_candidate(
                cluster_id=cluster_id,
                launch_id=body.launch_id,
                theme=body.theme,
                segment=body.segment,
                band=band,
                by=principal.ref,
            )
        except AlreadyConfirmed as twice:
            raise HTTPException(
                status_code=409, detail="this candidate is already recorded as an outcome"
            ) from twice
        except KeyError as missing:
            raise HTTPException(status_code=404, detail="no such candidate or launch") from missing
        return {
            "outcome_id": outcome.outcome_id,
            "launch_id": outcome.launch_id,
            "theme": outcome.theme,
            "segment": outcome.segment,
            "band": outcome.band.value,
            "recorded_by": outcome.recorded_by,
            "cluster_id": cluster_id,
        }

    @app.get("/v1/foresight/launches/{launch_id}/comparison", tags=["foresight"])
    def launch_comparison(
        launch_id: str,
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        """What the rehearsal said, beside what the launch produced (C7/F10)."""
        comparison = clarity.foresight_service.comparison(launch_id)
        if comparison is None:
            raise HTTPException(status_code=404, detail="no such launch")
        return _comparison_view(comparison)

    @app.post("/v1/foresight/backtests", tags=["foresight"], status_code=201)
    def run_backtest(
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(requires(Permission.FORESIGHT_RUN))],
    ) -> dict[str, Any]:
        """Replay every stored launch through the baseline and keep the result."""
        return _calibration_view(clarity.foresight_service.backtest(by=principal.ref))

    @app.get("/v1/foresight/backtests", tags=["foresight"])
    def list_backtests(
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        return {
            "backtests": [
                _calibration_view(item) for item in clarity.foresight_service.calibrations()
            ]
        }

    @app.get("/v1/foresight/calibration", tags=["foresight"])
    def read_calibration(
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        """The calibration a report would rest on today.

        404 when no backtest has run, rather than a cheerful "not calibrated":
        the two are different, and only one of them has been measured.
        """
        latest = clarity.foresight_service.latest_calibration()
        if latest is None:
            raise HTTPException(status_code=404, detail="no backtest has been run")
        return _calibration_view(latest)

    @app.get("/v1/foresight/spikes", tags=["foresight"])
    def list_spikes(
        clarity: ClarityDep,
        _: Annotated[Principal, Depends(requires(Permission.FORESIGHT_READ))],
    ) -> dict[str, Any]:
        """Early-warning spikes, raised by the radar (C5)."""
        return {"spikes": [_spike_view(item) for item in clarity.foresight_service.spikes()]}


# --------------------------------------------------------------------------- #
# Foresight views (C4)
#
# Every one of these is a rendering of a stored record. None of them computes
# anything: a view that did arithmetic would be a second place a band could be
# decided, and banding belongs to the module under policy thresholds (ADR-0043).
# --------------------------------------------------------------------------- #


def _scenario_from(body: Any, *, scenario_id: str | None = None) -> Scenario:
    """A request body as a domain scenario.

    An unknown change type is a 422 rather than a silent fall-through to an
    empty report: "no themes configured" and "you named a type that does not
    exist" look identical on screen and are not the same problem.
    """
    try:
        change_type = ChangeType(body.change_type)
    except ValueError as bad:
        raise HTTPException(status_code=422, detail="unknown change type") from bad
    fields: dict[str, Any] = {
        "name": body.name,
        "change_type": change_type,
        "effective_date": body.effective_date,
        "affected_share": body.affected_share,
        "severity": body.severity,
        "affected_products": tuple(body.affected_products),
        "business_context": body.business_context,
    }
    if scenario_id is not None:
        fields["scenario_id"] = scenario_id
    return Scenario(**fields)


def _scenario_view(version: ScenarioVersion) -> dict[str, Any]:
    scenario = version.scenario
    return {
        "scenario_id": version.scenario_id,
        "version_id": version.version_id,
        "version": version.version,
        "supersedes": version.supersedes,
        "created_at": version.created_at.isoformat(),
        "created_by": version.created_by,
        "name": scenario.name,
        "change_type": scenario.change_type.value,
        "effective_date": scenario.effective_date.isoformat(),
        "affected_share": str(scenario.affected_share),
        "severity": str(scenario.severity),
        "affected_products": list(scenario.affected_products),
        "business_context": scenario.business_context,
    }


def _run_view(
    clarity: Clarity,
    run: ScenarioRun,
    *,
    with_report: bool = False,
    replayed: bool = False,
) -> dict[str, Any]:
    view: dict[str, Any] = {
        "run_id": run.run_id,
        "scenario_version_id": run.scenario_version_id,
        "status": run.status.value,
        "requested_at": run.requested_at.isoformat(),
        "requested_by": run.requested_by,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "report_id": run.report_id,
        "failure": run.failure,
        "poll_url": f"/v1/foresight/runs/{run.run_id}",
    }
    if replayed:
        # Says plainly that the caller's key matched an earlier request, so a
        # repeat is not mistaken for a second rehearsal (I8).
        view["replayed"] = True
    if with_report:
        stored = clarity.foresight_service.report_of_run(run.run_id)
        view["report"] = _foresight_report_view(stored.report) if stored else None
    return view


def _foresight_report_view(report: ForesightReport) -> dict[str, Any]:
    return {
        "report_id": report.run_id,
        "scenario": report.scenario,
        "scenario_id": report.scenario_id,
        "effective_date": report.effective_date.isoformat() if report.effective_date else None,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "basis": report.basis,
        "caveats": list(report.caveats),
        "backtested": report.backtested,
        "decision_ready": report.is_decision_ready,
        "predictions": [
            {
                "theme": item.theme,
                "segment": item.segment,
                "band": item.band.value,
                "relative_score": str(item.relative_score),
                "mitigation": item.suggested_mitigation,
            }
            for item in report.predictions
        ],
    }


def _launch_view(launch: StoredLaunch) -> dict[str, Any]:
    return {
        "launch_id": launch.launch_id,
        "scenario_version_id": launch.scenario_version_id,
        "provenance": launch.provenance.value,
        "is_real": launch.is_real,
        "evidence_ref": launch.evidence_ref,
        "authority": launch.authority,
        "note": launch.note,
        "recorded_at": launch.recorded_at.isoformat(),
        "recorded_by": launch.recorded_by,
    }


def _calibration_view(stored: StoredCalibration) -> dict[str, Any]:
    report = stored.report
    return {
        "calibration_id": stored.calibration_id,
        "computed_at": stored.computed_at.isoformat(),
        "computed_by": stored.computed_by,
        "launch_ids": list(stored.launch_ids),
        "status": report.status.value,
        "calibrated": report.is_calibrated,
        "launches": report.launches,
        "real_launches": report.real_launches,
        "compared": report.compared,
        # `None` rather than a number, everywhere, when nothing was comparable.
        # A 0.000 would read as a flawless model.
        "mean_absolute_band_error": _opt_str(report.mean_absolute_band_error),
        "signed_band_error": _opt_str(report.signed_band_error),
        "exact_band_rate": _opt_str(report.exact_band_rate),
        "top_theme_hit_rate": _opt_str(report.top_theme_hit_rate),
        # Plan 08 section 12.9's two. Recall is the one that catches the
        # dangerous direction: without it the band error improves as the model
        # predicts less, because what it never predicted is excluded from it.
        "theme_recall": _opt_str(report.theme_recall),
        "segment_rank_correlation": _opt_str(report.segment_rank_correlation),
        "unpredicted": [
            {"theme": o.theme, "segment": o.segment, "band": o.band.value}
            for o in report.unpredicted
        ],
        "unobserved": [{"theme": t, "segment": g} for t, g in report.unobserved],
        "basis": report.basis,
        "caveats": list(report.caveats),
        "summary": report.summary(),
    }


def _spike_view(spike: DetectedSpike) -> dict[str, Any]:
    return {
        "spike_id": spike.spike_id,
        "scope": spike.scope.value,
        # A code, never a name: `_FORBIDDEN_SEGMENTS` rejects a `name` field on
        # the event this becomes, and the view keeps the same discipline.
        "scope_ref": spike.scope_ref,
        "window_start": spike.window_start.isoformat(),
        "window_end": spike.window_end.isoformat(),
        "observed": spike.observed,
        "baseline": str(spike.baseline),
        "ratio": _opt_str(spike.ratio),
        "detected_at": spike.detected_at.isoformat(),
        "basis": spike.basis,
        "caveats": list(spike.caveats),
    }


def _candidate_view(candidate: OutcomeCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "cluster_id": candidate.cluster_id,
        "status": candidate.status,
        "size": candidate.size,
        "rule_id": candidate.rule_id,
        "reviewed_by": candidate.reviewed_by,
        "noticed_at": candidate.noticed_at.isoformat(),
        "confirmed": candidate.is_confirmed,
        "confirmed_by": candidate.confirmed_by,
        "confirmed_at": (candidate.confirmed_at.isoformat() if candidate.confirmed_at else None),
        "outcome_id": candidate.outcome_id,
    }


def _comparison_view(comparison: PostLaunchComparison) -> dict[str, Any]:
    return {
        "launch_id": comparison.launch_id,
        "scenario_version_id": comparison.scenario_version_id,
        "provenance": comparison.provenance,
        "compared": comparison.compared,
        "agreement_rate": _opt_str(comparison.agreement_rate),
        "pairs": [
            {
                "theme": pair.theme,
                "segment": pair.segment,
                "predicted": pair.predicted.value,
                # `null`, never "low": absence of a record is absence of a
                # record, and the backtest refuses to average it in either.
                "observed": pair.observed.value if pair.observed else None,
                "agrees": pair.agrees,
            }
            for pair in comparison.pairs
        ],
        "unpredicted": [{"theme": t, "segment": g} for t, g in comparison.unpredicted],
        "cluster_rates": [
            {
                "cluster_id": rate.cluster_id,
                "size": rate.size,
                "status": rate.status,
                "rule_id": rate.rule_id,
            }
            for rate in comparison.cluster_rates
        ],
        "caveats": list(comparison.caveats),
    }


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _verification_view(clarity: Clarity, receipt_id: str) -> VerificationView:
    receipt = clarity.receipts.get(receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="no such receipt")

    result = clarity.receipts.verify_document(receipt)
    view = clarity.receipts.public_view(receipt)
    # The anchor is reported separately from the receipt's own validity, and
    # deliberately does not affect it: a receipt is a statement about one
    # customer's money, and it stays true whether or not the audit checkpoint it
    # happened to carry still verifies. Conflating them would let an audit-side
    # problem tell a customer their refund never happened.
    anchor = receipt.payload.audit_anchor
    return VerificationView(
        receipt_id=receipt_id,
        audit_anchor_seq=anchor.checkpoint_seq if anchor else None,
        audit_anchor_ok=(
            anchor_verifies(anchor, clarity.audit_checkpoints.public_keys())
            if anchor is not None
            else None
        ),
        status=result.display,
        valid=result.valid,
        reason=result.reason,
        key_id=result.kid,
        chain_ok=result.chain_ok,
        superseded_by=result.superseded_by,
        issued_at=str(view["issued_at"]),
        number=str(view["number"]),
        corrected_lkr=str(view["corrected_lkr"]),
        safeguard=str(view["safeguard"]) if view["safeguard"] else None,
        recurrence_test=str(view["recurrence_test"]) if view["recurrence_test"] else None,
    )


_MONEY_TYPES = {
    EventType.VAS_CHARGE,
    EventType.PAYMENT_CAPTURED,
    EventType.BALANCE_CREDITED,
    EventType.CHARGE_APPLIED,
    EventType.PACK_PURCHASED,
    EventType.PAYMENT_REVERSED,
    EventType.BALANCE_ADJUSTED,
    EventType.SUBSCRIPTION_RENEWED,
}


def _customer_ref(principal: Principal) -> str:
    """The signed-in customer's own subject, after the route's ``self:*`` check.

    The permission itself is declared on each route with ``requires(...)``
    (I9). This only binds the request to the caller's own account; a staff
    token has no subscriber, so it has no "me" to act on.
    """
    if principal.subscriber_ref is None:
        raise HTTPException(status_code=403, detail="only a customer account has a 'me'")
    return principal.subscriber_ref


def _home_for(clarity: Clarity, ref: str) -> dict[str, Any]:
    """Shape the synthetic account into the customer home payload."""
    from decimal import Decimal

    account = clarity.world.account(ref)
    if account is None:
        raise HTTPException(status_code=404, detail="no such account")

    events = [event for records in account.records.values() for event in records]
    events.sort(key=lambda event: event.occurred_at, reverse=True)

    used_gb: Decimal | None = None
    for event in events:
        raw_used = event.attributes.get("used_gb")
        raw_left = event.attributes.get("remaining_gb")
        if raw_used is not None:
            used_gb = Decimal(str(raw_used))
        elif raw_left is not None and account.packs:
            cap = account.packs[0].fup_cap_gb
            if cap is not None:
                used_gb = cap - Decimal(str(raw_left))

    pack_view: dict[str, Any] | None = None
    alerts: list[dict[str, str]] = []
    active = next((pack for pack in account.packs if pack.active), None)
    if active is not None:
        cap = active.fup_cap_gb
        pct = None
        if cap is not None and cap > 0 and used_gb is not None:
            pct = int((used_gb / cap) * 100)
        days_left = (active.expires_at - clarity.world.now).days
        pack_view = {
            "name": active.name,
            "price_lkr": str(active.price_lkr),
            "purchased_at": active.purchased_at.isoformat(),
            "expires_at": active.expires_at.isoformat(),
            "days_left": days_left,
            "data_gb": str(cap) if cap is not None else None,
            "used_gb": str(used_gb) if used_gb is not None else None,
            "used_pct": pct,
            "after_cap_speed": active.after_cap_speed,
            "disclosed": active.fup_disclosed_at_purchase,
            "apps": "All apps",
            "restrictions": (
                f"Speed drops to {active.after_cap_speed} after the fair-use cap."
                if active.after_cap_speed
                else "No extra speed restriction on this pack."
            ),
            "renewal": "Does not renew by itself.",
            "after_expiry": "If data stays on, later use can draw from your main balance.",
        }
        if pct is not None and pct >= 95:
            alerts.append({"kind": "fup", "text": "Fair-use is at or past 95%."})
        elif pct is not None and pct >= 80:
            alerts.append({"kind": "fup", "text": "Fair-use has passed 80%."})
        if any(event.event_type is EventType.FUP_CAP_REACHED for event in events):
            alerts.append(
                {
                    "kind": "fup",
                    "text": "This pack has hit its fair-use cap. Data is slowed, not cut off.",
                }
            )
        if days_left <= 5:
            alerts.append({"kind": "pack", "text": f"This pack expires in {days_left} day(s)."})

    for sub in account.subscriptions:
        if sub.active and sub.otp_verified_at is None:
            alerts.append(
                {
                    "kind": "charge",
                    "text": (
                        f"{sub.merchant_name} charged LKR {sub.price_lkr} without a confirmation."
                    ),
                }
            )

    open_case = next(
        (
            record
            for record in clarity.cases.all_cases()
            if record.subscriber_ref == ref and record.case.state is not CaseState.CLOSED
        ),
        None,
    )
    decision = open_case.decision if open_case is not None else None
    if decision is not None and decision.outcome.value in {"STAFF_APPROVAL", "HANDOFF"}:
        alerts.append({"kind": "case", "text": "A case is waiting for Hutch staff."})

    shown = _MONEY_TYPES | {
        EventType.DATA_SESSION,
        EventType.FUP_CAP_REACHED,
        EventType.THROTTLE_APPLIED,
        EventType.USAGE_THRESHOLD_CROSSED,
    }
    activity = []
    for event in events:
        if event.event_type not in shown:
            continue
        attrs = event.attributes
        reason = str(attrs.get("reason") or "")
        if event.event_type is EventType.PACK_PURCHASED:
            bucket = "packages"
        elif event.event_type in {
            EventType.DATA_SESSION,
            EventType.FUP_CAP_REACHED,
            EventType.THROTTLE_APPLIED,
            EventType.USAGE_THRESHOLD_CROSSED,
        }:
            bucket = "usage"
        elif event.event_type is EventType.PAYMENT_CAPTURED or reason == "reload":
            bucket = "reloads"
        elif event.event_type is EventType.BALANCE_CREDITED:
            bucket = "refunds"
        else:
            bucket = "charges"
        activity.append(
            {
                "id": event.event_id,
                "at": event.occurred_at.isoformat(),
                "type": event.event_type.value,
                "bucket": bucket,
                "amount_lkr": str(event.amount_lkr) if event.amount_lkr is not None else None,
                "source": event.source.value,
                "detail": str(
                    attrs.get("merchant_name")
                    or attrs.get("product")
                    or attrs.get("offering_id")
                    or attrs.get("reason")
                    or event.event_type.value.replace("_", " ")
                ),
                "balance_before": attrs.get("balance_before"),
                "balance_after": attrs.get("balance_after"),
                "status": str(attrs.get("status") or "posted"),
                "subscription_id": attrs.get("subscription_id"),
            }
        )

    return {
        "name": account.name,
        "msisdn": account.msisdn,
        "masked": account.masked,
        "language": account.language.value,
        "notify": account.notify,
        "large_text": account.large_text,
        "onboarded": account.onboarded,
        "balance_lkr": str(account.balance_lkr),
        "pack": pack_view,
        "subscriptions": [
            {
                "id": sub.subscription_id,
                "name": sub.product,
                "merchant": sub.merchant_name,
                "merchant_id": sub.merchant_id,
                "price_lkr": str(sub.price_lkr),
                "active": sub.active,
                "consent": sub.otp_verified_at is not None,
                "renewal": "Renews until you cancel.",
                "charges": [
                    row["amount_lkr"]
                    for row in activity
                    if row.get("subscription_id") == sub.subscription_id and row["amount_lkr"]
                ],
            }
            for sub in account.subscriptions
        ],
        "activity": activity,
        "alerts": alerts,
        "open_case_id": open_case.case_id if open_case else None,
        "open_case_state": open_case.case.state.value if open_case else None,
    }


def _app_for(clarity: Clarity, ref: str) -> dict[str, Any]:
    """One payload for Home, Usage, Clarity, Activity and More."""
    home = _home_for(clarity, ref)
    account = clarity.world.account(ref)
    if account is None:
        raise HTTPException(status_code=404, detail="no such account")

    cases: list[dict[str, Any]] = []
    mine: set[str] = set()
    for record in clarity.cases.all_cases():
        if record.subscriber_ref != ref:
            continue
        mine.add(record.case_id)
        cases.append(
            {
                "case_id": record.case_id,
                "case_no": record.case.case_no,
                "state": record.case.state.value,
                "opened_at": record.case.opened_at.isoformat(),
                "outcome": record.decision.outcome.value if record.decision else None,
                "headline": (
                    record.decision.rationale[0]
                    if record.decision and record.decision.rationale
                    else None
                ),
                "open": record.case.state is not CaseState.CLOSED,
            }
        )
    cases.sort(key=lambda row: str(row["opened_at"]), reverse=True)

    receipts: list[dict[str, Any]] = []
    ref_hash = hash_payload(ref)
    for issued in reversed(clarity.receipts.issued()):
        belongs = issued.case_id in mine or (issued.payload.subject.subscriber_ref_hash == ref_hash)
        if not belongs:
            continue
        corrected = issued.payload.total_corrected_lkr
        receipts.append(
            {
                "receipt_id": issued.receipt_id,
                "issued_at": issued.payload.issued_at.isoformat(),
                "corrected_lkr": str(corrected) if corrected is not None else "0.00",
                "summary": issued.payload.what_happened.summary,
                "case_id": issued.case_id,
            }
        )

    notifications = [{"kind": alert["kind"], "text": alert["text"]} for alert in home["alerts"]]
    for case in cases[:5]:
        notifications.append(
            {
                "kind": "case",
                "text": f"Case {case['case_no']} is {str(case['state']).replace('_', ' ')}.",
            }
        )
    for row in receipts[:5]:
        notifications.append(
            {
                "kind": "receipt",
                "text": f"Trust Receipt {row['receipt_id']} is ready.",
                "receipt_id": row["receipt_id"],
            }
        )

    family = []
    for number in account.family:
        other = clarity.world.account_by_msisdn(number)
        if other is None:
            continue
        active = next((pack for pack in other.packs if pack.active), None)
        family.append(
            {
                "name": other.name,
                "masked": other.masked,
                "msisdn": other.msisdn,
                "pack": active.name if active else None,
                "safeguards": [key for key in other.safeguards if not str(key).startswith("_")],
            }
        )

    network = account.safeguards.get("_network")
    if not isinstance(network, dict):
        network = {"status": "clear", "text": "No outage in your area.", "eta": None}

    return {
        **home,
        "catalogue": CATALOGUE,
        "safeguards": {
            key: (value.get("value") if isinstance(value, dict) else value)
            for key, value in account.safeguards.items()
            if not str(key).startswith("_")
        },
        "blocked_merchants": sorted(account.blocked_merchants),
        "cases": cases,
        "receipts": receipts,
        "notifications": notifications,
        "network": {
            "status": network.get("status") or "clear",
            "text": network.get("text") or "No outage in your area.",
            "eta": network.get("eta"),
        },
        "family": family,
        "usage": {
            "data_used_gb": home["pack"]["used_gb"] if home["pack"] else None,
            "data_cap_gb": home["pack"]["data_gb"] if home["pack"] else None,
            "voice_minutes": 0,
            "sms": 0,
        },
    }
