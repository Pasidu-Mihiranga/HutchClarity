"""Canonical JSON serialization and hashing (plan §15.2).

Evidence snapshots and Trust Receipts are hashed, chained and signed, so two
parties must be able to reproduce byte-identical bytes from the same data.
This module provides that canonical form.

**Scope of this implementation.** It is an RFC 8785 (JCS) compatible *subset*,
sufficient because Clarity's canonical payloads never contain floating-point
numbers (money is a decimal string, see :data:`clarity.schemas.common.Money`)
and every object key is ASCII:

- object keys sorted by code point (identical to JCS's UTF-16 order for ASCII);
- no insignificant whitespace;
- UTF-8 output, no ``\\uXXXX`` escaping of non-ASCII;
- integers serialized without a decimal point.

Floats are rejected rather than silently serialized, because JCS number
formatting rules are not implemented here. Production should swap in a full
JCS library; the interface stays the same.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

__all__ = ["canonical_bytes", "canonical_json", "chain_hash", "hash_payload", "sha256_hex"]


def _normalise(value: Any) -> Any:
    """Convert domain values into JSON-safe primitives, deterministically."""
    if isinstance(value, bool) or value is None or isinstance(value, str | int):
        # bool first: bool is a subclass of int.
        return value
    if isinstance(value, float):
        raise TypeError(
            "floats are not allowed in canonical payloads; "
            "use Decimal/str for money and measurements"
        )
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite Decimal cannot be canonicalized")
        # Money and other decimals travel as strings so the exact scale survives.
        return format(value, "f")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime cannot be canonicalized")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, list | tuple):
        return [_normalise(v) for v in value]
    if hasattr(value, "model_dump"):  # pydantic BaseModel
        return _normalise(value.model_dump(mode="json"))
    raise TypeError(f"cannot canonicalize value of type {type(value).__name__}")


def canonical_json(payload: Any) -> str:
    """Return the canonical JSON text for ``payload``."""
    return json.dumps(
        _normalise(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(payload: Any) -> bytes:
    """Return the canonical UTF-8 bytes that get hashed and signed."""
    return canonical_json(payload).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Prefixed SHA-256 digest, e.g. ``sha256:9a1f...``."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def hash_payload(payload: Any) -> str:
    """Canonical hash of a domain object or dict."""
    return sha256_hex(canonical_bytes(payload))


def chain_hash(payload_hash: str, previous_hash: str | None) -> str:
    """Link a record to its predecessor (plan §15.2, §20.3).

    ``previous_hash`` is ``None`` only for the first record in a chain, which
    is bound to the constant ``genesis`` so an empty chain cannot be forged by
    presenting a single record as the head.
    """
    prev = previous_hash or "genesis"
    return sha256_hex(f"{prev}\n{payload_hash}".encode())
