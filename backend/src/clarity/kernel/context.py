"""Correlation context propagated HTTP → event → consumer."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field

from clarity.kernel.ids import new_id

_CURRENT: ContextVar[CorrelationContext | None] = ContextVar("clarity_correlation", default=None)


@dataclass(slots=True)
class CorrelationContext:
    correlation_id: str = field(default_factory=lambda: new_id("COR"))
    causation_id: str | None = None
    traceparent: str | None = None

    @classmethod
    def current(cls) -> CorrelationContext:
        existing = _CURRENT.get()
        if existing is None:
            created = cls()
            _CURRENT.set(created)
            return created
        return existing

    @classmethod
    def bind(cls, ctx: CorrelationContext) -> None:
        _CURRENT.set(ctx)

    @classmethod
    def clear(cls) -> None:
        _CURRENT.set(None)
