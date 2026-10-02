"""Token buckets per provider, with priority (A01, plan 19 section 4.3).

The prototype runs on free tiers, which means a hard ceiling that is shared by
everything in the system. Without an allocation the first batch job of the day
can spend the whole quota and a customer asking "why was I charged" gets
nothing, which is the one request that must never be the one that fails.

So spending is bounded per provider and ordered by who is waiting:

**customer live** keeps a reserved share nothing else may touch. A person is
waiting for this answer.

**staff** spends from the shared pool. An agent can see the evidence and the
decision without a model; the model only phrases it.

**batch** spends only what is left after the reserve. Autopsy and evaluation are
useful and can wait for tomorrow's quota.

Refusing is not a failure here. Every customer-facing role has a template or
rule at the end of its chain, so a refused model call becomes a deterministic
answer rather than an error (ADR-0009).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum

from clarity.kernel.common import utc_now


class Priority(IntEnum):
    """Who is waiting. Lower is more important, so it sorts naturally."""

    CUSTOMER_LIVE = 0
    STAFF = 1
    BATCH = 2

    @property
    def label(self) -> str:
        return self.name.lower().replace("_", " ")


class QuotaExhausted(RuntimeError):
    """This provider has no allowance left for this priority.

    A condition, not a fault: the caller falls back down the chain, and the
    chain ends somewhere that needs no quota.
    """

    def __init__(self, provider: str, priority: Priority) -> None:
        super().__init__(
            f"{provider} has no allowance left for {priority.label} work; "
            "fall back to the next provider in the role's chain"
        )
        self.provider = provider
        self.priority = priority


@dataclass
class ProviderQuota:
    """One provider's ceiling, and how much of it customers keep."""

    provider: str
    tokens_per_window: int
    window: timedelta = timedelta(minutes=1)
    customer_reserve: float = 0.3
    """Share of the window only ``CUSTOMER_LIVE`` may spend."""

    def __post_init__(self) -> None:
        if not 0.0 <= self.customer_reserve < 1.0:
            raise ValueError("customer_reserve is a share of the window, so 0 <= r < 1")

    @property
    def reserved_tokens(self) -> int:
        return int(self.tokens_per_window * self.customer_reserve)

    def ceiling_for(self, priority: Priority) -> int:
        """How much of the window this priority may reach.

        Customers may spend all of it. Everything else stops at the reserve, so
        there is always something left for the person who is waiting.
        """
        if priority is Priority.CUSTOMER_LIVE:
            return self.tokens_per_window
        return self.tokens_per_window - self.reserved_tokens


@dataclass
class _Window:
    started_at: datetime
    spent: int = 0


@dataclass
class TokenBuckets:
    """Tracks spending per provider inside a rolling window."""

    quotas: dict[str, ProviderQuota] = field(default_factory=dict)
    now: Callable[[], datetime] = utc_now
    _windows: dict[str, _Window] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def add(self, quota: ProviderQuota) -> None:
        self.quotas[quota.provider] = quota

    def claim(self, provider: str, *, tokens: int, priority: Priority) -> None:
        """Reserve ``tokens`` for this provider, or raise ``QuotaExhausted``.

        An unmetered provider (a local template, or one with no declared quota)
        always succeeds: there is no ceiling to run into.
        """
        quota = self.quotas.get(provider)
        if quota is None:
            return

        with self._lock:
            window = self._current(provider, quota)
            if window.spent + tokens > quota.ceiling_for(priority):
                raise QuotaExhausted(provider, priority)
            window.spent += tokens

    def record(self, provider: str, *, tokens: int) -> None:
        """Account for tokens actually spent, when the real cost is known.

        A claim is an estimate made before the call; this corrects it with what
        the provider reported, so the window reflects real spending.
        """
        if provider not in self.quotas:
            return
        with self._lock:
            window = self._current(provider, self.quotas[provider])
            window.spent = max(0, window.spent + tokens)

    def remaining(self, provider: str, *, priority: Priority = Priority.CUSTOMER_LIVE) -> int:
        quota = self.quotas.get(provider)
        if quota is None:
            return 0
        with self._lock:
            window = self._current(provider, quota)
            return max(0, quota.ceiling_for(priority) - window.spent)

    def _current(self, provider: str, quota: ProviderQuota) -> _Window:
        """The live window, started fresh if the previous one has elapsed."""
        moment = self.now()
        window = self._windows.get(provider)
        if window is None or moment - window.started_at >= quota.window:
            window = _Window(started_at=moment)
            self._windows[provider] = window
        return window


__all__ = [
    "Priority",
    "ProviderQuota",
    "QuotaExhausted",
    "TokenBuckets",
]
