"""Every deployable meets the deployment contract (ADR-0016, X03 issue #44).

ADR-0016 says each deployable ships one OCI image, takes its config from the
environment, is stateless, and **has health probes**. The last one is easy to
leave out, because a process that starts looks healthy until an orchestrator
asks it something.

`clarity-mcp` had no `/health`. It passed `make check`, started cleanly under
uvicorn and crash-looped in a kind cluster: the liveness probe got 404 and
Kubernetes killed it, over and over. These tests ask each deployable's ASGI app
the same question the probe asks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world


def test_the_api_answers_health() -> None:
    from clarity.interfaces.http.main import create_app

    response = TestClient(create_app(Clarity(world=build_demo_world()))).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_the_mcp_server_answers_health() -> None:
    """Regression: no /health here meant a CrashLoopBackOff in the cluster."""
    from clarity.interfaces.mcp.app import build_mcp_app
    from clarity.interfaces.mcp.server import ClarityMCPServer

    clarity = Clarity(world=build_demo_world())
    app = build_mcp_app(
        ClarityMCPServer(clarity.mcp_view),
        clarity.token_verifier,
        issuer_url="http://localhost:8099",
        resource_url="http://localhost:8099",
    )

    response = StarletteClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_the_mcp_health_endpoint_needs_no_token() -> None:
    """A probe runs before any token exists, so it cannot be authenticated."""
    from clarity.interfaces.mcp.app import build_mcp_app
    from clarity.interfaces.mcp.server import ClarityMCPServer

    clarity = Clarity(world=build_demo_world())
    app = build_mcp_app(
        ClarityMCPServer(clarity.mcp_view),
        clarity.token_verifier,
        issuer_url="http://localhost:8099",
        resource_url="http://localhost:8099",
    )

    assert StarletteClient(app).get("/health").status_code == 200


def test_the_mcp_health_endpoint_reveals_nothing_useful_to_an_attacker() -> None:
    """It is unauthenticated, so it must not list tools or configuration."""
    from clarity.interfaces.mcp.app import build_mcp_app
    from clarity.interfaces.mcp.server import ClarityMCPServer

    clarity = Clarity(world=build_demo_world())
    app = build_mcp_app(
        ClarityMCPServer(clarity.mcp_view),
        clarity.token_verifier,
        issuer_url="http://localhost:8099",
        resource_url="http://localhost:8099",
    )

    body = StarletteClient(app).get("/health").json()

    assert set(body) == {"status", "service"}, f"the probe endpoint leaks: {body}"


def test_the_channel_gateway_answers_health() -> None:
    from clarity.interfaces.channels.gateway import create_channel_gateway_app

    response = TestClient(create_channel_gateway_app(Clarity(world=build_demo_world()))).get(
        "/health"
    )

    assert response.status_code == 200


def test_hutch_sim_answers_health() -> None:
    from clarity.integration.drivers.mock.http_service import create_hutch_sim_app

    assert TestClient(create_hutch_sim_app()).get("/health").status_code == 200


@pytest.mark.parametrize(
    "command",
    [
        ["uvicorn", "clarity.entrypoints.asgi:app", "--host", "0.0.0.0", "--port", "8000"],
        ["uvicorn", "clarity.entrypoints.mcp_asgi:app", "--host", "0.0.0.0", "--port", "8099"],
    ],
)
def test_the_chart_runs_an_entry_point_that_imports(command: list[str]) -> None:
    """A command in values.yaml that names a module that does not exist is a
    defect nothing else catches until a pod starts."""
    import importlib

    target = next(part for part in command if ":" in part)
    module = target.split(":")[0]

    assert importlib.import_module(module), module
