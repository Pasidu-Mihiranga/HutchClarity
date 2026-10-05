"""Request rate limiting (A8).

Nothing in `backend/src` limited a request rate before this. The OTP service
throttles challenges per number (TH1) and `ai/buckets.py` rations provider token
spend by priority; neither counts requests. So `/v1/conversation/turn`, which
runs masking, intake, a flow step, retrieval and composition and can be called
with no session at all, could be run in a loop by anyone with the URL.

Two groups of tests: the counter's own behaviour, and the middleware's choice of
who to count against, which is the part that would be wrong in a way nobody
notices.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app
from clarity.platform.throttle import WINDOW, MemoryRateLimiter

NOON = datetime(2027, 3, 1, 12, 0, tzinfo=None).replace(tzinfo=None)


@pytest.fixture
def limiter() -> MemoryRateLimiter:
    return MemoryRateLimiter()


def test_calls_inside_the_limit_are_allowed(limiter: MemoryRateLimiter) -> None:
    for _ in range(5):
        assert limiter.check("caller", limit=5, now=NOON).allowed


def test_the_call_past_the_limit_is_refused(limiter: MemoryRateLimiter) -> None:
    for _ in range(5):
        limiter.check("caller", limit=5, now=NOON)

    verdict = limiter.check("caller", limit=5, now=NOON)

    assert not verdict.allowed
    assert verdict.retry_after_seconds > 0
    assert verdict.headers["Retry-After"] == str(verdict.retry_after_seconds)


def test_the_budget_returns_in_the_next_window(limiter: MemoryRateLimiter) -> None:
    for _ in range(5):
        limiter.check("caller", limit=5, now=NOON)
    assert not limiter.check("caller", limit=5, now=NOON).allowed

    assert limiter.check("caller", limit=5, now=NOON + WINDOW).allowed


def test_callers_do_not_share_a_budget(limiter: MemoryRateLimiter) -> None:
    for _ in range(5):
        limiter.check("one", limit=5, now=NOON)

    assert limiter.check("two", limit=5, now=NOON).allowed


def test_asking_is_counting(limiter: MemoryRateLimiter) -> None:
    """A limiter with a free 'may I?' can be walked past by never asking."""
    first = limiter.check("caller", limit=3, now=NOON)
    second = limiter.check("caller", limit=3, now=NOON)

    assert first.remaining == 2
    assert second.remaining == 1


def test_a_zero_limit_is_a_bug_not_a_lockout(limiter: MemoryRateLimiter) -> None:
    """Refusing everything is never what somebody meant to configure."""
    with pytest.raises(ValueError):
        limiter.check("caller", limit=0, now=NOON)


# --------------------------------------------------------------------------- #
# The middleware
# --------------------------------------------------------------------------- #


@pytest.fixture
def api() -> TestClient:
    return TestClient(create_app(Clarity(world=build_demo_world())))


def test_an_anonymous_flood_is_refused_with_a_problem_document(api: TestClient) -> None:
    body = {"text": "why was I charged"}

    statuses = [api.post("/v1/conversation/turn", json=body).status_code for _ in range(60)]

    assert 429 in statuses, "an anonymous caller ran 60 turns without being throttled"

    refused = api.post("/v1/conversation/turn", json=body)
    assert refused.status_code == 429
    assert refused.headers["content-type"].startswith("application/problem+json")
    assert refused.json()["code"] == "RATE_LIMITED"
    assert "Retry-After" in refused.headers


def test_the_streaming_twin_shares_the_budget(api: TestClient) -> None:
    """Otherwise a caller refused on /turn simply moves to /turn/stream."""
    body = {"text": "why was I charged"}
    for _ in range(60):
        api.post("/v1/conversation/turn", json=body)

    streamed = api.post("/v1/conversation/turn/stream", json=body)

    assert streamed.status_code == 429


def test_an_unthrottled_route_is_untouched(api: TestClient) -> None:
    """The limiter covers the anonymous, expensive routes and nothing else."""
    for _ in range(60):
        api.post("/v1/conversation/turn", json={"text": "why was I charged"})

    assert api.get("/health").status_code == 200


def test_a_refused_call_never_enters_the_pipeline(api: TestClient) -> None:
    """A 429 must cost nothing: that is the whole point of refusing early."""
    body = {"text": "why was I charged"}
    for _ in range(80):
        api.post("/v1/conversation/turn", json=body)

    refused = api.post("/v1/conversation/turn", json=body)

    assert refused.status_code == 429
    assert "turn" not in refused.json()


def test_a_refused_call_still_tells_the_browser_which_origin(api: TestClient) -> None:
    """A 429 without CORS headers is what the sign-in page calls Failed to fetch."""
    body = {"text": "why was I charged"}
    for _ in range(80):
        api.post("/v1/conversation/turn", json=body)

    refused = api.post(
        "/v1/conversation/turn",
        json=body,
        headers={"Origin": "http://localhost:3000"},
    )

    assert refused.status_code == 429
    assert refused.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert refused.headers["access-control-allow-credentials"] == "true"
