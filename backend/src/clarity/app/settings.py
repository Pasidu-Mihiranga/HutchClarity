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
    signing_key_path: Path | None = Field(
        default=None,
        alias="SIGNING_KEY_PATH",
        description=(
            "Ed25519 key the development signer persists for Trust Receipts. "
            "Unset keeps the key in memory, so a read-only container still starts."
        ),
    )
    keys_dir: Path | None = Field(
        default=None,
        alias="KEYS_DIR",
        description=(
            "Directory for the development keys this process persists: the "
            "customer token issuer key. Unset keeps it in memory, so every "
            "restart signs everyone out."
        ),
    )
    keycloak_issuer: str | None = Field(default=None, alias="CLARITY_KEYCLOAK_ISSUER")
    keycloak_audience: str = Field(default="clarity-api", alias="CLARITY_KEYCLOAK_AUDIENCE")
    keycloak_jwks_url: str | None = Field(default=None, alias="CLARITY_KEYCLOAK_JWKS_URL")
    oidc_client_id: str = Field(
        default="clarity-console",
        alias="CLARITY_OIDC_CLIENT_ID",
        description="The confidential client the API uses for staff sign-in (B1).",
    )
    oidc_client_secret: str | None = Field(
        default=None,
        alias="CLARITY_OIDC_CLIENT_SECRET",
        description=(
            "Its secret. Staff SSO is off until this is set, because a "
            "confidential client with no secret is a public client nobody "
            "decided to make public."
        ),
    )
    oidc_redirect_uri: str | None = Field(
        default=None,
        alias="CLARITY_OIDC_REDIRECT_URI",
        description=(
            "Where the provider sends the browser back. Must be this API's own "
            "callback and must match a redirect URI registered on the client."
        ),
    )
    allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3101,http://127.0.0.1:3101,http://localhost:3102,http://127.0.0.1:3102,http://localhost:3100,http://127.0.0.1:3100",
        alias="CLARITY_ALLOWED_ORIGINS",
        description=(
            "Comma-separated browser origins allowed to call this API with "
            "credentials. The wildcard is not an option: CORS forbids it with "
            "credentials, and the staff console signs in with a cookie."
        ),
    )
    console_base_url: str = Field(
        default="http://127.0.0.1:3101",
        alias="CLARITY_CONSOLE_BASE_URL",
        description="Where a completed sign-in returns the browser to.",
    )
    cookie_secure: bool = Field(
        default=False,
        alias="CLARITY_COOKIE_SECURE",
        description=(
            "Whether the staff session cookie carries Secure. False only for "
            "local http development; any deployment sets it."
        ),
    )
    staff_directory: str | None = Field(
        default=None,
        alias="CLARITY_STAFF_DIRECTORY",
        description=(
            "JSON staff accounts. When set, the browser cannot choose a role: "
            "POST /v1/auth/staff/login checks this directory and "
            "POST /v1/auth/staff/session answers 404."
        ),
    )
    staff_directory_file: Path | None = Field(
        default=None,
        alias="CLARITY_STAFF_DIRECTORY_FILE",
        description="Path to that JSON document. The inline variable wins when both are set.",
    )
    sms_url: str | None = Field(
        default=None,
        alias="CLARITY_SMS_URL",
        description=(
            "The SMS gateway one-time codes are delivered through (B6). "
            "Without it the simulated inbox is used, which is correct for the "
            "synthetic profiles and useless in prod. REQUIRES HUTCH "
            "CONFIRMATION of the real SMSC interface."
        ),
    )
    sms_token: str | None = Field(default=None, alias="CLARITY_SMS_TOKEN")
    sms_sender: str = Field(default="HutchClarity", alias="CLARITY_SMS_SENDER")
    httpsms_api_key: str | None = Field(default=None, alias="HTTPSMS_API_KEY")
    httpsms_sender: str | None = Field(default=None, alias="HTTPSMS_SENDER")
    httpsms_base_url: str = Field(default="https://api.httpsms.com/v1", alias="HTTPSMS_BASE_URL")
    httpsms_timeout_seconds: float = Field(default=10.0, alias="HTTPSMS_TIMEOUT", gt=0)
    linked_phones: str | None = Field(
        default=None,
        alias="CLARITY_LINKED_PHONES",
        description=(
            "Real phones that sign in as a synthetic customer, as "
            "'real=synthetic' pairs separated by commas. Only these numbers "
            "receive a real SMS; set on the server, never committed."
        ),
    )
    opa_url: str | None = Field(default=None, alias="CLARITY_OPA_URL")
    # The clarity-mcp deployable (A04, ADR-0018).
    mcp_resource_url: str = Field(
        default="http://localhost:8081/mcp",
        alias="CLARITY_MCP_RESOURCE_URL",
        description="This MCP server's own identifier (RFC 8707 resource indicator).",
    )
    mcp_allowed_hosts: str = Field(
        default="",
        alias="CLARITY_MCP_ALLOWED_HOSTS",
        description="Comma-separated Host headers the MCP server answers to. "
        "Empty: the host in CLARITY_MCP_RESOURCE_URL. Never a wildcard.",
    )
    mcp_api_url: str = Field(
        default="http://localhost:8000",
        alias="CLARITY_MCP_API_URL",
        description="Base URL of clarity-api, which clarity-mcp calls for every tool.",
    )
    mcp_exchange_url: str | None = Field(
        default=None,
        alias="CLARITY_MCP_EXCHANGE_URL",
        description="RFC 8693 token-exchange endpoint. Unset: downstream calls are "
        "refused rather than forwarding the client's token (ADR-0018).",
    )
    auth_timeout_seconds: float = Field(default=3.0, alias="CLARITY_AUTH_TIMEOUT", gt=0)
    signer_url: str | None = Field(default=None, alias="CLARITY_SIGNER_URL")
    signer_token: str | None = Field(default=None, alias="CLARITY_SIGNER_TOKEN")
    signer_key_name: str = Field(default="clarity-receipts", alias="CLARITY_SIGNER_KEY_NAME")
    audit_signer_key_name: str = Field(
        default="clarity-audit-checkpoints",
        alias="CLARITY_AUDIT_SIGNER_KEY_NAME",
        description=(
            "OpenBao Transit key that signs audit checkpoints (ADR-0035). Separate "
            "from the receipt key, so a compromise of one cannot forge the other."
        ),
    )
    audit_backup_key: str | None = Field(
        default=None,
        alias="CLARITY_AUDIT_BACKUP_KEY",
        description=(
            "Secret that encrypts audit backup bundles (Phase 6). Unset: backups "
            "are refused rather than written in the clear. A deployment sets a "
            "32-byte random value; any length works and is hashed to the key."
        ),
    )
    audit_backup_dir: Path = Field(
        default=Path(".backups"),
        alias="CLARITY_AUDIT_BACKUP_DIR",
        description="Where backup bundles are written. A mounted volume in full.",
    )
    signer_mount: str = Field(default="transit", alias="CLARITY_SIGNER_MOUNT")
    signer_namespace: str | None = Field(default=None, alias="CLARITY_SIGNER_NAMESPACE")
    signer_timeout_seconds: float = Field(default=3.0, alias="CLARITY_SIGNER_TIMEOUT", gt=0)

    # -- artefacts -------------------------------------------------------- #

    rules_dir: Path | None = Field(default=None, alias="CLARITY_RULES_DIR")
    policy_dir: Path | None = Field(default=None, alias="CLARITY_POLICY_DIR")
    flows_dir: Path | None = Field(default=None, alias="CLARITY_FLOWS_DIR")
    retrieval_file: Path | None = Field(default=None, alias="CLARITY_RETRIEVAL_FILE")
    channel_webhook_secret: str | None = Field(
        default=None,
        alias="CLARITY_CHANNEL_WEBHOOK_SECRET",
        description=(
            "HMAC secret the channel gateway verifies inbound webhooks against "
            "(N02). Unset: every webhook is refused, which is the safe "
            "direction. The simulator routes do not use it."
        ),
    )

    # -- AI --------------------------------------------------------------- #

    model_base_url: str | None = Field(
        default=None,
        alias="CLARITY_MODEL_BASE_URL",
        description="Unset: no model. The gateway answers from approved templates (ADR-0009).",
    )
    model_name: str = Field(default="local-model", alias="CLARITY_MODEL_NAME")
    model_api_key: str | None = Field(default=None, alias="CLARITY_MODEL_API_KEY")
    model_timeout_seconds: float = Field(default=20.0, alias="CLARITY_MODEL_TIMEOUT", gt=0)
    vertex_project: str | None = Field(
        default=None,
        alias="CLARITY_VERTEX_PROJECT",
        description="Vertex AI project. Unset: this process does not call Vertex.",
    )
    vertex_location: str = Field(default="global", alias="CLARITY_VERTEX_LOCATION")
    prefer_templates: bool = Field(default=True, alias="AI_PREFER_TEMPLATES")
    cassette_dir: Path = Field(default=Path("cassettes"), alias="AI_CASSETTE_DIR")
    record_cassettes: bool = Field(
        default=False,
        alias="CLARITY_RECORD_CASSETTES",
        description="Record model responses instead of replaying them (A02). Needs a provider.",
    )
    models_file: Path | None = Field(
        default=None,
        alias="CLARITY_MODELS_FILE",
        description="Model roles and provider chains. Unset: config/ai/models.yaml.",
    )

    # -- interfaces ------------------------------------------------------- #

    verify_base: str = Field(default="http://localhost:3002/r", alias="VERIFY_BASE")

    # -- audit ------------------------------------------------------------ #

    audit_break_glass: bool = Field(
        default=False,
        alias="CLARITY_AUDIT_BREAK_GLASS",
        description=(
            "Start even when the audit chain fails verification (ADR-0034). "
            "For an incident only: the start itself is recorded as break-glass. "
            "Unset, a broken chain stops the process from serving."
        ),
    )

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
        if bool(self.httpsms_api_key) != bool(self.httpsms_sender):
            raise SettingsInvalid(
                "HTTPSMS_API_KEY and HTTPSMS_SENDER must either both be set or both be unset"
            )
        try:
            self.linked_phone_pairs()
        except ValueError as error:
            raise SettingsInvalid(f"CLARITY_LINKED_PHONES: {error}") from error
        if self.httpsms_api_key and self.httpsms_api_key.startswith("pk_"):
            raise SettingsInvalid(
                "HTTPSMS_API_KEY is a phone-scoped pk_ key; customer OTP sending "
                "requires the primary user API key from httpSMS Settings"
            )
        return self

    def linked_phone_pairs(self) -> list[tuple[str, str]]:
        """`CLARITY_LINKED_PHONES` as (real phone, synthetic number) pairs."""
        from clarity.kernel.common import normalise_msisdn

        pairs: list[tuple[str, str]] = []
        for item in (self.linked_phones or "").split(","):
            if not item.strip():
                continue
            real, sep, synthetic = item.partition("=")
            if not sep:
                raise ValueError("each entry is real=synthetic")
            pairs.append((normalise_msisdn(real.strip()), normalise_msisdn(synthetic.strip())))
        return pairs

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
