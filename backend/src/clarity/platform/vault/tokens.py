"""PII token vault — MSISDN never enters domain models."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from clarity.kernel.common import normalise_msisdn, subscriber_ref


@dataclass
class TokenVault:
    """Maps opaque tokens ↔ PII. Domain code only ever sees tokens / refs."""

    hmac_key: bytes
    _forward: dict[str, str] = field(default_factory=dict)
    _reverse: dict[str, str] = field(default_factory=dict)

    def tokenise_msisdn(self, msisdn: str) -> tuple[str, str]:
        """Return (token, subscriber_ref)."""
        normalised = normalise_msisdn(msisdn)
        ref = subscriber_ref(normalised, key=self.hmac_key)
        if normalised in self._reverse:
            return self._reverse[normalised], ref
        token = f"tok_{secrets.token_hex(16)}"
        self._forward[token] = normalised
        self._reverse[normalised] = token
        return token, ref

    def reveal(self, token: str) -> str | None:
        return self._forward.get(token)

    def ref_for(self, msisdn: str) -> str:
        return subscriber_ref(normalise_msisdn(msisdn), key=self.hmac_key)
