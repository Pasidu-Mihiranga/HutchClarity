"""Staff sign-in and step-up through the OpenID Provider (B1, B2, B3).

Four routes, and a cookie.

``GET  /v1/auth/staff/oidc/start``     send the browser to the provider
``GET  /v1/auth/staff/oidc/callback``  take the code back, mint a session
``POST /v1/auth/staff/step-up``        the same trip, at a higher level
``POST /v1/auth/logout``               end the session here and at the provider

**The cookie, and why there is one.** The console used to keep a bearer token
in `sessionStorage`, where any script on the page can read it, on the surface
that approves refunds. The session cookie here is `HttpOnly`, so JavaScript
cannot read it, `SameSite=Lax`, so another site cannot drive a state change
with it, and `Secure` wherever the deployment is not plain local http. The
value is the same Clarity staff token `TokenIssuer` has always minted: one
issuer for staff sessions whatever proved the identity, so revocation, the
audit trail and `STEP_UP_WINDOW` all keep working unchanged.

**Why the API is the client and not the console.** See `modules/iam/oidc.py`.
The short version: a public client with PKCE would put a role-carrying access
token into JavaScript, and this is a money path.

**What is still simulated.** The provider is a local Keycloak with synthetic
accounts and published development passwords (I16). Production federates HUTCH
SSO. **REQUIRES HUTCH CONFIRMATION.**
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from urllib.parse import urlencode, urlparse

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from clarity.app.container import Profile
from clarity.interfaces.http import trail
from clarity.interfaces.http.auth import ANONYMOUS, current_principal, requires
from clarity.interfaces.http.cookies import ID_TOKEN_COOKIE, STAFF_COOKIE
from clarity.interfaces.http.deps import ClarityDep
from clarity.kernel.common import utc_now
from clarity.modules.iam.public import (
    LOA_MFA,
    LOA_PASSWORD,
    OidcError,
    TokenInvalid,
    nonce_matches,
)
from clarity.platform.audit.ledger import ActorKind, AuditEventType
from clarity.platform.security.principal import Permission, Principal

_log = logging.getLogger("clarity.auth.sso")


def _safe_return_to(value: str | None, console_base: str) -> str:
    """Where to send the browser after a sign-in.

    Only a path on the console's own origin. An open redirect on a sign-in
    endpoint is how a phishing page borrows a real login screen, and the
    `return_to` is the one part of this flow an attacker gets to choose.
    """
    if not value:
        return console_base
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return console_base
    if not value.startswith("/"):
        return console_base
    return f"{console_base.rstrip('/')}{value}"


def _bearer(request: Request) -> str:
    """The token this request arrived with, from either carrier."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return (request.cookies.get(STAFF_COOKIE) or "").strip()


def _session_id(clarity: Any, request: Request) -> str | None:
    """Which stored session this request is using.

    Read from the request's own token, because that is the only thing that
    identifies one session among several. An earlier version guessed from the
    subject's session list and only worked when there was exactly one, which
    is precisely the case "sign out everywhere" is not for.
    """
    token = _bearer(request)
    return clarity.tokens.session_id(token) if token else None


