"""Typed settings fail fast and name the variable (issue #15, B07).

A deployment that is misconfigured should stop while someone is watching, with
a message that says which variable to set. The alternative is an obscure failure
on the first request that happens to need the value.
"""

from __future__ import annotations

import pytest

from clarity.app.container import Clarity, Profile
from clarity.app.settings import Settings, SettingsInvalid


def test_the_full_profile_without_a_database_url_stops_and_names_it() -> None:
    settings = Settings(CLARITY_PROFILE="full", DATABASE_URL=None, _env_file=None)

    with pytest.raises(SettingsInvalid, match="DATABASE_URL"):
        Clarity(profile=Profile.FULL, settings=settings)


def test_the_message_says_how_to_run_without_a_database() -> None:
    settings = Settings(CLARITY_PROFILE="full", DATABASE_URL=None, _env_file=None)

    with pytest.raises(SettingsInvalid) as refusal:
        settings.require_database_url()

    message = str(refusal.value)
    assert "postgresql" in message, "the message should show the expected shape"
    assert "demo profile" in message, "and the way to run with no database"


def test_an_unknown_profile_is_refused() -> None:
    with pytest.raises(SettingsInvalid, match="CLARITY_PROFILE"):
        Settings(CLARITY_PROFILE="staging", _env_file=None)


def test_an_unknown_log_format_is_refused() -> None:
    with pytest.raises(SettingsInvalid, match="CLARITY_LOG_FORMAT"):
        Settings(CLARITY_LOG_FORMAT="xml", _env_file=None)


def test_otlp_without_an_endpoint_is_refused() -> None:
    """Exporting to a collector that was never named silently drops traces."""
    with pytest.raises(SettingsInvalid, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
        Settings(OTEL_EXPORTER="otlp", OTEL_EXPORTER_OTLP_ENDPOINT=None, _env_file=None)


def test_httpsms_needs_both_the_user_key_and_sender() -> None:
    with pytest.raises(SettingsInvalid, match="HTTPSMS_API_KEY and HTTPSMS_SENDER"):
        Settings(HTTPSMS_API_KEY="key-only", HTTPSMS_SENDER=None, _env_file=None)


def test_httpsms_refuses_a_phone_scoped_key_for_sending() -> None:
    with pytest.raises(SettingsInvalid, match="phone-scoped pk_ key"):
        Settings(
            HTTPSMS_API_KEY="pk_phone-key",
            HTTPSMS_SENDER="+94780000000",
            _env_file=None,
        )


def test_the_defaults_run_with_no_environment_at_all() -> None:
    """ADR-0006: clone and run, no infrastructure and no configuration."""
    settings = Settings(_env_file=None)

    assert settings.profile == "demo"
    assert settings.database_url is None
    assert settings.kafka_bootstrap is None
    assert settings.model_base_url is None, "no model by default (ADR-0009)"


def test_lite_is_accepted_as_the_name_for_demo() -> None:
    """The plan and ADR-0027 say lite; the container calls it demo."""
    assert Settings(CLARITY_PROFILE="lite", _env_file=None).profile == "lite"
    assert (
        Clarity(settings=Settings(CLARITY_PROFILE="lite", _env_file=None)).profile is Profile.DEMO
    )


def test_settings_are_passed_in_rather_than_read_from_the_process() -> None:
    """A test configures the app by argument, never by mutating the environment."""
    settings = Settings(VERIFY_BASE="https://verify.example/v", _env_file=None)
    clarity = Clarity(settings=settings)

    assert clarity.settings.verify_base == "https://verify.example/v"
    assert clarity._verify_base == "https://verify.example/v"


def test_configured_signing_key_survives_a_restart(tmp_path) -> None:
    """Synthetic VPS receipts must remain verifiable after a container restart."""
    key_path = tmp_path / "private" / "signing.pem"
    settings = Settings(SIGNING_KEY_PATH=key_path, _env_file=None)

    first = Clarity(settings=settings)
    first_public_keys = first.signing.public_keys()
    second = Clarity(settings=settings)

    assert key_path.stat().st_mode & 0o777 == 0o600
    assert second.signing.public_keys() == first_public_keys


def test_unset_signing_key_path_writes_nothing(tmp_path, monkeypatch) -> None:
    """Helm runs the image with a read-only root filesystem.

    Defaulting the key path to `.keys/signing.pem` made every pod crash on
    `mkdir` (CI run 37180558291). Unset, the signer keeps its key in memory and
    the working directory stays untouched.
    """
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)

    clarity = Clarity(settings=settings)

    assert settings.signing_key_path is None
    assert clarity.signing.public_keys()
    assert list(tmp_path.iterdir()) == []
