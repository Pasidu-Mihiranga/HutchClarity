"""Tracing: one trace per request, across modules and across events (B08).

The question this has to answer is "why did this customer get this receipt".
Answering it means following one request from the HTTP route, through the case
orchestration and the tool layer, over the event that the outbox published, and
into the consumer that issued the receipt. Timestamps in four log files cannot
do that; a trace can.

The exporter is a profile choice (ADR-0027): console in ``demo`` so a reviewer
sees spans with no collector running, OTLP in ``full``. Business code calls
``span()`` and never knows which.

**Spans carry identifiers, never personal data** (I13). The same rule as events:
a case id, a plan id, a ``subscriber_ref``, an amount as a string. A span
attribute ends up in a tracing backend that is not covered by the AI gateway's
masking, so it is kept to things that are already pseudonyms.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, Tracer

#: One name for everything Clarity emits, so a backend groups it as one service.
SERVICE_NAME = "clarity"

_CONFIGURED = False


def configure_tracing(
    *,
    exporter: str = "console",
    endpoint: str | None = None,
    service_name: str = SERVICE_NAME,
) -> None:
    """Install the tracer provider for this process. Called by the container.

    ``exporter`` is ``console``, ``otlp`` or ``none``. Idempotent: calling it
    again is a no-op, because replacing a provider mid-process would orphan the
    spans already started under the old one.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    if exporter == "none":
        # A decision, not an absence of one: mark it done so a later caller
        # does not install an exporter over the top of it.
        _CONFIGURED = True
        return

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))

    if exporter == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        # Simple, not batched: a reviewer running the demo should see a span
        # when it happens rather than when a batch flushes.
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif exporter == "otlp":
        if not endpoint:
            raise ValueError("the otlp exporter needs an endpoint")
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    else:
        raise ValueError(f"unknown exporter {exporter!r}: use console, otlp or none")

    trace.set_tracer_provider(provider)
    _CONFIGURED = True


def tracer(name: str = SERVICE_NAME) -> Tracer:
    return trace.get_tracer(name)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    """One span, with its attributes.

    Attributes are identifiers and amounts only; see the module docstring.
    ``None`` values are dropped rather than recorded as "None", so an optional
    id simply does not appear.
    """
    with tracer().start_as_current_span(name) as started:
        for key, value in attributes.items():
            if value is not None:
                started.set_attribute(key, _as_attribute(value))
        yield started


def _as_attribute(value: Any) -> Any:
    """OpenTelemetry takes scalars; anything else goes as its string form."""
    if isinstance(value, bool | int | float | str):
        return value
    return str(value)


def current_trace_id() -> str | None:
    """The current trace as the 32 hex characters a backend shows, if tracing."""
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


def current_span_id() -> str | None:
    context = trace.get_current_span().get_span_context()
    return format(context.span_id, "016x") if context.is_valid else None


def link_to_event(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Trace identifiers to carry on an event, so a consumer joins the trace.

    The envelope's ``correlation_id`` already ties a request's events together.
    This adds the trace and span ids, which is what lets a tracing backend show
    the consumer's work as part of the request that caused it rather than as an
    unrelated trace.
    """
    carried = dict(attributes)
    if trace_id := current_trace_id():
        carried["trace_id"] = trace_id
    if span_id := current_span_id():
        carried["parent_span_id"] = span_id
    return carried


__all__ = [
    "SERVICE_NAME",
    "configure_tracing",
    "current_span_id",
    "current_trace_id",
    "link_to_event",
    "span",
    "tracer",
]
