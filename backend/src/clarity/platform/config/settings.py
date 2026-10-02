"""Application settings. Refuse to start if invalid."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Profile(StrEnum):
    LITE = "lite"
    FULL = "full"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    clarity_profile: Profile = Profile.LITE
    database_url: str = Field(
        default="postgresql+psycopg://clarity:clarity@localhost:5432/clarity",
        alias="DATABASE_URL",
    )
    subscriber_hmac_key: str = Field(
        default="clarity-demo-subscriber-key-not-a-secret",
        alias="SUBSCRIBER_HMAC_KEY",
    )
    signing_key_path: Path = Field(
        default=Path(".keys/signing.pem"),
        alias="SIGNING_KEY_PATH",
    )
    verify_base: str = Field(default="http://localhost:8000/v", alias="VERIFY_BASE")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    openai_compatible_base: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_compatible_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    ai_cassette_dir: Path = Field(default=Path("cassettes"), alias="AI_CASSETTE_DIR")
    ai_prefer_templates: bool = Field(default=True, alias="AI_PREFER_TEMPLATES")
    otel_exporter: str = Field(default="console", alias="OTEL_EXPORTER")
    keys_dir: Path = Field(default=Path(".keys"), alias="KEYS_DIR")

    @field_validator("database_url")
    @classmethod
    def _no_sqlite_in_lite(cls, value: str) -> str:
        # Plan: Postgres in every profile. SQLite is refused for the new tree.
        if value.startswith("sqlite"):
            raise ValueError(
                "DATABASE_URL must be PostgreSQL (lite/full/prod). "
                "SQLite is not allowed for schema-per-module + RLS + pgvector."
            )
        return value

    @property
    def profile(self) -> Profile:
        return self.clarity_profile

    @property
    def subscriber_key_bytes(self) -> bytes:
        return self.subscriber_hmac_key.encode("utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def reset_settings() -> None:
    get_settings.cache_clear()
