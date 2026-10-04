"""Authentication and authorization for the HTTP API (plan §19, ADR-0010).

Three rules, enforced here so no route can forget them:

1. **Deny by default.** A route states the permission it needs. There is no
   way to declare "open" by omission; `public` is explicit and visible.
2. **Subject binding.** A customer's token names one ``subscriber_ref``, and
   that is the only subject whose cases they can reach. Holding a case id is
   not authorisation to read it.
3. **Step-up for money.** Approving above the cap needs recent MFA, not just a
   valid session.

Failures are deliberately plain: 401 when we do not know who you are, 403 when
we do and you may not. Neither says which case exists.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from clarity.interfaces.http.cookies import CUSTOMER_COOKIE, STAFF_COOKIE
from clarity.modules.iam.public import (
    AuthorizationPolicy,
    TokenInvalid,
    TokenVerifier,
)

#: Permissions that require recent re-authentication.
from clarity.platform.security.principal import (
    ANONYMOUS,
    STEP_UP_PERMISSIONS,
    Assurance,
    Permission,
    Principal,
    Role,
)


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="sign in to continue",
        headers={"WWW-Authenticate": "Bearer"},
    )


_log = logging.getLogger("clarity.http.auth")


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=403, detail=detail)


def _unavailable() -> HTTPException:
    """The server cannot decide this request.

    503, not 401 or 403. Both of those say something about the caller, and the
    caller has done nothing wrong: a missing verifier or a missing policy is a
    wiring fault, and reporting it as a refusal sends somebody to look at
    credentials that are fine.
    """
    return HTTPException(status_code=503, detail="authorization is unavailable")


def principal_from(request: Request, authorization: str | None) -> Principal:
    """Build the principal from the bearer token or the staff cookie.

    **Two carriers, one token.** The header is what the MCP server, the channel
    gateway and the customer app send. The cookie is what the staff console
    sends after signing in through the provider (B1): the value is the same
    Clarity staff token, kept somewhere JavaScript cannot read it, because the
    console is the surface that approves refunds.

    The header wins when both are present. A caller who went to the trouble of
    sending one is being explicit, and a stale cookie silently overriding it
    would be the harder bug to find.

    **Why a cookie does not open a CSRF hole here.** It is `SameSite=Lax`, so
    another origin cannot drive a state-changing request with it, and the API
    pins CORS to the console's own origin rather than echoing any. The one
    thing Lax still permits from elsewhere is a top-level GET, and no GET on
    this API changes anything.
    """
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    else:
        token = (
            request.cookies.get(STAFF_COOKIE) or request.cookies.get(CUSTOMER_COOKIE) or ""
        ).strip()
    if not token:
        return ANONYMOUS

    verifier: TokenVerifier | None = getattr(request.app.state, "token_verifier", None)
    if verifier is None:
        # A token arrived and nothing can check it. Treating that as anonymous
        # is the wrong way round: the caller presented a credential, so the
        # honest answer is that this request cannot be authenticated, not that
        # it was made by nobody. Silently downgrading would turn a wiring fault
        # into an authorization decision, and the route would then refuse with
        # a 401 that blames the caller for a server defect.
        _log.error("a token was presented but no verifier is wired")
        raise _unavailable()

    try:
        principal = verifier.verify(token)
    except TokenInvalid as error:
        raise _unauthenticated() from error
    # Audit duties held by grant (Phase 3). Applied here, once, so every check
    # after this, route dependency or handler, sees the same permissions.
    grants = getattr(request.app.state, "audit_grants", None)
    return grants.apply(principal) if grants is not None else principal


async def current_principal(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    """The caller, as proven by their token. Anonymous if they have none."""
    return principal_from(request, authorization)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def requires(permission: Permission) -> Callable[..., Awaitable[Principal]]:
    """Declare the permission a route needs.

    Used as a dependency, so a route cannot be mounted without stating what it
    requires:

        @app.get("/v1/desk/queue", dependencies=[Depends(requires(Permission.DESK_QUEUE_READ))])
    """

    async def dependency(request: Request, principal: CurrentPrincipal) -> Principal:
        if principal is ANONYMOUS or not principal.roles:
            raise _unauthenticated()
        policy: AuthorizationPolicy | None = getattr(
            request.app.state, "authorization_policy", None
        )
        if policy is None:
            # This used to fall back to a fresh `PythonAuthorizationPolicy()`.
            # In a deployment that configures OPA, a missing app state would
            # have meant every decision silently reverted to the local driver:
            # the same answers today, and a different authority than the one
            # operations believes is deciding, with nothing in the logs. An
            # authorization driver is not something to improvise per request.
            _log.error("no authorization policy is wired; refusing the request")
            raise _unavailable()
        if policy.allows(principal, permission):
            return principal
        if (
            permission in STEP_UP_PERMISSIONS
            and principal.has(permission)
            and not principal.assurance.is_step_up
        ):
            raise _forbidden(f"{permission.value} needs recent re-authentication (step-up)")
        raise _forbidden(f"this account may not {permission.value}")

    return dependency


def public() -> Callable[..., Awaitable[Principal]]:
    """Declare a route deliberately open.

    Only the receipt verification page and the service endpoints use this. It
    is a dependency rather than an omission so that "no auth here" is a visible
    decision in the route table.
    """

    async def dependency(principal: CurrentPrincipal) -> Principal:
        return principal

    return dependency


def authorize_case_access(principal: Principal, subscriber_ref: str) -> None:
    """Subject binding. Raises 403 if this caller may not see this subject.

    A customer holding someone else's case id gets the same refusal as any
    other caller, so the id itself grants nothing.
    """
    if not principal.may_read(subscriber_ref):
        raise _forbidden("this account may not read that case")


def authorize_action(principal: Principal, *, amount_lkr: object, cap: object) -> None:
    """Approving above the cap needs step-up, whatever the role."""
    try:
        over_cap = amount_lkr is not None and cap is not None and amount_lkr > cap  # type: ignore[operator]
    except TypeError:  # pragma: no cover - amounts are always comparable
        over_cap = True

    needed = Permission.ACTION_APPROVE_HIGH_VALUE if over_cap else Permission.ACTION_APPROVE
    if not principal.has(needed):
        raise _forbidden(f"this account may not {needed.value}")
    if over_cap and not principal.assurance.is_step_up:
        raise _forbidden("approving above the cap needs recent re-authentication")


def customer_can_act(principal: Principal) -> None:
    """A customer confirming a fix must have proven their number.

    A claimed WhatsApp number or a network-asserted MSISDN is enough to be told
    things, not enough to change them (plan §17 5.2).
    """
    if not principal.has(Permission.ACTION_CONFIRM_OWN):
        raise _forbidden("this account may not confirm actions")
    if not principal.assurance.can_act:
        raise _forbidden(
            "confirming a fix needs a verified number; "
            f"this session is '{principal.assurance.value}'"
        )


__all__ = [
    "ANONYMOUS",
    "Assurance",
    "CurrentPrincipal",
    "Permission",
    "Principal",
    "Role",
    "authorize_action",
    "authorize_case_access",
    "current_principal",
    "customer_can_act",
    "public",
    "requires",
]
