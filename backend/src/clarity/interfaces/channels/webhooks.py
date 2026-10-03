"""Verifying an inbound channel webhook (N02, #40; plan 09 section 9.7).

A webhook endpoint is the one door into Clarity that anybody on the internet
can knock on. Everything else needs a session, a token or a staff role; this
takes a POST from a provider and starts a conversation with a customer. So the
whole of this module is about refusing.

Six rules, and the first is the one that matters most.

**1. No secret configured means reject everything.** A gateway that accepts
unsigned webhooks because nobody set a secret is worse than one that is down:
it looks like it works. I9 is deny by default and this is the sharpest case of
it, so an unconfigured verifier refuses every request and says why.

**2. The signature is computed over the raw body bytes.** Not over a parsed and
re-serialised payload: `json.dumps(json.loads(body))` changes whitespace and
key order, so the digest stops matching and the natural fix is to stop
checking. The verifier therefore runs before parsing and takes `bytes`.

**3. Comparison is constant time.** `==` on a digest leaks how many leading
bytes were right, which is enough to forge one byte at a time.
`hmac.compare_digest` does not.

**4. The timestamp is inside the signed payload.** Signing the body alone lets
an attacker replay yesterday's valid request forever, and lets them change the
timestamp header freely because nothing covers it. The signed string is
`timestamp.body`, so neither can move without breaking the digest.

**5. A stale timestamp is rejected even when the signature is good.** A valid
signature on an old payload is still a valid signature; freshness is the only
thing that makes a replay detectable.

**6. A delivery id is accepted once.** A replay inside the freshness window has
a good signature and a good timestamp, so only remembering the id catches it.

**ASSUMPTION** on the scheme: `sha256=<hex>` over `timestamp.body`, which is the
shape Stripe, Slack and the WhatsApp Cloud API all use with small differences.
**REQUIRES HUTCH CONFIRMATION** of the real provider's exact scheme before this
faces a real webhook; the shape of the check does not change, only how the
header is named and parsed.
"""

from __future__ import annotations

import hashlib
import hmac
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from clarity.kernel.common import utc_now

#: How old a signed request may be. Five minutes is enough for a provider
#: retry and short enough that a captured request is useless by the time it is
#: replayed by hand.
DEFAULT_FRESHNESS = timedelta(minutes=5)

#: How many delivery ids the replay guard remembers.
#:
#: Bounded, because an unbounded set is a memory leak on a public endpoint:
#: anybody can make it grow by sending ids. Oldest are dropped first, so a
#: replay after this many deliveries would pass. That is the honest limit of an
#: in-process guard, and the note in `MODULE.md` says what replaces it.
DEFAULT_REPLAY_MEMORY = 4096

#: The prefix the signature header carries, naming the algorithm.
#:
#: Named in the header rather than assumed, so upgrading the digest later does
#: not need every sender changed at once, and so a sender using something else
#: is refused rather than silently compared against SHA-256.
SCHEME = "sha256"


class Rejection(str):
    """A reason a webhook was refused. A string subclass so it logs plainly."""


#: Every reason the verifier can refuse. Stable, because they reach the audit.
NO_SECRET = Rejection("no_signing_secret_configured")
MISSING_SIGNATURE = Rejection("missing_signature")
MISSING_TIMESTAMP = Rejection("missing_timestamp")
UNKNOWN_SCHEME = Rejection("unknown_signature_scheme")
MALFORMED_SIGNATURE = Rejection("malformed_signature")
BAD_SIGNATURE = Rejection("bad_signature")
STALE_TIMESTAMP = Rejection("stale_timestamp")
FUTURE_TIMESTAMP = Rejection("timestamp_in_the_future")
REPLAYED = Rejection("delivery_already_seen")


@dataclass(frozen=True)
class Verdict:
    """Whether a webhook may be processed, and why not when it may not."""

    ok: bool
    reason: Rejection | None = None

    def __bool__(self) -> bool:
        return self.ok


ACCEPTED = Verdict(ok=True)


