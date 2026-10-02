"""OpenTelemetry console exporter bootstrap."""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger("clarity.otel")


def setup_otel(*, exporter: str = "console", service_name: str = "clarity-api") -> None:
    """Best-effort OTel setup. Missing packages do not prevent startup."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        _log.info("opentelemetry not installed; tracing disabled")
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if exporter == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


def get_tracer(name: str = "clarity") -> Any:
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return _NoopTracer()


class _NoopSpan:
    def __enter__(self) -> _NoopSpan:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def set_attribute(self, *args: object, **kwargs: object) -> None:
        return None


class _NoopTracer:
    def start_as_current_span(self, name: str) -> _NoopSpan:
        _ = name
        return _NoopSpan()
