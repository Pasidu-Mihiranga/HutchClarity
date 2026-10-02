"""OpenBao Transit driver for the receipt signing port.

Only public keys cross back into the application. The private Ed25519 key is
created, rotated and used inside the Transit engine. The driver also works
against a compatible Vault/KMS gateway that exposes the same endpoints.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx


class SignerUnavailable(RuntimeError):
    """The remote signer failed or returned an invalid response."""


class OpenBaoSigningService:
    """SigningService backed by OpenBao's versioned Transit Ed25519 key."""

    def __init__(
        self,
        base_url: str,
        *,
        key_name: str,
        token: str,
        mount: str = "transit",
        namespace: str | None = None,
        timeout_seconds: float = 3.0,
        client: httpx.Client | None = None,
    ) -> None:
        headers = {"X-Vault-Token": token}
        if namespace:
            headers["X-Vault-Namespace"] = namespace
        self._client = client or httpx.Client(headers=headers, timeout=timeout_seconds)
        if client is not None:
            self._client.headers.update(headers)
        self._base_url = base_url.rstrip("/")
        self._mount = mount.strip("/")
        self._key_name = key_name
        self._active_version: int | None = None
        self._public: dict[str, str] = {}

    @property
    def active_kid(self) -> str:
        if self._active_version is None:
            self._refresh_public_keys()
        if self._active_version is None:  # pragma: no cover - guarded by refresh
            raise SignerUnavailable("OpenBao returned no active signing key")
        return self._kid(self._active_version)

    def sign(self, payload_hash: str) -> tuple[str, str]:
        encoded = base64.b64encode(payload_hash.encode("utf-8")).decode("ascii")
        try:
            response = self._client.post(
                f"{self._base_url}/v1/{self._mount}/sign/{self._key_name}",
                json={"input": encoded},
            )
            response.raise_for_status()
            signature = response.json()["data"]["signature"]
            prefix, version, value = signature.split(":", 2)
            if prefix != "vault" or not version.startswith("v") or not value:
                raise ValueError("invalid Transit signature")
            self._active_version = int(version[1:])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise SignerUnavailable("OpenBao could not sign the receipt hash") from error
        return self._kid(self._active_version), value

    def public_keys(self) -> dict[str, str]:
        self._refresh_public_keys()
        return dict(self._public)

    def _refresh_public_keys(self) -> None:
        try:
            response = self._client.get(
                f"{self._base_url}/v1/{self._mount}/export/public-key/{self._key_name}",
                params={"format": "raw"},
            )
            response.raise_for_status()
            payload: Any = response.json()
            keys = payload["data"]["keys"]
            if not isinstance(keys, dict) or not keys:
                raise ValueError("no public keys")
            parsed = {int(version): self._raw_public(value) for version, value in keys.items()}
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise SignerUnavailable("OpenBao did not publish its signing keys") from error
        self._public = {self._kid(version): value for version, value in parsed.items()}
        self._active_version = max(parsed)

    def _kid(self, version: int) -> str:
        return f"{self._key_name}:v{version}"

    @staticmethod
    def _raw_public(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("public key is not a string")
        raw = base64.b64decode(value, validate=True)
        if len(raw) != 32:
            raise ValueError("public key is not raw Ed25519 material")
        return base64.b64encode(raw).decode("ascii")


__all__ = ["OpenBaoSigningService", "SignerUnavailable"]
