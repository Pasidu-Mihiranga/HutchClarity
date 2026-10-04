"""Request rate limiting (A8).

**What this is for, and what it is not.** Nothing in `backend/src` limited a
request rate before this. `OtpService` throttles challenges per number, which
is the TH1 SMS-pumping mitigation and nothing wider, and `ai/buckets.py` rations
provider *token spend* by priority, not caller requests. So the anonymous
assistant routes, which run masking, intake, retrieval and composition, could be
called in a loop by anyone with the URL.

It is a flood and abuse control, not a quota. nginx already caps 20 r/s per IP
in the deployed profile, which stops a crude flood at the edge but cannot see a
subscriber, cannot distinguish an expensive route from a cheap one, and is not
there at all in `lite`. This sits in the app where both are visible.

**A port with a driver, because the obvious implementation is wrong in `full`.**
A counter in a process is per replica, so two replicas give a caller twice the
budget, and a restart forgets everything. That is survivable for a flood control
and unacceptable for anything that pretends to be a quota, which is the other
reason this is not one. `MemoryRateLimiter` is the `lite` driver and the honest
default; a shared driver (Redis, or the unit of work) is the `full` one and must
pass the same parity suite (I20).

**Fixed window, not a token bucket.** A fixed window lets a caller spend two
windows' worth across a boundary, which for a flood control is a rounding error,
and it has one integer of state per key instead of a float and a timestamp. The
window is deliberately not a policy value: changing it changes what the limit
*means*, and a reviewer approving "30" should not have to look up what it is 30
of.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

#: One minute, everywhere. See the module docstring for why this is not policy.
WINDOW = timedelta(seconds=60)


@dataclass(frozen=True)
class Verdict:
    """Whether this call may proceed, and when to try again if not."""

    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int

    @property
    def headers(self) -> dict[str, str]:
        """RFC 9239-style hints. A limiter that does not say so is a mystery."""
        headers = {
            "RateLimit-Limit": str(self.limit),
            "RateLimit-Remaining": str(max(0, self.remaining)),
            "RateLimit-Reset": str(self.retry_after_seconds),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after_seconds)
        return headers


class RateLimiter(Protocol):
    """Counts calls against a key inside a fixed window."""

    def check(self, key: str, *, limit: int, now: datetime) -> Verdict:
        """Record one call and say whether it is allowed.

        Recording and deciding are one operation on purpose: a limiter where a
        caller can ask "may I?" without being counted is a limiter that can be
        walked past by never asking.
        """
        ...


class MemoryRateLimiter:
    """In-process fixed-window counter. The `lite` driver.

    Per replica and forgotten on restart, which the module docstring explains
    and which is why this is a flood control rather than a quota.
    """

    def __init__(self, *, window: timedelta = WINDOW) -> None:
        self._window = window
        self._lock = threading.Lock()
        #: key -> (window start, count seen in it)
        self._counts: dict[str, tuple[datetime, int]] = {}

    def check(self, key: str, *, limit: int, now: datetime) -> Verdict:
        if limit <= 0:
            raise ValueError("a rate limit must be positive; 0 would refuse everything")
        with self._lock:
            started, seen = self._counts.get(key, (now, 0))
            if now - started >= self._window:
                started, seen = now, 0
            seen += 1
            self._counts[key] = (started, seen)

            # Opportunistic sweep, so a long-lived process does not accumulate
            # a key per address it has ever seen. Cheap because it only runs
            # when the table is already large.
            if len(self._counts) > 10_000:
                self._counts = {
                    existing: value
                    for existing, value in self._counts.items()
                    if now - value[0] < self._window
                }

        elapsed = now - started
        resets_in = max(1, int((self._window - elapsed).total_seconds()))
        return Verdict(
            allowed=seen <= limit,
            limit=limit,
            remaining=limit - seen,
            retry_after_seconds=resets_in,
        )


__all__ = ["WINDOW", "MemoryRateLimiter", "RateLimiter", "Verdict"]
