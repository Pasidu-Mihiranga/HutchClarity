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

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import Response as RawResponse
from fastapi.staticfiles import StaticFiles

from clarity.app.container import Clarity, Profile
from clarity.contracts.case import CaseState
from clarity.contracts.decision import Outcome, PlanStatus
from clarity.contracts.timeline import EventType
from clarity.integration.drivers.mock.world import CATALOGUE, ref_for
from clarity.interfaces.http.auth import (
    ANONYMOUS,
    CurrentPrincipal,
    Permission,
    Principal,
    authorize_action,
    authorize_case_access,
    customer_can_act,
    public,
    requires,
)
from clarity.interfaces.http.schemas import (
    ActionView,
    ApproveRequest,
    CaseSummary,
    CauseView,
    ConfirmRequest,
    DecisionView,
    DemoSubscriber,
    ExecutionView,
    FamilyRequest,
    MerchantSuspendRequest,
    OpenCaseRequest,
    OtpRequest,
    OtpVerify,
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
    SessionView,
    SourceStatusView,
    StaffSignIn,
    SwitchFlipRequest,
    TimelineEventView,
    TimelineView,
    VerificationView,
)
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import Language, mask_msisdn, normalise_msisdn
from clarity.kernel.ids import new_id
from clarity.modules.actions.public import ToolLayerError
from clarity.modules.case.public import CaseNotFound, CaseNotReady, CaseRecord
from clarity.modules.governance.public import ChangeRefused, ImpactReport, PolicyChange
from clarity.modules.iam.public import OtpRefused, SimulatedInbox, TokenInvalid
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

_app_state: dict[str, Clarity] = {}


def get_clarity() -> Clarity:
    """The single assembled core this process serves."""
    if "clarity" not in _app_state:
        _app_state["clarity"] = Clarity()
    return _app_state["clarity"]


ClarityDep = Annotated[Clarity, Depends(get_clarity)]


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


