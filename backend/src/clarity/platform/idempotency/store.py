"""HTTP Idempotency-Key store."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from clarity.kernel.common import utc_now
from clarity.platform.db.session import Base


class IdempotencyRecord(Base):
    __tablename__ = "idempotency"
    __table_args__ = {"schema": "platform"}

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def request_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


class IdempotencyStore:
    def __init__(self, session: Any) -> None:
        self._session = session

    async def get(self, *, key: str, scope: str) -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.key == key,
            IdempotencyRecord.scope == scope,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def put(
        self,
        *,
        key: str,
        scope: str,
        request_hash_value: str,
        response: Any,
        status_code: int,
    ) -> None:
        existing = await self.get(key=key, scope=scope)
        if existing is not None:
            if existing.request_hash != request_hash_value:
                raise ValueError("Idempotency-Key reused with a different payload")
            return
        self._session.add(
            IdempotencyRecord(
                key=key,
                scope=scope,
                request_hash=request_hash_value,
                response_json=json.dumps(response, default=str),
                status_code=status_code,
                created_at=utc_now(),
            )
        )


# In-memory store for lite unit tests without Postgres
class MemoryIdempotencyStore:
    def __init__(self) -> None:
        import threading

        self._store: dict[tuple[str, str], dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, *, key: str, scope: str) -> dict[str, Any] | None:
        with self._lock:
            return self._store.get((key, scope))

    def put(
        self,
        *,
        key: str,
        scope: str,
        request_hash_value: str,
        response: Any,
        status_code: int,
    ) -> dict[str, Any]:
        with self._lock:
            existing = self._store.get((key, scope))
            if existing is not None:
                if existing["request_hash"] != request_hash_value:
                    raise ValueError("Idempotency-Key reused with a different payload")
                return existing
            record = {
                "request_hash": request_hash_value,
                "response": response,
                "status_code": status_code,
            }
            self._store[(key, scope)] = record
            return record
