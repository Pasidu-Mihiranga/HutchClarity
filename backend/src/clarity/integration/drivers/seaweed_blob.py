"""SeaweedFS blob driver (full profile) via S3-compatible HTTP API.

Without ``httpx`` or a live SeaweedFS, falls back to an in-process store so
imports succeed. Live path is gated by ``CLEARITY_FULL`` / ``CLARITY_FULL``.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote


def _httpx_available() -> bool:
    try:
        import httpx  # noqa: F401
    except ImportError:
        return False
    return True


class SeaweedBlobStore:
    """Full-profile blob store. Same surface as ``MockBlobStore``."""

    def __init__(self, *, master_url: str | None = None) -> None:
        self.master_url = (master_url or os.getenv("CLARITY_SEAWEED_MASTER", "http://localhost:9333")).rstrip(
            "/"
        )
        self._fallback: dict[str, tuple[bytes, str]] = {}
        self._use_seaweed = _httpx_available() and os.getenv(
            "CLEARITY_FULL", os.getenv("CLARITY_FULL", "")
        ) == "1"

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        if not self._use_seaweed:
            self._fallback[key] = (data, content_type)
            return key
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            assign = await client.get(f"{self.master_url}/dir/assign")
            assign.raise_for_status()
            info: dict[str, Any] = assign.json()
            fid = info["fid"]
            url = f"http://{info['url']}/{fid}"
            upload = await client.post(
                url,
                content=data,
                headers={"Content-Type": content_type},
                params={"filename": quote(key, safe="")},
            )
            upload.raise_for_status()
            self._fallback[key] = (data, content_type)  # keep locator map for get
            # Store remote locator alongside key for get
            self._fallback[f"__loc__{key}"] = (url.encode("utf-8"), "text/plain")
            return url

    async def get(self, key: str) -> bytes:
        if key not in self._fallback and not self._use_seaweed:
            raise KeyError(key)
        if not self._use_seaweed:
            return self._fallback[key][0]
        loc = self._fallback.get(f"__loc__{key}")
        if loc is None:
            if key in self._fallback:
                return self._fallback[key][0]
            raise KeyError(key)
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(loc[0].decode("utf-8"))
            resp.raise_for_status()
            return resp.content

    async def delete(self, key: str) -> None:
        self._fallback.pop(key, None)
        self._fallback.pop(f"__loc__{key}", None)
