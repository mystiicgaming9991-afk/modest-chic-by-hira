"""Notifications."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel


class Notification(BaseModel):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notif_recipient", "recipient_type", "recipient_id"),
        Index("idx_notif_status", "status"),
    )
    recipient_type: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["Notification"]
