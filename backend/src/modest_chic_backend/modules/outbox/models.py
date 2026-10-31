"""Durable notification and integration event persistence models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel


class OutboxEvent(BaseModel):
    """An at-least-once delivery job persisted with its owning state change.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.

    Outbox rows are typically created by automated processes, so
    ``created_by`` will be ``NULL`` for system-generated events.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("idx_outbox_pending", "status", "next_attempt_at"),
        Index("idx_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING", server_default="PENDING"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