def sign(secret: str, *, body: bytes, timestamp: str) -> str:
    """The signature a sender would compute. Used by the simulator and tests.

    Exported rather than reimplemented in the tests, because a test that
    computes the digest its own way is testing its own arithmetic: if this
    function is wrong, both agree and the suite stays green.
    """
    payload = timestamp.encode("utf-8") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{SCHEME}={digest}"


class WebhookVerifier:
    """Checks a webhook's signature, freshness and uniqueness."""

    def __init__(
        self,
        secret: str | None,
        *,
        freshness: timedelta = DEFAULT_FRESHNESS,
        clock: Callable[[], datetime] = utc_now,
        replay_memory: int = DEFAULT_REPLAY_MEMORY,
    ) -> None:
        self._secret = secret or None
        self._freshness = freshness
        self._clock = clock
        self._capacity = max(1, replay_memory)
        # Ordered so the oldest id is the one dropped when it fills.
        self._seen: OrderedDict[str, None] = OrderedDict()

    @property
    def configured(self) -> bool:
        """Whether a secret exists. False means every webhook is refused."""
        return self._secret is not None

    def verify(
        self,
        *,
        body: bytes,
        signature: str | None,
        timestamp: str | None,
        delivery_id: str | None = None,
    ) -> Verdict:
        """Accept or refuse one webhook.

        The order of the checks is deliberate. The signature is checked before
        the timestamp is trusted for anything, because an unsigned timestamp is
        an attacker's input; and the delivery id is only remembered once the
        request has otherwise passed, so an attacker cannot fill the replay
        memory with ids of their choosing by sending garbage.
        """
        if self._secret is None:
            return Verdict(ok=False, reason=NO_SECRET)
        if not signature:
            return Verdict(ok=False, reason=MISSING_SIGNATURE)
        if not timestamp:
            return Verdict(ok=False, reason=MISSING_TIMESTAMP)

        scheme, _, provided = signature.partition("=")
        if scheme != SCHEME:
            return Verdict(ok=False, reason=UNKNOWN_SCHEME)
        if not provided or any(c not in "0123456789abcdefABCDEF" for c in provided):
            # Refused before `compare_digest`, which raises on non-ASCII and
            # would turn a malformed header into a 500 rather than a 401.
            return Verdict(ok=False, reason=MALFORMED_SIGNATURE)

        expected = sign(self._secret, body=body, timestamp=timestamp)
        if not hmac.compare_digest(expected, f"{SCHEME}={provided.lower()}"):
            return Verdict(ok=False, reason=BAD_SIGNATURE)

        fresh = self._freshness_of(timestamp)
        if fresh is not None:
            return Verdict(ok=False, reason=fresh)

        if delivery_id:
            if delivery_id in self._seen:
                return Verdict(ok=False, reason=REPLAYED)
            self._seen[delivery_id] = None
            while len(self._seen) > self._capacity:
                self._seen.popitem(last=False)

        return ACCEPTED

    def _freshness_of(self, timestamp: str) -> Rejection | None:
        """Whether the signed timestamp is inside the window."""
        try:
            sent = datetime.fromisoformat(timestamp)
        except ValueError:
            return STALE_TIMESTAMP
        if sent.tzinfo is None:
            # A naive timestamp cannot be compared without guessing a zone, and
            # guessing would make the window wrong by hours.
            return STALE_TIMESTAMP
        now = self._clock()
        if sent - now > self._freshness:
            # Clock skew allows a little, but a far-future timestamp is how a
            # captured request is made to stay valid indefinitely.
            return FUTURE_TIMESTAMP
        if now - sent > self._freshness:
            return STALE_TIMESTAMP
        return None


__all__ = [
    "ACCEPTED",
    "BAD_SIGNATURE",
    "DEFAULT_FRESHNESS",
    "DEFAULT_REPLAY_MEMORY",
    "FUTURE_TIMESTAMP",
    "MALFORMED_SIGNATURE",
    "MISSING_SIGNATURE",
    "MISSING_TIMESTAMP",
    "NO_SECRET",
    "REPLAYED",
    "SCHEME",
    "STALE_TIMESTAMP",
    "UNKNOWN_SCHEME",
    "Rejection",
    "Verdict",
    "WebhookVerifier",
    "sign",
]
