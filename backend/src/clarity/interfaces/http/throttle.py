"""The rate-limit middleware (A8).

Which routes, and why those. Only the ones that are both **anonymous** and
**expensive**: a turn runs masking, intake, a flow step, retrieval and
composition, and anyone with the URL could run it in a loop. Everything else
either needs a session, which gives the caller an identity and an audit trail,
or is a cheap read already behind a permission.

The key is the subscriber when there is one, so a signed-in customer's budget
follows them across addresses and a shared NAT does not throttle a whole
building. Without a session it falls back to the client address, which is the
only thing left and is why the anonymous ceiling is lower.

Limits are resolved from the policy store (I10), not constants, and resolved
per request so an activated change takes effect without a restart. A policy
store that cannot answer is not a reason to refuse traffic: the limiter falls
back to its declared default and says so in a log line, because a limiter that
fails closed turns a configuration problem into an outage.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from clarity.platform.throttle import RateLimiter

_log = logging.getLogger("clarity.http.throttle")

#: Path prefix -> the policy key holding its per-minute limit.
#:
#: Prefix matched, so the streaming twin of a route is covered by the same
#: budget as the route itself. That is deliberate: otherwise a caller refused
#: on `/turn` would simply move to `/turn/stream`.
THROTTLED: tuple[tuple[str, str], ...] = (
    ("/v1/conversation/turn", "throttle.conversation.per_minute"),
    ("/v1/conversation/suggestions", "throttle.knowledge.per_minute"),
    ("/v1/knowledge/search", "throttle.knowledge.per_minute"),
    ("/v1/clarity/route", "throttle.conversation.per_minute"),
    # Sign-in (B6). The OTP service already bounds challenges per *number*,
    # which is the SMS-pumping control; this bounds them per *caller*, which
    # is what stops one script working through a list of numbers. nginx caps
    # /v1/auth at 10 a minute in the deployed profile, and nothing does in
    # `lite`, so the control existed only where the reverse proxy did.
    ("/v1/auth/otp/request", "throttle.auth.per_minute"),
    ("/v1/auth/otp/verify", "throttle.auth.per_minute"),
    ("/v1/auth/staff/login", "throttle.auth.per_minute"),
    ("/v1/auth/refresh", "throttle.auth.per_minute"),
)

#: Used when the policy store cannot answer. See the module docstring.
FALLBACK_LIMIT = 30

#: The whole-surface ceiling for a caller with no session.
ANONYMOUS_KEY = "throttle.anonymous.per_minute"
ANONYMOUS_FALLBACK = 45


def _route_for(path: str) -> tuple[str, str] | None:
    for prefix, policy_key in THROTTLED:
        if path == prefix or path.startswith(f"{prefix}/"):
            return prefix, policy_key
    return None


def _caller(request: Request) -> tuple[str, bool]:
    """Who to count against, and whether they are signed in.

    The subject comes from the **verified** token, never from a header the
    caller supplies directly: a limiter keyed on something the caller chooses
    is a limiter with an opt-out. The principal is resolved per route by
    `Depends`, which has not run yet in middleware, so the token is verified
    here too. That is the same work twice per throttled request, and it is the
    price of counting a signed-in customer as themselves rather than as their
    network address.

    A token that does not verify is not refused here. This is a limiter, not an
    authenticator: the route's own dependency will answer 401 a moment later,
    with the audit record that belongs to it. Treating it as anonymous in the
    meantime is both correct and the stricter choice.
    """
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        verifier = getattr(request.app.state, "token_verifier", None)
        if verifier is not None:
            try:
                principal = verifier.verify(authorization.split(" ", 1)[1].strip())
                subject = getattr(principal, "subscriber_ref", None) or getattr(
                    principal, "ref", ""
                )
                if subject and subject != "anonymous":
                    return f"sub:{subject}", True
            except Exception:
                pass

    client = request.client.host if request.client else "unknown"
    return f"ip:{client}", False


class RateLimitMiddleware:
    """Pure ASGI rate limiting, with request-local response headers.

    FastAPI's function-style HTTP middleware is implemented through
    ``BaseHTTPMiddleware``. Under the browser suite's concurrent CORS traffic,
    its response boundary leaked one request's rate-limit headers and refusal
    onto unrelated authentication requests. Keeping this wrapper at the ASGI
    message layer gives every invocation its own scope and send closure.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: RateLimiter,
        resolve: Callable[[str, datetime], int],
        clock: Callable[[], datetime],
    ) -> None:
        self.app = app
        self.limiter = limiter
        self.resolve = resolve
        self.clock = clock

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        # Classify from the immutable ASGI scope. `request.url` is a derived,
        # cached object; under the browser suite's concurrent CORS traffic it
        # was observed carrying a throttled request's classification into an
        # authentication response. That made unrelated login and OTP routes
        # spend the anonymous assistant budget.
        path = str(scope.get("path", ""))
        matched = _route_for(path)
        if matched is None or request.method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        prefix, policy_key = matched
        now = self.clock()
        key, signed_in = _caller(request)

        checks = [(f"{key}|{prefix}", self.resolve(policy_key, now))]
        if not signed_in:
            # One budget across every throttled route, on top of the per-route
            # one. An anonymous caller is the case where this is the only thing
            # between a script and the pipeline.
            checks.append((f"{key}|anon", self.resolve(ANONYMOUS_KEY, now)))

        for check_key, limit in checks:
            verdict = self.limiter.check(check_key, limit=limit, now=now)
            if not verdict.allowed:
                _log.warning(
                    "rate limit refused path=%s prefix=%s key=%s limit=%s remaining=%s",
                    path,
                    prefix,
                    check_key,
                    limit,
                    verdict.remaining,
                )
                response = JSONResponse(
                    status_code=429,
                    content={
                        "type": "about:blank",
                        "title": "Too many requests",
                        "status": 429,
                        "detail": "Too many requests. Please wait a moment and try again.",
                        "code": "RATE_LIMITED",
                    },
                    media_type="application/problem+json",
                    headers=verdict.headers,
                )
                await response(scope, receive, send)
                return

        async def send_with_budget(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                for header, value in verdict.headers.items():
                    encoded = header.lower().encode("latin-1")
                    if encoded not in existing:
                        headers.append((encoded, value.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_budget)


__all__ = [
    "ANONYMOUS_FALLBACK",
    "ANONYMOUS_KEY",
    "FALLBACK_LIMIT",
    "THROTTLED",
    "RateLimitMiddleware",
]
