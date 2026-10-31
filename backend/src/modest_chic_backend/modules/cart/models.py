"""Guest cart persistence — browser-bound cart with versioned item lines.

Inherits :class:`BaseModel` for audit columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modest_chic_backend.db.base import BaseModel


class Cart(BaseModel):
    """One browser-bound guest cart identified by a hashed guest token.

    Version increments on every item mutation for optimistic concurrency.
    """

    __tablename__ = "carts"
    __table_args__ = (
        Index("uq_cart_token", "guest_token_hash", unique=True),
        Index("idx_cart_expiry", "expires_at"),
    )

    guest_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="PKR", server_default="PKR"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(BaseModel):
    """A line in a guest cart — one variant at a requested quantity.

    Price is NOT stored here — totals are computed from current catalog prices.
    """

    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_cart_item_quantity_positive"),
        Index("uq_cart_variant", "cart_id", "variant_id", unique=True),
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")


__all__ = ["Cart", "CartItem"]
