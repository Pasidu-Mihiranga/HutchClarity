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

from collections.abc import Awaitable, Callable
from datetime import datetime

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from clarity.platform.throttle import RateLimiter

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


def rate_limit(
    limiter: RateLimiter,
    resolve: Callable[[str, datetime], int],
    clock: Callable[[], datetime],
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Build the middleware. The container supplies the driver and the clock."""

    async def middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        matched = _route_for(request.url.path)
        if matched is None or request.method == "OPTIONS":
            return await call_next(request)

        prefix, policy_key = matched
        now = clock()
        key, signed_in = _caller(request)

        checks = [(f"{key}|{prefix}", resolve(policy_key, now))]
        if not signed_in:
            # One budget across every throttled route, on top of the per-route
            # one. An anonymous caller is the case where this is the only thing
            # between a script and the pipeline.
            checks.append((f"{key}|anon", resolve(ANONYMOUS_KEY, now)))

        for check_key, limit in checks:
            verdict = limiter.check(check_key, limit=limit, now=now)
            if not verdict.allowed:
                return JSONResponse(
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

        response = await call_next(request)
        # Report the per-route budget, which is the one a client can act on.
        for header, value in verdict.headers.items():
            response.headers.setdefault(header, value)
        return response

    return middleware


__all__ = [
    "ANONYMOUS_FALLBACK",
    "ANONYMOUS_KEY",
    "FALLBACK_LIMIT",
    "THROTTLED",
    "rate_limit",
]
