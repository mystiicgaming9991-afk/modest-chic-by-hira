"""Security audit persistence models."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel


class AuditLog(BaseModel):
    """A redacted record of a security-relevant staff action or outcome.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.

    Audit rows are append-only; ``updated_by`` and ``deleted_at``
    will never be set in normal operation.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_actor", "actor_id"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_corr", "correlation_id"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
