"""Declarative base class and standard audit-column mixin."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Share metadata across feature-specific database models."""


class BaseModel(Base):
    """Mixin that adds an immutable UUID PK and standard audit columns.

    Every commerce table should inherit from this class so that every
    row carries creation identity, last-modification identity, and a
    soft-delete marker.  The mixin itself extends ``Base``, so a model
    that subclasses ``BaseModel`` does not also need to subclass
    ``Base`` directly.

    Attributes:
        id: Stable, randomly generated primary key (server-side gen).
        created_at: Immutable creation timestamp (server-side default).
        created_by: The staff user who created the row, if known.
        updated_at: Last-modification timestamp, updated automatically.
        updated_by: The staff user who last modified the row, if known.
        deleted_at: Soft-delete marker; ``NULL`` means the row is live.
        deleted_by: The staff user who soft-deleted the row, if known.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id"), nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id"), nullable=True
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id"), nullable=True
    )


__all__ = ["Base", "BaseModel"]
