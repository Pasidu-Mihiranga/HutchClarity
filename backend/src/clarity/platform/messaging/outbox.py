"""Transactional outbox, relay and consumer framework."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from clarity.kernel.common import utc_now
from clarity.kernel.events import Event, EventType
from clarity.platform.db.session import Base


class OutboxRow(Base):
    __tablename__ = "outbox"
    __table_args__ = {"schema": "platform"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    causation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessedEvent(Base):
    __tablename__ = "processed_event"
    __table_args__ = {"schema": "platform"}

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    consumer: Mapped[str] = mapped_column(String(128), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeadLetter(Base):
    __tablename__ = "dead_letter"
    __table_args__ = {"schema": "platform"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    consumer: Mapped[str] = mapped_column(String(128), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Outbox:
    """Write events in the same transaction as state changes."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def publish(self, event: Event) -> None:
        row = OutboxRow(
            id=event.id,
            event_type=event.type.value,
            subject=event.subject,
            payload_json=event.model_dump_json(),
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            created_at=utc_now(),
            published_at=None,
        )
        self._session.add(row)

    async def unpublished(self, *, limit: int = 100) -> list[OutboxRow]:
        stmt = (
            select(OutboxRow)
            .where(OutboxRow.published_at.is_(None))
            .order_by(OutboxRow.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_published(self, row_id: str) -> None:
        stmt = select(OutboxRow).where(OutboxRow.id == row_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        row.published_at = utc_now()


class InMemoryBus:
    """Lite-profile in-process event bus (parity with Kafka in full)."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Any]] = {}
        self._published: list[Event] = []

    def subscribe(self, event_type: EventType, handler: Any) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Event) -> None:
        self._published.append(event)
        for handler in self._handlers.get(event.type, []):
            await handler(event) if _is_coro(handler) else handler(event)

    @property
    def published(self) -> list[Event]:
        return list(self._published)


def _is_coro(fn: Any) -> bool:
    import asyncio

    return asyncio.iscoroutinefunction(fn)


class ConsumerGuard:
    """Idempotent consumer via processed_event; DLQ on repeated failure."""

    def __init__(self, session: Any, *, consumer: str) -> None:
        self._session = session
        self._consumer = consumer

    async def already_processed(self, event_id: str) -> bool:
        stmt = select(ProcessedEvent).where(
            ProcessedEvent.event_id == event_id,
            ProcessedEvent.consumer == self._consumer,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def mark_processed(self, event_id: str) -> None:
        self._session.add(
            ProcessedEvent(
                event_id=event_id,
                consumer=self._consumer,
                processed_at=utc_now(),
            )
        )

    async def dead_letter(self, event_id: str, *, error: str, payload: dict[str, Any]) -> None:
        self._session.add(
            DeadLetter(
                id=str(uuid4()),
                event_id=event_id,
                consumer=self._consumer,
                error=error,
                payload_json=json.dumps(payload),
                created_at=utc_now(),
            )
        )
