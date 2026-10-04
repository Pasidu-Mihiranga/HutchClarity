"""The names of the cookies this API sets (B1, B4).

Their own module because two places need them and neither should import the
other: `auth.py` reads the staff session on every request, and `staff_sso.py`
is what sets it. A string written twice is a string that gets changed once.
"""

from __future__ import annotations

#: The staff session. Carries the same Clarity staff token `TokenIssuer` has
#: always minted, so revocation, the audit trail and the step-up window all
#: work unchanged; what differs is that the browser cannot read it.
#:
#: Named distinctly from any customer session: the two have different
#: lifetimes and different revocation paths, and a shared name is how one ends
#: up clearing the other.
STAFF_COOKIE = "clarity_staff_session"

#: The provider's id token, kept so a sign-out can tell the provider who is
#: leaving. Without an `id_token_hint` an RP-initiated logout may be refused or
#: may prompt, and a sign-out that needs a confirmation click is one people
#: skip. It is never read as proof of anything.
ID_TOKEN_COOKIE = "clarity_staff_idt"

#: The customer session, for the same reason as the staff one: a token in
#: `sessionStorage` is readable by any script on the page, and this one can
#: open a dispute and confirm a refund.
CUSTOMER_COOKIE = "clarity_customer_session"

#: The CSRF token. Deliberately **not** `HttpOnly`: the page has to read it to
#: echo it back in a header, which is the whole mechanism. It is not a
#: credential on its own and proves nothing by itself; what it proves is that
#: the request came from a page that could read this origin's cookies, which a
#: cross-site form cannot.
#:
#: `SameSite=Lax` already stops a cross-site POST carrying the session cookie,
#: so this is the second line. It covers what Lax does not: a sibling
#: subdomain an attacker controls is same-site, and a browser that does not
#: implement Lax defaults sends the cookie anyway.
CSRF_COOKIE = "clarity_csrf"

#: The header the page echoes it in.
CSRF_HEADER = "X-CSRF-Token"

__all__ = [
    "CSRF_COOKIE",
    "CSRF_HEADER",
    "CUSTOMER_COOKIE",
    "ID_TOKEN_COOKIE",
    "STAFF_COOKIE",
]
