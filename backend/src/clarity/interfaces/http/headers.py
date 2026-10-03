"""Security response headers (X01, issue #42).

Found by the OWASP ZAP baseline, which reported six missing-header rules
against every page and asset this app serves. None of them is exploitable on
its own; together they are the difference between a browser that enforces the
app's intentions and one that guesses.

Each header below says what it stops. The values are deliberately strict
because this app serves exactly two kinds of response: JSON from `/v1`, and the
small static UI that FE01 is retiring. Neither embeds anything, neither is
meant to be framed, and neither needs a camera.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

#: Applied to every response.
#:
#: `frame-ancestors 'none'` and `X-Frame-Options: DENY` both stop clickjacking,
#: the second for browsers that predate CSP level 2. A receipt or a confirm
#: button inside someone else's iframe is the attack that matters here: the
#: customer thinks they are tapping one thing and taps another.
SECURITY_HEADERS: dict[str, str] = {
    # Stops a browser from re-interpreting a JSON response as HTML or script,
    # which is how a reflected value becomes stored XSS.
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    ),
    # No feature this app serves needs any of these, and a compromised script
    # that cannot reach them is a smaller problem.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    # Isolates this origin from cross-origin documents and popups, so a page
    # opened from here cannot reach back into it.
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cross-Origin-Resource-Policy": "same-origin",
    # A customer's case and receipt are not for a shared cache to keep. The
    # static UI overrides this; see `_CACHEABLE` below.
    "Referrer-Policy": "no-referrer",
}

#: Paths whose responses are public, identical for everyone, and worth caching.
#: Everything else carries the no-store default, because a case, a decision or
#: a receipt is one customer's and must not sit in an intermediary.
_CACHEABLE = ("/static/", "/docs", "/redoc", "/openapi.json")


def _is_cacheable(path: str) -> bool:
    return path.startswith(_CACHEABLE)


async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add the headers above, without overwriting one a route set deliberately."""
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    response.headers.setdefault(
        "Cache-Control",
        "public, max-age=300" if _is_cacheable(request.url.path) else "no-store",
    )
    return response


__all__ = ["SECURITY_HEADERS", "security_headers"]
