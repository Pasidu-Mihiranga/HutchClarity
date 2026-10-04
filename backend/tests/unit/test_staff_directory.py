"""Staff directory: the server assigns the role, the browser does not."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity, Profile
from clarity.app.settings import Settings, SettingsInvalid
from clarity.interfaces.http.main import create_app
from clarity.modules.iam.directory import (
    LoginRefused,
    StaffDirectory,
    StaffDirectoryInvalid,
    hash_secret,
)
from clarity.platform.security.principal import Assurance, Role

DIRECTORY = json.dumps(
    {
        "accounts": [
            {
                "username": "supervisor",
                "user_ref": "sup-1",
                "role": "supervisor",
                "password_hash": hash_secret("supervisor-clarity"),
                "step_up_hash": hash_secret("step-up"),
            },
            {
                "username": "auditor",
                "user_ref": "aud-1",
                "role": "auditor",
                "password_hash": hash_secret("auditor-clarity"),
                "step_up_hash": hash_secret("step-up"),
            },
        ]
    }
)


def _settings() -> Settings:
    return Settings(CLARITY_STAFF_DIRECTORY=DIRECTORY, _env_file=None)


def _client() -> TestClient:
    return TestClient(create_app(Clarity(settings=_settings())))


def test_password_assigns_the_directory_role_not_a_requested_one() -> None:
    response = _client().post(
        "/v1/auth/staff/login",
        json={
            "username": "supervisor",
            "password": "supervisor-clarity",
            "step_up_code": "step-up",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "sup-1"
    assert body["roles"] == ["supervisor"]
    assert body["assurance"] == "mfa-recent"
    assert "action:approve" in body["permissions"]


def test_omitting_the_step_up_code_signs_in_below_the_cap() -> None:
    identity = StaffDirectory.load(DIRECTORY).authenticate("auditor", "auditor-clarity", "")
    assert identity.role is Role.AUDITOR
    assert identity.assurance is Assurance.MFA


def test_wrong_password_and_wrong_step_up_code_look_the_same() -> None:
    client = _client()
    wrong_password = client.post(
        "/v1/auth/staff/login",
        json={"username": "supervisor", "password": "nope", "step_up_code": "step-up"},
    )
    wrong_code = client.post(
        "/v1/auth/staff/login",
        json={"username": "supervisor", "password": "supervisor-clarity", "step_up_code": "nope"},
    )
    assert wrong_password.status_code == 401
    assert wrong_code.status_code == 401
    assert wrong_password.json() == wrong_code.json()


def test_a_configured_directory_closes_the_role_assertion_route() -> None:
    client = _client()
    blocked = client.post(
        "/v1/auth/staff/session",
        json={"user_ref": "sup-1", "roles": ["finance"], "step_up": True},
    )
    assert blocked.status_code == 404
    # The client asked to become finance. The directory did not allow it.
    login = client.post(
        "/v1/auth/staff/login",
        json={"username": "supervisor", "password": "supervisor-clarity"},
    )
    assert login.json()["roles"] == ["supervisor"]


def test_login_does_not_exist_in_prod() -> None:
    clarity = Clarity(settings=_settings())
    clarity.profile = Profile.PROD
    client = TestClient(create_app(clarity))
    response = client.post(
        "/v1/auth/staff/login",
        json={
            "username": "supervisor",
            "password": "supervisor-clarity",
            "step_up_code": "step-up",
        },
    )
    assert response.status_code == 404


def test_a_missing_directory_file_stops_startup(tmp_path: Path) -> None:
    missing = tmp_path / "absent.json"
    with pytest.raises(SettingsInvalid, match="CLARITY_STAFF_DIRECTORY_FILE"):
        Clarity(settings=Settings(CLARITY_STAFF_DIRECTORY_FILE=missing, _env_file=None))


def test_directory_refuses_an_unknown_user_without_raising_a_different_error() -> None:
    directory = StaffDirectory.load(DIRECTORY)
    with pytest.raises(LoginRefused):
        directory.authenticate("nobody", "supervisor-clarity", "step-up")


def test_a_plaintext_password_in_the_file_is_refused() -> None:
    raw = json.dumps(
        {
            "accounts": [
                {
                    "username": "agent",
                    "user_ref": "a-1",
                    "role": "agent",
                    "password": "agent-clarity",
                    "step_up_code": "step-up",
                }
            ]
        }
    )
    with pytest.raises(StaffDirectoryInvalid, match="plaintext"):
        StaffDirectory.load(raw)


def test_an_unknown_username_is_refused_like_a_wrong_password() -> None:
    directory = StaffDirectory.load(DIRECTORY)
    with pytest.raises(LoginRefused):
        directory.authenticate("nobody", "supervisor-clarity", "")


def test_the_committed_synthetic_directory_holds_no_plaintext_secret() -> None:
    path = Path(__file__).resolve().parents[3] / "config" / "staff" / "synthetic-directory.json"
    raw = path.read_text()
    directory = StaffDirectory.load(raw)
    assert 'clarity"' not in raw and '"password"' not in raw
    assert directory.authenticate("supervisor", "supervisor-clarity", "").role is Role.SUPERVISOR
