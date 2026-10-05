"""The admin MCP connector, black box over `/v1` (OPS01).

The console's admin page carried a hard-coded list of three names under the
line "Placeholder inventory - not connected to live MCP clients". The server
it was describing was real: `clarity-mcp` is a separate deployable with an
OAuth 2.1 resource server in front of a tool registry.

What these pin is the part that would rot the same way again: the inventory is
**read from the registry**, so a tool added to `ClarityMCPServer` appears here
without anyone updating a page. Plus the two properties that make it safe to
hand an operator a connection recipe: it is admin-only, and it carries no
secret.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

from .conftest import bearer, staff_token


@pytest.fixture
def api() -> TestClient:
    return TestClient(create_app(Clarity(world=build_demo_world())))


@pytest.fixture
def admin(api: TestClient) -> dict[str, str]:
    return bearer(staff_token(api, "plat:sam", ["platform_admin"], step_up=True))


# ------------------------------------------------------------- the inventory


def test_the_tools_come_from_the_registry(api: TestClient, admin: dict[str, str]) -> None:
    """Not a list typed into a page, which is what this replaced.

    Asserted against the registry itself rather than against a fixed count, so
    adding a tool does not fail this test and forgetting to update a page
    cannot pass it.
    """
    from clarity.interfaces.mcp.server import ClarityMCPServer, Profile

    clarity = Clarity(world=build_demo_world())
    registry = ClarityMCPServer(clarity.mcp_view)
    expected = {
        profile.value: {tool["name"] for tool in registry.list_tools(profile)}
        for profile in Profile
    }

    body = api.get("/v1/admin/mcp", headers=admin).json()
    reported = {
        profile["profile"]: {tool["name"] for tool in profile["tools"]}
        for profile in body["profiles"]
    }
    assert reported == expected


def test_every_profile_names_the_scope_that_selects_it(
    api: TestClient, admin: dict[str, str]
) -> None:
    """A client cannot widen itself by asking, so the scope is the thing to publish."""
    from clarity.interfaces.mcp.auth import PROFILE_SCOPES

    body = api.get("/v1/admin/mcp", headers=admin).json()
    reported = {profile["profile"]: profile["scope"] for profile in body["profiles"]}
    assert reported == {profile.value: scope for scope, profile in PROFILE_SCOPES.items()}


def test_customer_assist_is_reported_as_case_bound(
    api: TestClient, admin: dict[str, str]
) -> None:
    """The property that stops one subscriber's agent reading another's case."""
    body = api.get("/v1/admin/mcp", headers=admin).json()
    bound = {profile["profile"]: profile["case_bound"] for profile in body["profiles"]}
    assert bound["customer-assist"] is True
    assert bound["staff-assist"] is False


def test_no_tool_executes_and_the_page_says_so(api: TestClient, admin: dict[str, str]) -> None:
    """I1 as published contract, not only as a handler."""
    body = api.get("/v1/admin/mcp", headers=admin).json()
    staff = next(p for p in body["profiles"] if p["profile"] == "staff-assist")
    by_name = {tool["name"]: tool for tool in staff["tools"]}

    # The strongest thing on the surface is a proposal.
    assert by_name["propose_action"]["level"] == "L3"
    assert "never executes" in by_name["propose_action"]["description"]
    # L4 is bulk admin. Nothing on the MCP surface is one.
    assert all(tool["level"] != "L4" for tool in staff["tools"])
    assert any("no amount" in line for line in body["guarantees"])


def test_the_endpoint_and_the_discovery_url_are_reported(
    api: TestClient, admin: dict[str, str]
) -> None:
    """What an operator actually has to paste into the other system."""
    body = api.get("/v1/admin/mcp", headers=admin).json()
    assert body["server"]["transport"] == "Streamable HTTP"
    assert body["server"]["resource_url"].endswith("/mcp")
    assert body["authorization"]["discovery_url"].endswith(
        "/.well-known/oauth-protected-resource"
    )
    assert body["authorization"]["resource_indicator"] == body["server"]["resource_url"]


# ----------------------------------------------------------------- no secrets


def test_the_connector_carries_no_secret(api: TestClient, admin: dict[str, str]) -> None:
    """I14. The client id is public; the secret stays in the identity provider.

    A connection recipe is exactly the kind of screen a secret gets added to
    for convenience, so this asserts the shape of the payload rather than
    trusting a reviewer to notice.
    """
    body = api.get("/v1/admin/mcp", headers=admin).json()
    flat = str(body).lower()
    for forbidden in ("client_secret", "secret=", "password", "private_key"):
        assert forbidden not in flat, forbidden
    assert body["authorization"]["client_id"] == "clarity-mcp"
    assert "identity provider" in body["authorization"]["secret_hint"]


# ------------------------------------------------------------------ the probe


def test_the_health_probe_reports_an_unreachable_server_rather_than_failing(
    api: TestClient, admin: dict[str, str]
) -> None:
    """`clarity-mcp` is a separate process and is not running in this test.

    "We asked and got nothing" is the answer. A 500 here would read as the
    console being broken rather than the thing it was asking about.
    """
    response = api.get("/v1/admin/mcp/health", headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert body["reachable"] is False
    assert body["status"] == "unreachable"
    assert body["url"].endswith("/health")


# ------------------------------------------------------------ who may read it


@pytest.mark.parametrize(
    ("user_ref", "roles"),
    [
        ("agent:nadeesha", ["agent"]),
        ("sup:ruwan", ["supervisor"]),
        ("comp:ravi", ["compliance"]),
        ("cxe:tharindu", ["cx_engineer"]),
    ],
)
def test_only_an_admin_may_read_the_connector(
    api: TestClient, user_ref: str, roles: list[str]
) -> None:
    """Connection details are operational detail about the way in.

    Not a secret, and still not something an agent needs: the endpoint, the
    scopes and the resource indicator together are the recipe for pointing a
    client at this system.
    """
    headers = bearer(staff_token(api, user_ref, roles, step_up=True))
    assert api.get("/v1/admin/mcp", headers=headers).status_code == 403
    assert api.get("/v1/admin/mcp/health", headers=headers).status_code == 403


def test_security_admin_may_read_it(api: TestClient) -> None:
    """`admin:manage` is platform's and security's."""
    headers = bearer(staff_token(api, "sec:dilani", ["security_admin"], step_up=True))
    assert api.get("/v1/admin/mcp", headers=headers).status_code == 200


def test_an_anonymous_caller_is_refused(api: TestClient) -> None:
    assert api.get("/v1/admin/mcp").status_code == 401
    assert api.get("/v1/admin/mcp/health").status_code == 401
