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

__all__ = ["ID_TOKEN_COOKIE", "STAFF_COOKIE"]
