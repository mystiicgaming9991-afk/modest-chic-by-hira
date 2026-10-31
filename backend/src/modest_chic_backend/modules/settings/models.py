"""Store setting persistence model — versioned key-value configuration with secrecy flag."""

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel


class StoreSetting(BaseModel):
    """A named, versioned business configuration value with optional secrecy.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.
    """

    __tablename__ = "store_settings"
    __table_args__ = (
        CheckConstraint("length(trim(key)) > 0", name="chk_setting_key_not_blank"),
        Index("uq_setting_key", "key", unique=True),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_secret: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text("1")
    )


__all__ = ["StoreSetting"]
