"""Security response headers on every response (X01, issue #42).

Found by the OWASP ZAP baseline: six missing-header rules across every page and
asset. The headers are only worth adding if they are on *every* response, so
these tests check the paths that are easy to miss: errors, 404s, and the
public endpoints that carry no credentials.

`/` is one of them, and it is a 404 since FE01 retired the static UI: a path
with no route still has to carry every header, because that is exactly where
middleware tends to stop short.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.headers import SECURITY_HEADERS
from clarity.interfaces.http.main import create_app


@pytest.fixture
def api() -> TestClient:
    return TestClient(create_app(Clarity(world=build_demo_world())))


PATHS = ["/health", "/", "/openapi.json", "/v1/cases", "/does-not-exist"]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("header", sorted(SECURITY_HEADERS))
def test_every_response_carries_every_security_header(
    api: TestClient, path: str, header: str
) -> None:
    """Including errors and 404s, which is where middleware usually stops short."""
    response = api.get(path)

    assert response.headers.get(header) == SECURITY_HEADERS[header], (
        f"{path} answered {response.status_code} without {header}"
    )


def test_the_app_refuses_to_be_framed(api: TestClient) -> None:
    """A confirm button inside someone else's iframe is the attack that matters."""
    headers = api.get("/").headers

    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_a_customers_data_is_never_stored_by_an_intermediary(api: TestClient) -> None:
    """A case or a receipt in a shared cache is a disclosure waiting to happen."""
    assert api.get("/v1/cases").headers["Cache-Control"] == "no-store"


def test_public_assets_stay_cacheable(api: TestClient) -> None:
    """no-store on everything would be a performance bug dressed as security."""
    assert "max-age" in api.get("/openapi.json").headers["Cache-Control"]
    assert "max-age" in api.get("/docs").headers["Cache-Control"]


def test_a_route_that_sets_its_own_header_is_not_overwritten(api: TestClient) -> None:
    """`setdefault`, so a route with a deliberate policy keeps it."""
    response = api.get("/health")

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"


def test_the_csp_forbids_inline_script(api: TestClient) -> None:
    """`unsafe-inline` for script would make the CSP decorative."""
    policy = api.get("/").headers["Content-Security-Policy"]

    assert "script-src 'self'" in policy
    assert "'unsafe-inline'" not in policy.split("script-src")[1].split(";")[0]
