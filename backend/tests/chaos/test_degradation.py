"""The degradation ladder holds when a dependency fails (X02, plan 39).

Plan 15 section 39 is a table of failures and the behaviour each one must
produce. These tests take that table literally: break one dependency, drive the
real journey over HTTP, and assert the row.

They are end-to-end on purpose. `tests/unit/test_ai.py` already proves the AI
gateway falls back to a template when its provider raises; that is the unit.
What a chaos test adds is the rest of the path: that the customer still gets a
`200`, that the case still reaches a decision, and that nothing downstream
treats the degraded answer as an error.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.ai.gateway import Prompt, Usage
from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

from ..acceptance.conftest import DILANI, bearer, customer_token


class DeadProvider:
    """A hosted model that is down. Every call raises, as a timeout would."""

    name = "dead-provider"

    def __init__(self) -> None:
        self.attempts = 0

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        self.attempts += 1
        raise ConnectionError("the provider is unreachable")


@pytest.fixture
def dead() -> DeadProvider:
    return DeadProvider()


@pytest.fixture
def api_without_a_model(dead: DeadProvider) -> TestClient:
    """The whole app, with a provider that fails every call."""
    clarity = Clarity(
        world=build_demo_world(),
        provider=dead,
        verify_base="http://testserver/v",
    )
    return TestClient(create_app(clarity))


# --------------------------------------------------------------------------- #
# Plan 39: "External/hosted AI provider fails -> templates. Customer sees the
# same, possibly shorter."
# --------------------------------------------------------------------------- #


def test_a_customer_still_gets_an_answer_when_the_model_is_down(
    api_without_a_model: TestClient,
):
    """Acceptance: the provider is down, customers ask, templates answer, no errors."""
    api = api_without_a_model
    headers = bearer(customer_token(api, DILANI))

    opened = api.post("/v1/cases", json={"msisdn": DILANI}, headers=headers)
    assert opened.status_code == 201, opened.text
    case_id = opened.json()["case_id"]

    decided = api.post(f"/v1/cases/{case_id}/evaluate", headers=headers)

    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["outcome"] == "ONE_TAP_FIX", "the rules decided without the model (I1)"
    assert body["explanation"].strip(), "the customer was told nothing at all"


def test_the_answer_still_carries_the_amount_the_rules_decided(
    api_without_a_model: TestClient,
):
    """A degraded answer is shorter, not vaguer about money (I1, I3)."""
    api = api_without_a_model
    headers = bearer(customer_token(api, DILANI))
    case_id = api.post("/v1/cases", json={"msisdn": DILANI}, headers=headers).json()["case_id"]

    decided = api.post(f"/v1/cases/{case_id}/evaluate", headers=headers).json()

    assert "49.00" in decided["explanation"], decided["explanation"]


def test_the_whole_money_path_still_completes_without_a_model(
    api_without_a_model: TestClient,
):
    """Fixing and proving never needed the model: rules decide, the LLM explains."""
    api = api_without_a_model
    headers = bearer(customer_token(api, DILANI))
    case_id = api.post("/v1/cases", json={"msisdn": DILANI}, headers=headers).json()["case_id"]
    api.post(f"/v1/cases/{case_id}/evaluate", headers=headers)
    plan_id = api.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "channel:web"}, headers=headers
    ).json()["plan_id"]

    confirmed = api.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan_id}, headers=headers)

    assert confirmed.status_code == 200, confirmed.text
    receipt_id = confirmed.json()["receipt_id"]
    assert receipt_id, "no receipt was issued"

    verified = api.post(f"/v1/receipts/{receipt_id}/verify")
    assert verified.status_code == 200, verified.text
    assert verified.json()["valid"] is True


def test_the_outage_is_visible_rather_than_silent(
    api_without_a_model: TestClient, dead: DeadProvider
):
    """A fallback nobody can see is indistinguishable from a model that works.

    The customer is not shown an error, but the run must be attributable: the
    provider was really called and really failed, rather than the request
    quietly skipping the model path.
    """
    api = api_without_a_model
    headers = bearer(customer_token(api, DILANI))
    case_id = api.post("/v1/cases", json={"msisdn": DILANI}, headers=headers).json()["case_id"]

    api.post(f"/v1/cases/{case_id}/evaluate", headers=headers)

    assert dead.attempts > 0, "the model path was never attempted, so nothing was proven"


def test_a_degraded_answer_is_never_a_stack_trace(api_without_a_model: TestClient):
    """`ConnectionError` text in a customer answer would leak internals."""
    api = api_without_a_model
    headers = bearer(customer_token(api, DILANI))
    case_id = api.post("/v1/cases", json={"msisdn": DILANI}, headers=headers).json()["case_id"]

    explanation = api.post(f"/v1/cases/{case_id}/evaluate", headers=headers).json()["explanation"]

    for leak in ("Traceback", "ConnectionError", "unreachable", "dead-provider"):
        assert leak not in explanation, f"the answer leaked {leak!r}"