def create_app(clarity: Clarity | None = None) -> FastAPI:
    if clarity is not None:
        _app_state["clarity"] = clarity

    app = FastAPI(
        title="Hutch Clarity API",
        version="0.1.0",
        description=(
            "Explain every rupee. Fix it by rule. Prove it won't happen again. "
            "PROTOTYPE: all HUTCH systems are mocked and all data is synthetic."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # prototype only; production restricts to HUTCH origins
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(_trace_requests)
    # Authentication and authorization are profile-selected drivers. Lite uses
    # local JWT/Python drivers; full may use Keycloak and OPA.
    core = clarity or get_clarity()
    app.state.token_verifier = core.token_verifier
    app.state.authorization_policy = core.authorization
    _register_handlers(app)
    _register_routes(app)
    _register_pages(app)
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

    @app.post("/v1/demo/reset", tags=["demo"], dependencies=[Depends(demo_only)])
    def demo_reset() -> dict[str, Any]:
        """Rebuild the synthetic world so the demo can be run again cleanly.

        Running a journey refunds balances and switches subscriptions off, so a
        second run would start from the first run's state. Prototype only: there
        is no such thing in production.
        """
        _app_state["clarity"] = get_clarity().reset()
        return {"status": "reset", "detail": "synthetic world and all cases rebuilt"}

    # ------------------------------------------------------------------ #
    # Sign in
    # ------------------------------------------------------------------ #

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

        if clarity.world.account_by_msisdn(msisdn) is None:
            raise HTTPException(status_code=404, detail="We could not find this Hutch number.")

        try:
            challenge_id = clarity.otp.request(msisdn)
        except OtpRefused as error:
            raise HTTPException(status_code=429, detail=str(error)) from error

        return {
            "challenge_id": challenge_id,
            "sent_to": mask_msisdn(msisdn),
            "simulated": True,
            "detail": "A simulated SMS was written to the demo inbox.",
        }

    @app.get("/v1/demo/inbox", tags=["demo"], dependencies=[Depends(demo_only)])
    def demo_inbox(clarity: ClarityDep, msisdn: str) -> dict[str, Any]:
        """The simulated SMS inbox. Prototype only, and labelled everywhere."""
        inbox = clarity.otp.delivery
        message = inbox.latest_for(msisdn) if isinstance(inbox, SimulatedInbox) else None
        if message is None:
            raise HTTPException(status_code=404, detail="no simulated message for that number")
        return message

    @app.post("/v1/auth/otp/verify", response_model=SessionView, tags=["auth"])
    def verify_otp(body: OtpVerify, clarity: ClarityDep) -> SessionView:
        """Exchange a correct code for a short-lived customer token."""
        try:
            msisdn = clarity.otp.verify(body.challenge_id, body.code)
        except OtpRefused as error:
            raise HTTPException(status_code=401, detail=str(error)) from error

        account = clarity.world.account_by_msisdn(msisdn)
        if account is None:
            raise HTTPException(status_code=404, detail="We could not find this Hutch number.")

        issued = clarity.tokens.for_customer(
            account.ref, assurance=Assurance.OTP, channel=body.channel.value
        )
        return SessionView(
            token=issued.value,
            refresh_token=issued.refresh_token,
            expires_at=issued.expires_at,
            subject=account.masked,
            roles=["customer"],
            assurance=issued.principal.assurance.value,
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

        **Simulated.** Production federates HUTCH SSO (Keycloak over AD/Entra)
        behind this same interface; there is no password here, which is why
        the Desk labels the role picker as a demo control.
        """
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
            raise HTTPException(status_code=401, detail=str(error)) from error
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
        return {"keys": [clarity.tokens.public_key_jwk()]}

    @app.get(
        "/v1/demo/subscribers",
        response_model=list[DemoSubscriber],
        tags=["demo"],
        dependencies=[Depends(demo_only)],
    )
    def demo_subscribers(clarity: ClarityDep) -> list[DemoSubscriber]:
        """Prototype only: the synthetic customers shipped with the demo."""
        scenarios = {
            "+94771234567": "VAS charged with no consent",
            "+94772223333": "Reload taken twice",
            "+94773334444": "'Unlimited' hit a fair-use cap",
            "+94774445555": "Large reload not credited, recent SIM swap",
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
        msisdn = body.subscriber_msisdn or "0771234567"
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
    def knowledge_search(q: str = "") -> dict[str, Any]:
        """Keyword search over how-to articles. Never opens a charge case."""
        from clarity.integration.drivers.mock.store.knowledge import (
            KNOWLEDGE_ARTICLES,
            classify_intent,
        )

        articles: list[dict[str, Any]] = []
        try:
            from clarity.integration.drivers.mock.store import search_knowledge, session_scope

            with session_scope() as session:
                articles = search_knowledge(session, q)
        except Exception:
            articles = []
        if not articles:
            # In-memory fallback for DEMO profile (no DB).
            hay = q.lower()
            scored: list[tuple[int, dict[str, Any]]] = []
            for article in KNOWLEDGE_ARTICLES:
                blob = (
                    f"{article['title']} {article['body']} {' '.join(article['keywords'])}"
                ).lower()
                score = sum(
                    2 for token in hay.replace("?", " ").split() if len(token) > 1 and token in blob
                )
                if score:
                    scored.append((score, article))
            scored.sort(key=lambda item: item[0], reverse=True)
            articles = [item for _, item in scored[:5]]
        return {"query": q, "intent": classify_intent(q), "articles": articles}

    @app.post("/v1/clarity/route", tags=["knowledge"])
    def clarity_route(body: dict[str, Any]) -> dict[str, Any]:
        """Server intent: account vs knowledge vs both (legacy) + chat taxonomy."""
        from clarity.integration.drivers.mock.store.knowledge import classify_intent
        from clarity.modules.conversation.public import handle_turn

        question = str(body.get("question") or "")
        legacy = classify_intent(question)
        articles: list[dict[str, Any]] = []
        if legacy in {"knowledge", "both"}:
            articles = knowledge_search(question).get("articles") or []
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
            )
            payload = turn.to_dict()
            route = turn.intake.route
        else:
            result = handle_turn(
                text,
                case_id=None,
                facts=facts,
                language_hint=body.get("language"),
                intent_override=body.get("intent"),
            )
            payload = result.to_dict()
            route = result.intake.route

        # Attach knowledge articles when route needs them.
        if route in {"knowledge", "both"}:
            payload["articles"] = knowledge_search(text).get("articles") or []
        return {"turn": payload}

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
        "/v1/demo/ops",
        tags=["demo"],
        dependencies=[Depends(requires(Permission.DESK_QUEUE_READ))],
    )
    def demo_ops(clarity: ClarityDep) -> dict[str, Any]:
        """Case counts already in memory. Empty until someone creates demo cases."""
        records = [record for record in clarity.cases.all_cases() if record.decision is not None]
        by_outcome: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        money = 0.0
        for record in records:
            assert record.decision is not None
            key = record.decision.outcome.value
            by_outcome[key] = by_outcome.get(key, 0) + 1
            stake = record.case.money_at_stake_lkr
            if stake is not None:
                money += float(stake)
            if record.decision.handoff_reason is not None:
                reason = record.decision.handoff_reason.value
                by_reason[reason] = by_reason.get(reason, 0) + 1
        return {
            "cases": len(clarity.cases.all_cases()),
            "decided": len(records),
            "money_at_stake_lkr": f"{money:.2f}",
            "by_outcome": by_outcome,
            "handoff_reasons": by_reason,
            "note": "Counts from cases in this process. Create demo cases if this is empty.",
        }

    @app.get(
        "/v1/demo/autopsy",
        tags=["demo"],
        dependencies=[Depends(requires(Permission.DESK_QUEUE_READ))],
    )
    def demo_autopsy(clarity: ClarityDep) -> dict[str, Any]:
        """Run Complaint Autopsy on generated historical complaints when seeded."""
        from clarity.modules.autopsy.public import Complaint, ComplaintAutopsy

        texts: list[str] = list(_DEMO_COMPLAINTS)
        try:
            from clarity.integration.drivers.mock.store import list_complaints, session_scope

            with session_scope() as session:
                stored = list_complaints(session)
            if stored:
                texts = [row["text"] for row in stored]
        except Exception:
            texts = list(_DEMO_COMPLAINTS)

        complaints = [
            Complaint(complaint_id=f"c-{index}", text=text)
            for index, text in enumerate(texts, start=1)
        ]
        report = ComplaintAutopsy().run(complaints)
        return {
            "run_id": report.run_id,
            "total_received": report.total_received,
            "duplicates_removed": report.duplicates_removed,
            "hypothesis": True,
            "clusters": [
                {
                    "label": cluster.label,
                    "size": cluster.size,
                    "status": cluster.status.value,
                    "suggested_rule_id": cluster.suggested_rule_id,
                }
                for cluster in report.clusters
            ],
            "noise": len(report.noise),
            "note": "Hypotheses until a person reviews them. Clustering here is not embeddings.",
        }

    @app.get(
        "/v1/demo/foresight",
        tags=["demo"],
        dependencies=[Depends(requires(Permission.DESK_QUEUE_READ))],
    )
    def demo_foresight() -> dict[str, Any]:
        """Rehearse retiring a pack. Scenarios, not certainties."""
        from clarity.modules.foresight.public import ChangeType, Foresight, Scenario

        report = Foresight().run(
            Scenario(name="Retire Unlimited Data", change_type=ChangeType.PACK_RETIRED)
        )
        return {
            "run_id": report.run_id,
            "scenario": report.scenario,
            "backtested": report.backtested,
            "basis": report.basis,
            "caveats": report.caveats,
            "predictions": [
                {
                    "theme": item.theme,
                    "segment": item.segment,
                    "band": item.band.value,
                    "mitigation": item.suggested_mitigation,
                }
                for item in report.predictions
                if item.band.value != "low"
            ],
            "note": "Scenarios, not certainties. This does not change any customer.",
        }


def _verification_view(clarity: Clarity, receipt_id: str) -> VerificationView:
    receipt = clarity.receipts.get(receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="no such receipt")

    result = clarity.receipts.verify_document(receipt)
    view = clarity.receipts.public_view(receipt)
    return VerificationView(
        receipt_id=receipt_id,
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

_DEMO_COMPLAINTS = (
    "VAS game subscription charged with no OTP",
    "daily game subscription deducted again",
    "reload taken twice from my bank",
    "the same reload was captured two times",
    "unlimited data became slow after the cap",
    "fup speed dropped on my unlimited pack",
    "balance disappeared after the pack ended",
    "money gone from balance when the pack expired",
    "wrong pack was activated",
    "I bought a different pack and it was not activated",
    "no reply from support after a week",
    "still waiting, no response on WhatsApp",
)


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


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _register_pages(app: FastAPI) -> None:
    """Serve the UI from the same process as the API.

    **Prototype simplification.** Plan §21 specifies Next.js/TypeScript for
    production; here the pages are plain HTML and vanilla JS served by FastAPI,
    so the whole prototype runs from one command with no Node toolchain. The
    pages only consume the public `/v1` API, so replacing them with the Next.js
    app changes nothing on the server.
    """
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def customer_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/desk", include_in_schema=False)
    def desk_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "desk.html")

    @app.get("/ops", include_in_schema=False)
    @app.get("/autopsy", include_in_schema=False)
    @app.get("/foresight", include_in_schema=False)
    def desk_section() -> FileResponse:
        """Insights, Autopsy and Foresight share the Desk page."""
        return FileResponse(STATIC_DIR / "desk.html")

    @app.get("/verify", include_in_schema=False)
    def verify_landing() -> FileResponse:
        """Bottom-tab landing for checking a Trust Receipt."""
        return FileResponse(STATIC_DIR / "verify.html")

    @app.get("/v/{receipt_id}", include_in_schema=False)
    @app.get("/v", include_in_schema=False)
    def verify_page(receipt_id: str = "") -> FileResponse:
        """Where a receipt QR code points."""
        return FileResponse(STATIC_DIR / "verify.html")
