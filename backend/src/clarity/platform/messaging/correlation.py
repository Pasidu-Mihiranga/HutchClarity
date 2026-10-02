"""The correlation ID, carried from a request to an event to a consumer (B04).

One request produces a state change, the state change produces events, and
those events produce more work in other consumers. Without a single id running
through all of it, "why did this customer get this receipt" is answered by
reading timestamps and guessing.

The id travels explicitly on the envelope (``Event.correlation_id``), which is
what crosses a process boundary. This module is the in-process half: it makes
the current id available to code that did not receive the event as an argument,
such as a log formatter or a span exporter. Nothing reads it to make a decision.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_CURRENT: ContextVar[str | None] = ContextVar("clarity_correlation_id", default=None)


def current_correlation_id() -> str | None:
    """The id of the request or event being handled, if there is one."""
    return _CURRENT.get()


@contextmanager
def correlated(correlation_id: str | None) -> Iterator[None]:
    """Run a block under one correlation id, restoring the previous one after.

    A context manager rather than a setter, because a consumer handling two
    events in a row must not leak the first one's id into the second.
    """
    token = _CURRENT.set(correlation_id)
    try:
        yield
    finally:
        _CURRENT.reset(token)


__all__ = ["correlated", "current_correlation_id"]
