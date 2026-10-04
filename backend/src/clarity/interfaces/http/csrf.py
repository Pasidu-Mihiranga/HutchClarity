"""Cross-site request forgery protection for cookie-borne sessions (B4).

**Why there is anything here at all.** The session cookies are `SameSite=Lax`,
which already stops a cross-site form POSTing with them, and CORS is pinned to
the deployment's own origins. That covers the ordinary case. It does not cover
two others: a sibling subdomain an attacker controls is *same-site* as far as
Lax is concerned, and a browser that does not apply the Lax default sends the
cookie on a cross-site POST as it always did. On a surface that approves
refunds, "the ordinary case" is not the bar.

**The mechanism.** Double submit. A random value is set in a cookie the page
can read, and the page echoes it in a header. A cross-site attacker can cause
the browser to *send* cookies but cannot *read* them, so they cannot produce
the header. The value is not a credential and proves nothing on its own; what
it proves is that the request came from a page able to read this origin's
cookies.

**What it deliberately does not apply to.** A request carrying a bearer token
is not forgeable this way: another site cannot make a browser attach a header
it does not know. So the check runs only when the request is relying on a
cookie, which keeps the MCP server, the channel gateway and every test driving
the API with a header out of it.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from clarity.interfaces.http.cookies import (
    CSRF_COOKIE,
    CSRF_HEADER,
    CUSTOMER_COOKIE,
    STAFF_COOKIE,
)
from clarity.interfaces.http.trail import NOT_RECORDED_AS_REQUESTS

#: Methods that change something. A GET does not, on any route here, which is
#: what lets `SameSite=Lax` be the first line at all.
UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Routes that complete a sign-in. They set the session cookie, so by
#: definition the caller does not have one yet and cannot echo a token for it.
#: Their protection is the single-use state and the one-time code, not this.
SIGN_IN = (
    "/v1/auth/otp/request",
    "/v1/auth/otp/verify",
    "/v1/auth/staff/login",
    "/v1/auth/staff/session",
    "/v1/auth/staff/oidc/",
    "/v1/auth/refresh",
)


def _read_only_posts() -> tuple[re.Pattern[str], ...]:
    """POSTs that change nothing, taken from the trail's own declarations.

    A handful of routes are POSTs because they are an action a person takes,
    not because they write: verifying a receipt, classifying a question,
    fetching suggestions. `NOT_RECORDED_AS_REQUESTS` already names them and
    says why, so this reads that rather than keeping a second list that can
    disagree with it.

    They are exempt because CSRF protects what a *session* can do, and these do
    nothing a session is needed for: an attacker who wants a receipt verified
    can verify it themselves.
    """
    patterns = []
    for route, reason in NOT_RECORDED_AS_REQUESTS.items():
        method, _, path = route.partition(" ")
        if method != "POST" or not reason.startswith("read only"):
            continue
        patterns.append(re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", path) + "$"))
    return tuple(patterns)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def issue(response: Response, *, secure: bool) -> str:
    """Attach a fresh CSRF cookie. Readable by the page, by design."""
    token = new_token()
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )
    return token


def enforce() -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Middleware refusing an unsafe cookie-borne request with no matching header."""
    read_only = _read_only_posts()

    async def middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in UNSAFE:
            return await call_next(request)
        if any(request.url.path.startswith(path) for path in SIGN_IN):
            return await call_next(request)
        if any(pattern.match(request.url.path) for pattern in read_only):
            return await call_next(request)
        # A bearer token cannot be forged across sites: another origin cannot
        # make the browser send a header it does not know.
        if request.headers.get("authorization", "").lower().startswith("bearer "):
            return await call_next(request)

        carries_session = bool(
            request.cookies.get(STAFF_COOKIE) or request.cookies.get(CUSTOMER_COOKIE)
        )
        if not carries_session:
            return await call_next(request)

        sent = request.headers.get(CSRF_HEADER, "")
        expected = request.cookies.get(CSRF_COOKIE, "")
        if not sent or not expected or not secrets.compare_digest(sent, expected):
            return JSONResponse(
                status_code=403,
                content={
                    "type": "about:blank",
                    "title": "Forbidden",
                    "status": 403,
                    "detail": "This request could not be verified. Please reload and try again.",
                    "code": "CSRF_FAILED",
                },
                media_type="application/problem+json",
            )
        return await call_next(request)

    return middleware


__all__ = ["SIGN_IN", "UNSAFE", "enforce", "issue", "new_token"]
