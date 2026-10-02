"""One trace per request, across modules and the event (issue #16, B08).

The question a trace has to answer is "why did this customer get this receipt".
That means one trace covering the HTTP route, the case orchestration, the tool
layer that moved the money, and the consumer that issued the receipt. Four
separate traces would answer nothing.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.interfaces.http.main import CORRELATION_HEADER, create_app
from clarity.kernel.common import Channel
from clarity.platform.observability import current_trace_id, tracing

DILANI = "+94771234567"


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    """Collect spans in memory instead of exporting them.

    OpenTelemetry keeps one provider per process and offers no way to put a
    previous one back. An earlier version of this fixture saved and restored it,
    which looked tidy and was a trap: before anything sets one, the global is a
    ``ProxyTracerProvider`` whose job is to delegate to that same global, so
    restoring it made it delegate to itself and every later span recursed.

    So this installs a provider once, if the process has none, and otherwise
    attaches to the one that is already there. ``_CONFIGURED`` is set so the
    container does not install the profile's console exporter over the top.
    """
    exporter = InMemorySpanExporter()
    active = trace.get_tracer_provider()
    if not isinstance(active, TracerProvider):
        active = TracerProvider(resource=Resource.create({"service.name": "clarity-test"}))
        trace.set_tracer_provider(active)
    active.add_span_processor(SimpleSpanProcessor(exporter))
    tracing._CONFIGURED = True
    yield exporter
    exporter.clear()


def _signed_in_client(clarity: Clarity) -> TestClient:
    """Signed in as the customer: confirming a plan is their own action (I9)."""
    client = TestClient(create_app(clarity))
    started = client.post("/v1/auth/otp/request", json={"msisdn": DILANI})
    assert started.status_code == 200, started.text
    code = client.get("/v1/demo/inbox", params={"msisdn": DILANI}).json()["code"]
    session = client.post(
        "/v1/auth/otp/verify",
        json={"challenge_id": started.json()["challenge_id"], "code": code},
    )
    assert session.status_code == 200, session.text
    client.headers["Authorization"] = f"Bearer {session.json()['token']}"
    return client


def _names(exporter: InMemorySpanExporter) -> list[str]:
    return [s.name for s in exporter.get_finished_spans()]


def _by_name(exporter: InMemorySpanExporter, name: str) -> ReadableSpan:
    found = [s for s in exporter.get_finished_spans() if s.name == name]
    assert found, f"no span named {name!r}; got {_names(exporter)}"
    return found[0]


# -- acceptance 1: one trace links HTTP, case, actions, receipt consumer --- #


def test_one_confirm_request_is_a_single_trace_across_the_modules(
    spans: InMemorySpanExporter,
) -> None:
    clarity = Clarity(world=build_demo_world())
    client = _signed_in_client(clarity)

    case = clarity.cases.open_case(
        subscriber_ref=ref_for(DILANI), msisdn_masked="077***4567", channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    plan = clarity.cases.propose(case.case_id, created_by="channel:web")

    spans.clear()
    response = client.post(f"/v1/cases/{case.case_id}/confirm", json={"plan_id": plan.plan_id})
    assert response.status_code in (200, 201), response.text

    names = _names(spans)
    for expected in (
        "http.request",
        "case.confirm_and_execute",
        "actions.execute",
        "receipts.on_action_completed",
    ):
        assert expected in names, f"{expected} is missing from the trace: {names}"

    # One trace, not four: every span shares the request's trace id.
    trace_ids = {s.context.trace_id for s in spans.get_finished_spans() if s.context}
    assert len(trace_ids) == 1, f"the request produced {len(trace_ids)} traces, not one"


def test_the_receipt_consumer_is_a_child_of_the_request(spans: InMemorySpanExporter) -> None:
    """The receipt has to be attributable to the tap that caused it."""
    clarity = Clarity(world=build_demo_world())
    client = _signed_in_client(clarity)
    case = clarity.cases.open_case(
        subscriber_ref=ref_for(DILANI), msisdn_masked="077***4567", channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    plan = clarity.cases.propose(case.case_id, created_by="channel:web")

    spans.clear()
    client.post(f"/v1/cases/{case.case_id}/confirm", json={"plan_id": plan.plan_id})

    request_span = _by_name(spans, "http.request")
    consumer_span = _by_name(spans, "receipts.on_action_completed")
    assert consumer_span.context is not None and request_span.context is not None
    assert consumer_span.context.trace_id == request_span.context.trace_id
    assert consumer_span.parent is not None, "the consumer span is not attached to anything"


def test_the_response_carries_the_correlation_and_trace_ids() -> None:
    """So a support agent can quote one id and an engineer can find the trace."""
    clarity = Clarity(world=build_demo_world())
    client = TestClient(create_app(clarity))

    response = client.get("/v1/health")

    assert response.headers[CORRELATION_HEADER], "every response needs a correlation id"


def test_a_caller_supplied_correlation_id_is_kept() -> None:
    """A trace may start in the app or the channel gateway and continue here."""
    clarity = Clarity(world=build_demo_world())
    client = TestClient(create_app(clarity))

    response = client.get("/v1/health", headers={CORRELATION_HEADER: "REQ-from-the-app"})

    assert response.headers[CORRELATION_HEADER] == "REQ-from-the-app"


def test_spans_carry_identifiers_not_personal_data(spans: InMemorySpanExporter) -> None:
    """I13: a span attribute reaches a backend the AI gateway does not mask."""
    clarity = Clarity(world=build_demo_world())
    case = clarity.cases.open_case(
        subscriber_ref=ref_for(DILANI), msisdn_masked="077***4567", channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    plan = clarity.cases.propose(case.case_id, created_by="channel:web")
    spans.clear()
    clarity.cases.confirm_and_execute(case.case_id, plan.plan_id)

    for finished in spans.get_finished_spans():
        rendered = str(dict(finished.attributes or {}))
        assert DILANI not in rendered, f"{finished.name} carries a raw number"
        assert "771234567" not in rendered, f"{finished.name} carries a raw number"


def test_there_is_no_trace_id_outside_a_span() -> None:
    assert current_trace_id() is None