def _set_session_cookie(response: Response, token: str, *, secure: bool, max_age: int) -> None:
    response.set_cookie(
        STAFF_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


#: Any signed-in staff member may begin a step-up. The permission that the
#: step-up is *for* is checked where it is used, by the route that needs it;
#: gating the request itself on a money permission would stop a supervisor
#: re-authenticating before they had the assurance to be allowed to.
StaffPrincipal = Annotated[Principal, Depends(requires(Permission.DESK_QUEUE_READ))]


def register(app: FastAPI) -> None:
    """Register the SSO routes on the app.

    Directly on `app`, not through an `APIRouter`. FastAPI wraps an included
    router in an opaque `_IncludedRouter` with no `path`, so every route
    inside one is invisible to anything walking `app.routes`. The route
    classification test is one of those things, and it is what enforces I9:
    a route added through a router would be exempt from declaring who may
    call it, silently.

    Takes nothing: every dependency is a module-level import. `main` imports
    this module, so nothing here may import `main`, and the pieces this flow
    needs (the core, the trail, the audit vocabulary, `requires`) all live in
    modules that do not.
    """

    def _enabled(clarity: Any) -> Any:
        if clarity.oidc is None:
            # Not an error the caller can fix, and not a hint worth giving:
            # staff SSO is either configured or the deployment uses the
            # development sign-in. 404 rather than 503 for the same reason
            # `demo_only` uses 404.
            raise HTTPException(status_code=404, detail="not found")
        return clarity.oidc

    @app.get("/v1/auth/sign-in-methods", tags=["auth"])
    def sign_in_methods(clarity: ClarityDep) -> dict[str, Any]:
        """How staff may sign in to this deployment.

        The console has to know, because the two paths look nothing alike: one
        is a redirect to the provider, the other a form. Asking is better than
        guessing, and better than the console carrying its own build-time
        setting that can disagree with what the API is actually configured for.

        Public: it names mechanisms, not people, and a caller who cannot sign
        in learns only what they would see on the sign-in screen anyway.
        """
        return {
            "provider": clarity.oidc is not None,
            "directory": clarity.staff_directory is not None,
            # The role picker is the development fallback, and it is already
            # 404 in `prod` and gone once a directory is configured.
            "development_role_picker": (
                clarity.staff_directory is None and clarity.profile is not Profile.PROD
            ),
            # The customer sign-in page shows the synthetic fallback number
            # only when the API will accept it.
            "customer_fallback": bool(getattr(clarity, "synthetic_fallback_enabled", False)),
        }

    @app.get("/v1/auth/staff/oidc/start", tags=["auth"])
    def start(clarity: ClarityDep, return_to: str = "/") -> RedirectResponse:
        """Begin a staff sign-in. Public by necessity: nobody is signed in yet."""
        oidc = _enabled(clarity)
        target = _safe_return_to(return_to, clarity.settings.console_base_url)
        url, _pending = oidc.start(return_to=target, loa=LOA_PASSWORD)
        return RedirectResponse(url, status_code=303)

    @app.get("/v1/auth/staff/oidc/callback", tags=["auth"])
    def callback(
        request: Request,
        clarity: ClarityDep,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> RedirectResponse:
        """Take the authorization code back and mint a Clarity staff session."""
        oidc = _enabled(clarity)
        console = clarity.settings.console_base_url

        if error or not code or not state:
            # The provider refused, or the browser arrived without a code.
            # Back to the console with a code it can show, never the
            # provider's own text: that is attacker-influenced content.
            _log.info("staff sso callback refused: %s", error or "missing code")
            return RedirectResponse(f"{console}?{urlencode({'sso': 'failed'})}", status_code=303)

        try:
            pending = oidc.take(state)
            tokens = oidc.exchange(code, pending)
        except OidcError as refused:
            _log.warning("staff sso exchange failed: %s", refused.code)
            return RedirectResponse(f"{console}?{urlencode({'sso': 'failed'})}", status_code=303)

        # Replay check before anything is trusted: an id token minted for a
        # different request must not complete this one.
        if tokens.id_token is not None and not nonce_matches(tokens.id_token, pending.nonce):
            _log.warning("staff sso nonce mismatch")
            return RedirectResponse(f"{console}?{urlencode({'sso': 'failed'})}", status_code=303)

        # The provider's access token is verified the same way every other
        # Keycloak token is, against its JWKS, by the driver that already
        # maps realm roles onto Clarity's closed enum. Nothing here reads a
        # role out of an unverified claim.
        try:
            external: Principal = clarity.token_verifier.verify(tokens.access_token)
        except TokenInvalid:
            _log.warning("staff sso returned a token this API will not accept")
            return RedirectResponse(f"{console}?{urlencode({'sso': 'failed'})}", status_code=303)

        staff_roles = {role for role in external.roles if role.value != "customer"}
        if not staff_roles:
            # Authenticated, but carrying no role this system knows. Refused
            # rather than admitted with nothing: a session with no role is a
            # session that will fail confusingly on every screen.
            _log.warning("staff sso principal carried no known role")
            return RedirectResponse(f"{console}?{urlencode({'sso': 'no_role'})}", status_code=303)

        issued = clarity.tokens.for_staff(
            external.ref,
            roles=staff_roles,
            assurance=external.assurance,
        )
        trail.record(
            clarity,
            AuditEventType.STAFF_SESSION_STARTED,
            actor_ref=external.ref,
            actor_kind=ActorKind.STAFF,
            session_ref=trail.session_ref_for(issued.value),
            object_ref=external.ref,
            detail={
                "roles": sorted(role.value for role in staff_roles),
                "assurance": issued.principal.assurance.value,
                "method": "oidc",
                "stepped_up": pending.stepping_up is not None,
                "simulated": True,
            },
        )

        response = RedirectResponse(pending.return_to, status_code=303)
        _set_session_cookie(
            response,
            issued.value,
            secure=clarity.settings.cookie_secure,
            # The cookie dies with the token it carries, so a browser is
            # never holding something the API has already stopped accepting.
            max_age=max(0, int((issued.expires_at - utc_now()).total_seconds())),
        )
        if tokens.id_token:
            response.set_cookie(
                ID_TOKEN_COOKIE,
                tokens.id_token,
                httponly=True,
                secure=clarity.settings.cookie_secure,
                samesite="lax",
                path="/",
            )
        return response

    @app.post("/v1/auth/staff/step-up", tags=["auth"])
    def step_up(
        clarity: ClarityDep,
        principal: StaffPrincipal,
        return_to: str = "/",
    ) -> dict[str, Any]:
        """Ask the provider to re-authenticate this person at a higher level.

        Returns the URL rather than redirecting, because the caller is the
        console's own fetch and a 303 on an XHR is not a thing a browser
        follows usefully. The console sends the person there.

        `prompt=login` and `max_age=0` are what make this a re-authentication.
        Without them the provider answers from the session cookie it already
        has, the token comes back claiming MFA, and the approval rests on the
        password typed an hour ago.
        """
        oidc = _enabled(clarity)
        target = _safe_return_to(return_to, clarity.settings.console_base_url)
        url, _pending = oidc.start(return_to=target, loa=LOA_MFA, stepping_up=principal.ref)
        trail.record(
            clarity,
            AuditEventType.STAFF_STEP_UP_REQUESTED,
            actor_ref=principal.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=principal.ref,
            detail={"level": LOA_MFA},
        )
        return {"redirect_to": url, "level": LOA_MFA}

    @app.get("/v1/auth/sessions", tags=["auth"])
    def list_sessions(
        request: Request,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> dict[str, Any]:
        """Every live session this person holds (B3).

        Signed in callers only, and it shows **their own** sessions: the
        subject comes from the verified token, never from a parameter, so there
        is no id to tamper with and nothing to enumerate.

        What it deliberately does not show: the token, or anything that could
        be used to resume a session. A list that can be read over somebody's
        shoulder should not also be a way in. Channel and timings are enough to
        recognise a device you do not know.
        """
        if principal is ANONYMOUS or not principal.roles:
            raise HTTPException(status_code=401, detail="a session is required")

        current = _session_id(clarity, request)
        return {
            "sessions": [
                {
                    "session_ref": trail.session_ref_for(record.jti),
                    "channel": record.principal.channel,
                    "assurance": record.principal.assurance.value,
                    "started_at": record.started().isoformat(),
                    "expires_at": record.expires_at.isoformat(),
                    "refresh_expires_at": record.refresh_expires_at.isoformat(),
                    "current": record.jti == current,
                }
                for record in clarity.tokens.sessions_for(principal.ref)
            ]
        }

    @app.delete("/v1/auth/sessions", tags=["auth"])
    def end_other_sessions(
        request: Request,
        clarity: ClarityDep,
        principal: Annotated[Principal, Depends(current_principal)],
        keep_current: bool = True,
    ) -> dict[str, Any]:
        """Sign out everywhere (B3).

        `keep_current` defaults to true, so somebody who has just found a
        session they do not recognise does not also sign themselves out of the
        device they are holding while they deal with it.
        """
        if principal is ANONYMOUS or not principal.roles:
            raise HTTPException(status_code=401, detail="a session is required")

        current = _session_id(clarity, request) if keep_current else None
        ended = clarity.tokens.revoke_all(principal.ref, keep=current)
        trail.record(
            clarity,
            AuditEventType.STAFF_SESSION_ENDED,
            actor_ref=principal.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=principal.ref,
            detail={"method": "sign_out_everywhere", "ended": ended, "kept_current": keep_current},
        )
        return {"ended": ended, "kept_current": keep_current}

    @app.post("/v1/auth/logout", tags=["auth"])
    def logout(
        clarity: ClarityDep,
        response: Response,
        session: Annotated[str | None, Cookie(alias=STAFF_COOKIE)] = None,
        id_token: Annotated[str | None, Cookie(alias=ID_TOKEN_COOKIE)] = None,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """End the session here, and at the provider.

        Revoking locally and leaving the provider's cookie alone is not a
        sign-out: the next visit returns instantly with no credentials asked
        for, which on a shared desk is the whole problem.

        Idempotent on purpose. Signing out twice, or signing out with no
        session, is not an error worth reporting to someone who is leaving.
        """
        token = session
        if token is None and authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()

        if token:
            try:
                principal = clarity.tokens.verify(token)
                clarity.tokens.revoke(token)
                trail.record(
                    clarity,
                    AuditEventType.STAFF_SESSION_ENDED,
                    actor_ref=principal.ref,
                    actor_kind=ActorKind.STAFF,
                    session_ref=trail.session_ref_for(token),
                    object_ref=principal.ref,
                    detail={"method": "logout"},
                )
            except TokenInvalid:
                # Already gone. Still clear the cookie.
                pass

        response.delete_cookie(STAFF_COOKIE, path="/")
        response.delete_cookie(ID_TOKEN_COOKIE, path="/")

        provider_logout: str | None = None
        if clarity.oidc is not None:
            provider_logout = clarity.oidc.end_session_url(
                id_token=id_token,
                redirect_to=clarity.settings.console_base_url,
            )
        return {"signed_out": True, "provider_logout": provider_logout}


__all__ = ["ID_TOKEN_COOKIE", "STAFF_COOKIE", "register"]
