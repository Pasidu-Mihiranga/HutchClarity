"""Abuse / auth boundary tests for clarity-mcp."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# services/mcp is a thin satellite; add its src to path for the test.
_MCP_SRC = Path(__file__).resolve().parents[3] / "services" / "mcp" / "src"
if str(_MCP_SRC) not in sys.path:
    sys.path.insert(0, str(_MCP_SRC))

from main import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_mcp_tool_rejects_missing_auth(client: TestClient) -> None:
    response = client.post(
        "/tools/get_case_timeline",
        json={"case_id": "CASE-DEMO-001"},
    )
    assert response.status_code == 401
    assert "Bearer" in response.json()["detail"] or "token" in response.json()["detail"].lower()


def test_propose_action_without_idempotency_key_fails(client: TestClient) -> None:
    response = client.post(
        "/tools/propose_action",
        headers={"Authorization": "Bearer dev-token"},
        json={"case_id": "CASE-DEMO-001", "action_type": "cancel_vas"},
    )
    assert response.status_code == 422  # pydantic: idempotency_key required


def test_propose_action_with_idempotency_key_ok(client: TestClient) -> None:
    response = client.post(
        "/tools/propose_action",
        headers={"Authorization": "Bearer dev-token"},
        json={
            "case_id": "CASE-DEMO-001",
            "action_type": "cancel_vas",
            "idempotency_key": "demo-idem-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["result"]["idempotency_key"] == "demo-idem-1"
