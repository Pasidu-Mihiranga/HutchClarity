"""Cache port — lite in-memory / full Valkey share this surface."""

from __future__ import annotations

from typing import Protocol


class CachePort(Protocol):
    async def get(self, key: str) -> bytes | None:
        """Return value or ``None`` if missing / expired."""

    async def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None:
        """Store ``value`` under ``key``, optional TTL in seconds."""

    async def delete(self, key: str) -> None:
        """Remove ``key`` (no-op if absent)."""
