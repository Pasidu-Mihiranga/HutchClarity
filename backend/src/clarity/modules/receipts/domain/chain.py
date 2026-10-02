"""Ed25519 hash-chained Trust Receipts.

Uses cryptography Ed25519 when available; otherwise falls back to an
HMAC-SHA256 stub so lite unit tests still run without the native wheel.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
from dataclasses import dataclass, field
from typing import Any

from clarity.kernel.common import utc_now
from clarity.kernel.ids import receipt_id as make_receipt_id

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover - cryptography is a declared dependency
    _HAS_CRYPTO = False


def _canonical_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class SignedReceipt:
    receipt_id: str
    payload: dict[str, Any]
    payload_hash: str
    prev_hash: str
    chain_hash: str
    kid: str
    signature_b64: str
    issued_at: str
    html: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "id": self.receipt_id,
            "payload": self.payload,
            "payload_hash": self.payload_hash,
            "prev_hash": self.prev_hash,
            "chain_hash": self.chain_hash,
            "kid": self.kid,
            "signature": self.signature_b64,
            "issued_at": self.issued_at,
            "html": self.html,
        }


@dataclass
class ReceiptChain:
    """Append-only hash-chained receipts with Ed25519 (or HMAC stub) signatures."""

    kid: str = "clarity-dev-2026"
    _private: Any = field(default=None, repr=False)
    _public_raw: bytes | None = field(default=None, repr=False)
    _hmac_key: bytes = field(default=b"clarity-hmac-dev-key", repr=False)
    _receipts: dict[str, SignedReceipt] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)
    _last_chain_hash: str = "0" * 64
    _sequence: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if _HAS_CRYPTO:
            self._private = Ed25519PrivateKey.generate()
            self._public_raw = self._private.public_key().public_bytes_raw()
        # else: HMAC-SHA256 stub — cryptography unavailable

    def public_keys(self) -> dict[str, str]:
        if _HAS_CRYPTO and self._public_raw is not None:
            return {self.kid: base64.b64encode(self._public_raw).decode("ascii")}
        # Stub mode exposes the HMAC key id only (not the secret).
        return {self.kid: "hmac-sha256-stub"}

    def issue(self, payload: dict[str, Any], *, html: str | None = None) -> SignedReceipt:
        with self._lock:
            self._sequence += 1
            year = utc_now().year
            rid = make_receipt_id(self._sequence, year=year)
            issued_at = utc_now().isoformat()
            body = {**payload, "receipt_id": rid, "issued_at": issued_at}
            payload_hash = _canonical_hash(body)
            prev = self._last_chain_hash
            chain_hash = hashlib.sha256(f"{prev}{payload_hash}".encode()).hexdigest()
            kid, signature = self._sign(payload_hash)
            receipt = SignedReceipt(
                receipt_id=rid,
                payload=body,
                payload_hash=payload_hash,
                prev_hash=prev,
                chain_hash=chain_hash,
                kid=kid,
                signature_b64=signature,
                issued_at=issued_at,
                html=html,
            )
            self._receipts[rid] = receipt
            self._order.append(rid)
            self._last_chain_hash = chain_hash
            return receipt

    def get(self, receipt_id: str) -> SignedReceipt | None:
        with self._lock:
            return self._receipts.get(receipt_id)

    def verify(self, receipt_id: str) -> dict[str, Any]:
        with self._lock:
            receipt = self._receipts.get(receipt_id)
            if receipt is None:
                return {
                    "receipt_id": receipt_id,
                    "valid": False,
                    "reason": "not_found",
                    "display": "NOT VALID",
                }

            sig_ok = self._verify_sig(receipt.payload_hash, receipt.kid, receipt.signature_b64)
            chain_ok = self._verify_chain_up_to(receipt_id)
            valid = sig_ok and chain_ok
            return {
                "receipt_id": receipt_id,
                "valid": valid,
                "reason": "ok" if valid else ("bad_signature" if not sig_ok else "chain_broken"),
                "kid": receipt.kid,
                "chain_ok": chain_ok,
                "display": "VERIFIED" if valid else "NOT VALID",
            }

    def replay(self, receipt_id: str) -> dict[str, Any]:
        """Return stored receipt + verification (read-only replay)."""
        receipt = self.get(receipt_id)
        if receipt is None:
            raise KeyError(receipt_id)
        verification = self.verify(receipt_id)
        return {"receipt": receipt.to_dict(), "verification": verification}

    def clear(self) -> None:
        with self._lock:
            self._receipts.clear()
            self._order.clear()
            self._last_chain_hash = "0" * 64
            self._sequence = 0

    def _sign(self, payload_hash: str) -> tuple[str, str]:
        if _HAS_CRYPTO and self._private is not None:
            signature = self._private.sign(payload_hash.encode("utf-8"))
            return self.kid, base64.b64encode(signature).decode("ascii")
        # HMAC-SHA256 stub when cryptography is not installed.
        digest = hmac.new(self._hmac_key, payload_hash.encode("utf-8"), hashlib.sha256).digest()
        return self.kid, base64.b64encode(digest).decode("ascii")

    def _verify_sig(self, payload_hash: str, kid: str, signature_b64: str) -> bool:
        if kid != self.kid:
            return False
        try:
            raw = base64.b64decode(signature_b64)
        except Exception:
            return False
        if _HAS_CRYPTO and self._public_raw is not None:
            try:
                public = Ed25519PublicKey.from_public_bytes(self._public_raw)
                public.verify(raw, payload_hash.encode("utf-8"))
                return True
            except Exception:
                return False
        expected = hmac.new(
            self._hmac_key, payload_hash.encode("utf-8"), hashlib.sha256
        ).digest()
        return hmac.compare_digest(expected, raw)

    def _verify_chain_up_to(self, receipt_id: str) -> bool:
        prev = "0" * 64
        for rid in self._order:
            receipt = self._receipts[rid]
            if receipt.prev_hash != prev:
                return False
            expected = hashlib.sha256(
                f"{receipt.prev_hash}{receipt.payload_hash}".encode()
            ).hexdigest()
            if expected != receipt.chain_hash:
                return False
            prev = receipt.chain_hash
            if rid == receipt_id:
                return True
        return False

