"""Transactional claiming and completion of durable outbox events."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.outbox.models import OutboxEvent


class OutboxRepository:
    """Claim and update outbox rows using PostgreSQL row-level locks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_next(self, lease_seconds: int = 60) -> OutboxEvent | None:
        """Lock one due event with SKIP LOCKED and claim it for a bounded lease."""
        now = datetime.now(UTC)
        statement = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status.in_(("PENDING", "RETRY", "PROCESSING")),
                OutboxEvent.next_attempt_at <= now,
            )
            .where((OutboxEvent.lease_until.is_(None)) | (OutboxEvent.lease_until <= now))
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        event = await self._session.scalar(statement)
        if event is None:
            return None
        event.status = "PROCESSING"
        event.attempts += 1
        event.lease_until = now + timedelta(seconds=lease_seconds)
        await self._session.flush()
        return event

    async def mark_sent(self, event: OutboxEvent) -> None:
        """Persist successful delivery and release the event lease."""
        event.status = "SENT"
        event.processed_at = datetime.now(UTC)
        event.lease_until = None
        await self._session.flush()

    async def mark_failed(self, event: OutboxEvent, max_attempts: int = 10) -> None:
        """Schedule bounded exponential retry or mark the event terminally failed."""
        event.lease_until = None
        if event.attempts >= max_attempts:
            event.status = "FAILED"
        else:
            event.status = "RETRY"
            delay_seconds = min(3600, 2 ** min(event.attempts, 10))
            event.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        await self._session.flush()

    async def get(self, event_id: uuid.UUID) -> OutboxEvent | None:
        """Load an outbox event by its stable identifier."""
        return await self._session.get(OutboxEvent, event_id)
