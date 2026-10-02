"""Typed settings, read in one place (B07, ADR-0027, I20).

Every value the process takes from its environment is declared here, validated
here, and handed to drivers as an argument. A driver that reads the environment
itself is invisible to this file, so nobody can tell from one place how a
deployment is configured, and a missing variable surfaces as an obscure failure
deep in a request instead of at startup.

``tests/architecture/test_settings.py`` enforces that: no module outside
``clarity.app`` may read ``os.environ``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsInvalid(RuntimeError):
    """The process is not configured well enough to start.

    Raised at startup with the variable named, because a deployment that is
    missing a database URL should fail while someone is watching, not on the
    first request that needs it.
    """


class Settings(BaseSettings):
    """Everything this process reads from its environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- profile ---------------------------------------------------------- #

    profile: str = Field(
        default="demo",
        alias="CLARITY_PROFILE",
        description="demo (= lite, in memory) | full (real components) | prod (not implemented)",
    )

    # -- data ------------------------------------------------------------- #

    database_url: str | None = Field(
        default=None,
        alias="DATABASE_URL",
        description="PostgreSQL for the full profile. Unset in full: a local SQLite file.",
    )

    # -- messaging -------------------------------------------------------- #

    kafka_bootstrap: str | None = Field(
        default=None,
        alias="CLARITY_KAFKA_BOOTSTRAP",
        description="Unset: the in-process bus. Set: the Kafka driver (needs the kafka extra).",
    )

    # -- simulated HUTCH estate ------------------------------------------ #

    hutch_sim_url: str = Field(
        default="http://localhost:8090",
        alias="CLARITY_HUTCH_SIM_URL",
        description="Private hutch-sim service used by the full profile.",
    )
    hutch_sim_timeout_seconds: float = Field(
        default=3.0,
        alias="CLARITY_HUTCH_SIM_TIMEOUT",
        gt=0,
    )

    # -- identity and crypto ---------------------------------------------- #

    subscriber_hmac_key: str = Field(
        default="clarity-demo-subscriber-key-not-a-secret",
        alias="SUBSCRIBER_HMAC_KEY",
        description="Keys the subscriber_ref pseudonym. A real deployment sets its own.",
    )
    signing_key_path: Path = Field(
        default=Path(".keys/signing.pem"),
        alias="SIGNING_KEY_PATH",
        description="Ed25519 key the signer uses for Trust Receipts.",
    )
    keys_dir: Path = Field(default=Path(".keys"), alias="KEYS_DIR")
    keycloak_issuer: str | None = Field(default=None, alias="CLARITY_KEYCLOAK_ISSUER")
    keycloak_audience: str = Field(default="clarity-api", alias="CLARITY_KEYCLOAK_AUDIENCE")
    keycloak_jwks_url: str | None = Field(default=None, alias="CLARITY_KEYCLOAK_JWKS_URL")
    opa_url: str | None = Field(default=None, alias="CLARITY_OPA_URL")
    auth_timeout_seconds: float = Field(default=3.0, alias="CLARITY_AUTH_TIMEOUT", gt=0)
    signer_url: str | None = Field(default=None, alias="CLARITY_SIGNER_URL")
    signer_token: str | None = Field(default=None, alias="CLARITY_SIGNER_TOKEN")
    signer_key_name: str = Field(default="clarity-receipts", alias="CLARITY_SIGNER_KEY_NAME")
    signer_mount: str = Field(default="transit", alias="CLARITY_SIGNER_MOUNT")
    signer_namespace: str | None = Field(default=None, alias="CLARITY_SIGNER_NAMESPACE")
    signer_timeout_seconds: float = Field(default=3.0, alias="CLARITY_SIGNER_TIMEOUT", gt=0)

    # -- artefacts -------------------------------------------------------- #

    rules_dir: Path | None = Field(default=None, alias="CLARITY_RULES_DIR")
    policy_dir: Path | None = Field(default=None, alias="CLARITY_POLICY_DIR")

    # -- AI --------------------------------------------------------------- #

    model_base_url: str | None = Field(
        default=None,
        alias="CLARITY_MODEL_BASE_URL",
        description="Unset: no model. The gateway answers from approved templates (ADR-0009).",
    )
    model_name: str = Field(default="local-model", alias="CLARITY_MODEL_NAME")
    model_api_key: str | None = Field(default=None, alias="CLARITY_MODEL_API_KEY")
    model_timeout_seconds: float = Field(default=20.0, alias="CLARITY_MODEL_TIMEOUT", gt=0)
    prefer_templates: bool = Field(default=True, alias="AI_PREFER_TEMPLATES")
    cassette_dir: Path = Field(default=Path("cassettes"), alias="AI_CASSETTE_DIR")

    # -- interfaces ------------------------------------------------------- #

    verify_base: str = Field(default="http://localhost:8000/v", alias="VERIFY_BASE")

    # -- observability ---------------------------------------------------- #

    otel_exporter: str = Field(
        default="console",
        alias="OTEL_EXPORTER",
        description="console (lite) | otlp (full) | none",
    )
    otlp_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    log_format: str = Field(default="text", alias="CLARITY_LOG_FORMAT", description="text | json")

    # -- validation ------------------------------------------------------- #

    @model_validator(mode="after")
    def _check_profile_requirements(self) -> Settings:
        if self.profile not in {"demo", "lite", "full", "prod"}:
            raise SettingsInvalid(
                f"CLARITY_PROFILE is {self.profile!r}; it must be one of "
                "demo (= lite), full or prod"
            )
        if self.otel_exporter not in {"console", "otlp", "none"}:
            raise SettingsInvalid(
                f"OTEL_EXPORTER is {self.otel_exporter!r}; it must be console, otlp or none"
            )
        if self.log_format not in {"text", "json"}:
            raise SettingsInvalid(
                f"CLARITY_LOG_FORMAT is {self.log_format!r}; it must be text or json"
            )
        if self.otel_exporter == "otlp" and not self.otlp_endpoint:
            raise SettingsInvalid(
                "OTEL_EXPORTER is otlp but OTEL_EXPORTER_OTLP_ENDPOINT is not set; "
                "the collector address is required"
            )
        if self.signer_url and not self.signer_token:
            raise SettingsInvalid(
                "CLARITY_SIGNER_URL is set but CLARITY_SIGNER_TOKEN is empty; "
                "OpenBao requires a scoped Transit token"
            )
        return self

    @property
    def is_full(self) -> bool:
        return self.profile == "full"

    def require_database_url(self) -> str:
        """The database URL, refusing to guess one for a real deployment.

        The ``full`` profile exists to run against real components. Falling back
        to a local SQLite file there would look like success and quietly give a
        single-writer database that two replicas cannot share.
        """
        if not self.database_url:
            raise SettingsInvalid(
                "CLARITY_PROFILE=full needs DATABASE_URL (for example "
                "postgresql+psycopg://clarity:clarity@localhost:5432/clarity). "
                "Use the demo profile to run with no database."
            )
        return self.database_url


__all__ = ["Settings", "SettingsInvalid"]
