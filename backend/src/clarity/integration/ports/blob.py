"""Blob store port — lite local folder / full SeaweedFS share this surface."""

from __future__ import annotations

from typing import Protocol


class BlobPort(Protocol):
    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Store ``data`` and return a locator (key or URL)."""

    async def get(self, key: str) -> bytes:
        """Fetch object bytes; raise ``KeyError`` if missing."""

    async def delete(self, key: str) -> None:
        """Delete object (no-op if absent)."""
