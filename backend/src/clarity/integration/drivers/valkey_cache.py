"""Valkey cache driver (full profile).

Uses ``redis`` / ``valkey`` asyncio client when available. Without the client,
stores values in process memory so the module imports cleanly; parity tests
skip the live path unless ``CLEARITY_FULL=1`` / ``CLARITY_FULL=1``.
"""

from __future__ import annotations

import os
import time
from typing import Any


def _redis_available() -> bool:
    try:
        import redis.asyncio  # noqa: F401
    except ImportError:
        return False
    return True


class ValkeyCache:
    """Full-profile cache. Same surface as ``MockCache``."""

    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or os.getenv("CLARITY_VALKEY_URL", "redis://localhost:6379/0")
        self._client: Any = None
        self._fallback: dict[str, tuple[bytes, float | None]] = {}
        self._use_valkey = _redis_available() and os.getenv(
            "CLEARITY_FULL", os.getenv("CLARITY_FULL", "")
        ) == "1"

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from redis.asyncio import from_url

        self._client = from_url(self.url, decode_responses=False)
        return self._client

    async def get(self, key: str) -> bytes | None:
        if self._use_valkey:
            client = await self._ensure_client()
            value = await client.get(key)
            return value if value is None or isinstance(value, bytes) else bytes(value)
        item = self._fallback.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and time.monotonic() >= expires_at:
            del self._fallback[key]
            return None
        return value

    async def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None:
        if self._use_valkey:
            client = await self._ensure_client()
            if ttl_seconds is None:
                await client.set(key, value)
            else:
                await client.set(key, value, ex=ttl_seconds)
            return
        expires_at = None if ttl_seconds is None else time.monotonic() + ttl_seconds
        self._fallback[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        if self._use_valkey:
            client = await self._ensure_client()
            await client.delete(key)
            return
        self._fallback.pop(key, None)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
