"""The 24-hour customer service window (N02, #40; plan 09 section 9.7).

WhatsApp lets a business reply freely only inside 24 hours of the customer's
last message. Outside it, the only thing that may be sent is an approved
template. That is a provider rule, and it happens to be the same rule Clarity
already imposes on itself: I15 allows no free text to a customer except through
an approved template, and I1 keeps a model out of composing one.

So the window is not a limitation to work around. It is the provider agreeing
with an invariant, and the honest implementation makes outside-the-window the
*stricter* path rather than finding a way to keep talking.

**A refused send is reported, never silently substituted.** The tempting
shortcut is to swap a composed reply for a template when the window has
closed. That sends the customer something other than what the system decided,
with nothing saying so: the audit shows a reply that was never delivered and
the customer gets wording nobody chose for their case. So `allows` returns a
verdict, the caller decides, and the substitution is explicit.

**The window opens on the customer's message, not on ours.** Sending does not
extend it. Getting that backwards would let a business keep its own window open
indefinitely by messaging, which is exactly what the rule exists to stop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from clarity.kernel.common import utc_now

#: The provider's rule. 24 hours from the customer's last inbound message.
#:
#: **REQUIRES HUTCH CONFIRMATION** against the account's real terms: the Cloud
#: API uses 24 hours for the customer service window, and a given provider or
#: tier can differ. It is a constant here rather than in the policy store
#: because it is a provider's rule, not HUTCH's: it is not ours to tune, and a
#: deployment that could tune it would be configuring its way out of
#: compliance.
SERVICE_WINDOW = timedelta(hours=24)


class SendKind(StrEnum):
    """What a channel is allowed to send right now."""

    FREE_FORM = "free_form"
    """Inside the window. The composed reply may go as it is."""

    TEMPLATE_ONLY = "template_only"
    """Outside the window, or never opened. Only an approved template."""


@dataclass(frozen=True)
class WindowState:
    """Whether this conversation is inside its service window."""

    kind: SendKind
    opened_at: datetime | None
    expires_at: datetime | None
    remaining: timedelta | None

    @property
    def free_form(self) -> bool:
        return self.kind is SendKind.FREE_FORM

    def to_dict(self) -> dict[str, object]:
        return {
            "send": self.kind.value,
            "window_opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "window_expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "window_remaining_seconds": (
                int(self.remaining.total_seconds()) if self.remaining else None
            ),
            # Said plainly, because a caller that reads only this needs to know
            # the reply it composed may not be sendable.
            "free_form_allowed": self.free_form,
        }


class ServiceWindows:
    """Tracks when each conversation's window last opened.

    Keyed by `(channel, thread)` rather than by subscriber: the same customer
    on WhatsApp and on SMS has two windows, because the rule belongs to the
    provider's conversation and not to the person.

    In process memory, which is the honest limit of this implementation: two
    replicas would disagree about whether a window is open, and the safe
    direction of that disagreement is the strict one, since a replica that has
    not seen the inbound message says `TEMPLATE_ONLY`. Recorded in `MODULE.md`.
    """

    def __init__(
        self,
        *,
        span: timedelta = SERVICE_WINDOW,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._span = span
        self._clock = clock
        self._opened: dict[tuple[str, str], datetime] = {}

    def opened(self, channel: str, thread: str, *, at: datetime | None = None) -> None:
        """Record a customer message arriving, which opens or renews the window.

        Only inbound messages reach this. Nothing the business sends does.
        """
        self._opened[(channel, thread)] = at or self._clock()

    def state(self, channel: str, thread: str, *, now: datetime | None = None) -> WindowState:
        """What may be sent on this conversation right now."""
        moment = now or self._clock()
        opened_at = self._opened.get((channel, thread))
        if opened_at is None:
            # Never heard from. A business-initiated conversation is template
            # only by definition, which is the rule's whole point.
            return WindowState(
                kind=SendKind.TEMPLATE_ONLY,
                opened_at=None,
                expires_at=None,
                remaining=None,
            )
        expires_at = opened_at + self._span
        remaining = expires_at - moment
        if remaining <= timedelta(0):
            return WindowState(
                kind=SendKind.TEMPLATE_ONLY,
                opened_at=opened_at,
                expires_at=expires_at,
                remaining=timedelta(0),
            )
        return WindowState(
            kind=SendKind.FREE_FORM,
            opened_at=opened_at,
            expires_at=expires_at,
            remaining=remaining,
        )

    def allows_free_form(self, channel: str, thread: str, *, now: datetime | None = None) -> bool:
        return self.state(channel, thread, now=now).free_form


__all__ = ["SERVICE_WINDOW", "SendKind", "ServiceWindows", "WindowState"]
