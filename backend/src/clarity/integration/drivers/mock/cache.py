"""In-memory cache (lite profile parity with Valkey)."""

from __future__ import annotations

import time


class MockCache:
    """Process-local key/value store with optional TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, float | None]] = {}

    async def get(self, key: str) -> bytes | None:
        item = self._store.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None:
        expires_at = None if ttl_seconds is None else time.monotonic() + ttl_seconds
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
