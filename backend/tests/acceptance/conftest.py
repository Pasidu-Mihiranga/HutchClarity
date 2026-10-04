"""R0 acceptance suite: the /v1 contract, frozen before the migration rewires modules.

Black-box by design: tests talk HTTP only. The one exception is building the app
(``create_app`` over a fresh synthetic world), which is how any client would get
a running server. If a migration step changes behaviour here, it is a deliberate
contract change: update the test, CHANGELOG.md and the consumers' MODULE.md.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

DILANI = "+94781234567"  # VAS without consent -> ONE_TAP_FIX, LKR 49
NIMAL = "+94782223333"  # duplicate reload -> AUTO_FIX
KUMAR = "+94783334444"  # disclosed fair-use cap -> EXPLAIN_ONLY
PRIYA = "+94784445555"  # LKR 12,000 reload, SIM swap -> STAFF_APPROVAL


@pytest.fixture
def api() -> TestClient:
    """A fresh server over a fresh synthetic world, with no credentials."""
    clarity = Clarity(world=build_demo_world(), verify_base="http://testserver/v")
    return TestClient(create_app(clarity))


def customer_token(api: TestClient, msisdn: str) -> str:
    """Sign in the way the customer page does: OTP through the simulated inbox."""
    started = api.post("/v1/auth/otp/request", json={"msisdn": msisdn})
    assert started.status_code == 200, started.text
    code = api.get("/v1/auth/otp/inbox", params={"msisdn": msisdn}).json()["code"]
    verified = api.post(
        "/v1/auth/otp/verify",
        json={"challenge_id": started.json()["challenge_id"], "code": code},
    )
    assert verified.status_code == 200, verified.text
    return str(verified.json()["token"])


def staff_token(api: TestClient, user_ref: str, roles: list[str], *, step_up: bool) -> str:
    session = api.post(
        "/v1/auth/staff/session", json={"user_ref": user_ref, "roles": roles, "step_up": step_up}
    )
    assert session.status_code == 200, session.text
    return str(session.json()["token"])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
