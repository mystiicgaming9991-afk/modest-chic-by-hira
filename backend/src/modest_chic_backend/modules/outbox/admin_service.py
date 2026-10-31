"""Permission-scoped operational views of durable email delivery jobs."""

from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only
from sqlalchemy.sql.elements import ColumnElement

from modest_chic_backend.modules.outbox.models import OutboxEvent

OutboxStatus = Literal["PENDING", "RETRY", "PROCESSING", "SENT", "FAILED"]


class OutboxAdminService:
    """Read delivery status without exposing message payloads or recipients."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_events(
        self,
        *,
        status: OutboxStatus | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        """Return one bounded status page and its matching total count."""
        filters: list[ColumnElement[bool]] = [OutboxEvent.deleted_at.is_(None)]
        if status is not None:
            filters.append(OutboxEvent.status == status)

        total_count = await self._session.scalar(
            select(func.count()).select_from(OutboxEvent).where(*filters)
        )
        rows = (
            await self._session.scalars(
                select(OutboxEvent)
                .options(
                    load_only(
                        OutboxEvent.id,
                        OutboxEvent.event_type,
                        OutboxEvent.aggregate_type,
                        OutboxEvent.status,
                        OutboxEvent.attempts,
                        OutboxEvent.created_at,
                        OutboxEvent.processed_at,
                        OutboxEvent.next_attempt_at,
                    )
                )
                .where(*filters)
                .order_by(OutboxEvent.created_at.desc(), OutboxEvent.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return {
            "items": [_outbox_event_read(event) for event in rows],
            "total_count": total_count or 0,
            "limit": limit,
            "offset": offset,
        }


def _outbox_event_read(event: OutboxEvent) -> dict[str, object]:
    """Build an allow-listed status record without recipient or payload data."""
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "status": event.status,
        "attempts": event.attempts,
        "created_at": event.created_at,
        "processed_at": event.processed_at,
        "next_attempt_at": event.next_attempt_at,
    }
