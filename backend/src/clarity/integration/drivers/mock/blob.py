"""Local in-memory blob store (lite profile parity with SeaweedFS)."""

from __future__ import annotations


class MockBlobStore:
    """Dict-backed object store for the lite profile."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        self._objects[key] = (data, content_type)
        return key

    async def get(self, key: str) -> bytes:
        if key not in self._objects:
            raise KeyError(key)
        return self._objects[key][0]

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)
