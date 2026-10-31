"""Policy version persistence model — immutable approved business policy evidence."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel


class PolicyVersion(BaseModel):
    """An immutable approved policy text with an effective date for a specific type.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.

    ``approved_by`` remains a separate field because it records the
    specific staff member who published this version — distinct from
    the generic ``created_by`` audit column (though they will usually
    be the same).
    """

    __tablename__ = "policy_versions"
    __table_args__ = (
        CheckConstraint("length(trim(type)) > 0", name="chk_policy_type_not_blank"),
        Index("uq_policy_type_version", "type", "version", unique=True),
        Index("idx_policy_type_effective", "type", "effective_from"),
    )

    type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text("1")
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id")
    )


__all__ = ["PolicyVersion"]
