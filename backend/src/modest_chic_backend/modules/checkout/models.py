"""Order access token — private guest credential for order tracking."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel


class OrderAccessToken(BaseModel):
    """A scoped guest credential bound to one order."""

    __tablename__ = "order_access_tokens"
    __table_args__ = (
        Index("uq_access_token", "token_hash", unique=True),
        Index("idx_at_order", "order_id"),
        Index("idx_at_expiry", "expires_at", postgresql_where="revoked_at IS NULL"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="order.read return.create review.create",
        server_default="order.read return.create review.create",
    )
    replay_ciphertext: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    replay_key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def allows(self, action: str) -> bool:
        """Return whether this active credential was granted the named action scope."""
        return action in self.scope.split()


__all__ = ["OrderAccessToken"]
