"""Ed25519 signing for Trust Receipts (deck S6, plan §15.2).

The signature is what makes a receipt checkable by someone who does not trust
us — a customer, an agent on 1788, or TRCSL. Only receipts we actually issued
will verify, so a forged PDF fails.

**Prototype note.** :class:`DevSigningService` holds a key in memory or in a
local file. That is fine for a demo and **not** how this runs in production:
plan §15.2 puts the private key in an HSM or KMS, with annual rotation and old
public keys retained so historic receipts keep verifying. The interface here is
deliberately the one a KMS-backed implementation would expose, so swapping it
changes no caller.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Protocol, runtime_checkable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


@runtime_checkable
class SigningService(Protocol):
    """What the receipt service needs from a signer."""

    @property
    def active_kid(self) -> str: ...

    def sign(self, payload_hash: str) -> tuple[str, str]:
        """Return ``(kid, base64 signature)`` over ``payload_hash``."""

    def public_keys(self) -> dict[str, str]:
        """All known key ids to base64 public keys, including retired ones."""


class UnknownKeyId(KeyError):
    """A receipt names a key we do not publish, so it cannot be verified."""


class DevSigningService:
    """Development signer. Never use for real customer receipts."""

    def __init__(self, *, kid: str = "clarity-dev-2027-01", key_path: Path | None = None) -> None:
        self._kid = kid
        self._private = self._load_or_create(key_path)
        self._public: dict[str, Ed25519PublicKey] = {kid: self._private.public_key()}

    @staticmethod
    def _load_or_create(key_path: Path | None) -> Ed25519PrivateKey:
        if key_path is None:
            return Ed25519PrivateKey.generate()
        if key_path.exists():
            loaded = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            if not isinstance(loaded, Ed25519PrivateKey):
                raise TypeError(f"{key_path} does not hold an Ed25519 private key")
            return loaded

        private = Ed25519PrivateKey.generate()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(
            private.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        key_path.chmod(0o600)
        return private

    @property
    def active_kid(self) -> str:
        return self._kid

    def sign(self, payload_hash: str) -> tuple[str, str]:
        signature = self._private.sign(payload_hash.encode("utf-8"))
        return self._kid, base64.b64encode(signature).decode("ascii")

    def public_keys(self) -> dict[str, str]:
        """Served at ``/.well-known/clarity-keys.json`` in production."""
        return {
            kid: base64.b64encode(
                key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode("ascii")
            for kid, key in self._public.items()
        }


def verify_signature(
    payload_hash: str, *, kid: str, signature_b64: str, public_keys: dict[str, str]
) -> bool:
    """Check a receipt signature against a published public key.

    Takes only public material, so a verifier — including one outside HUTCH —
    can run exactly this with nothing secret.
    """
    encoded = public_keys.get(kid)
    if encoded is None:
        raise UnknownKeyId(kid)

    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))
    try:
        public.verify(base64.b64decode(signature_b64), payload_hash.encode("utf-8"))
    except (InvalidSignature, ValueError):
        return False
    return True
