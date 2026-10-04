"""Operations dashboards as a real resource (D2).

The projection has existed since I01. Its only surface was `GET /v1/demo/ops`,
a route tagged `demo`, which is not where a desk's dashboard belongs: a
console running a shift was reading a demonstration endpoint.

The numbers are unchanged. These assert the two properties that make them
worth reading, and the one that makes them safe to act on.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

from .conftest import bearer, staff_token


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def api(clarity: Clarity) -> TestClient:
    return TestClient(create_app(clarity))


@pytest.fixture
def desk(api: TestClient) -> dict[str, str]:
    return bearer(staff_token(api, "sup:dilani", ["supervisor"], step_up=False))


def test_the_dashboards_need_a_session(api: TestClient) -> None:
    assert api.get("/v1/insights/dashboards").status_code == 401


def test_a_customer_cannot_read_the_desk_dashboards(api: TestClient) -> None:
    """They aggregate across every subscriber, so they are staff-only."""
    from .conftest import DILANI, customer_token

    me = bearer(customer_token(api, DILANI))

    assert api.get("/v1/insights/dashboards", headers=me).status_code == 403


def test_the_dashboards_carry_every_board(api: TestClient, desk: dict[str, str]) -> None:
    board = api.get("/v1/insights/dashboards", headers=desk)

    assert board.status_code == 200, board.text
    body = board.json()
    for name in (
        "top_causes",
        "where_ai_stops",
        "drop_offs",
        "refunds_by_rule",
        "outcomes",
        "events_folded",
    ):
        assert name in body, f"{name} missing from the dashboards"


def test_the_dashboards_say_where_their_numbers_came_from(
    api: TestClient, desk: dict[str, str]
) -> None:
    """`events_folded` is the count that makes the figures checkable: a reader
    can tell whether the projection has seen the log they are asking about."""
    body = api.get("/v1/insights/dashboards", headers=desk).json()

    assert isinstance(body["events_folded"], int)
    assert "event log" in body["note"]


def test_money_is_never_a_float(api: TestClient, desk: dict[str, str]) -> None:
    """I3. A figure a desk acts on has to be the figure the ledger holds, and
    this dashboard used to sum with `money += float(stake)`."""
    body = api.get("/v1/insights/dashboards", headers=desk).json()

    for rule in body["refunds_by_rule"]:
        for key, value in rule.items():
            assert not isinstance(value, float), f"{key} came back as a float"


def test_the_real_route_answers_the_same_numbers_as_the_demo_one(
    api: TestClient, desk: dict[str, str]
) -> None:
    """The move is a change of address, not of arithmetic. Asserted so the
    demo route can be retired without anybody wondering what changed."""
    real = api.get("/v1/insights/dashboards", headers=desk).json()
    demo = api.get("/v1/demo/ops", headers=desk).json()

    assert real == demo
