"""Inventory persistence — locations, balances, reservations, movements.

All entities inherit :class:`BaseModel` for standard audit columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel
from modest_chic_backend.modules.inventory.enums import MovementReason, ReservationStatus


class InventoryLocation(BaseModel):
    """A physical or logical stock location."""

    __tablename__ = "inventory_locations"
    __table_args__ = (Index("uq_location_key", "key", unique=True),)

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class InventoryBalance(BaseModel):
    """Variant-level stock at a location with optimistic concurrency."""

    __tablename__ = "inventory_balances"
    __table_args__ = (
        CheckConstraint("on_hand >= 0", name="chk_on_hand_nonnegative"),
        CheckConstraint("reserved >= 0", name="chk_reserved_nonnegative"),
        CheckConstraint("reserved <= on_hand", name="chk_reserved_lte_on_hand"),
        Index("uq_balance_variant_loc", "variant_id", "location_id", unique=True),
        Index("idx_balance_variant", "variant_id"),
        Index("idx_balance_location", "location_id"),
        CheckConstraint(
            "low_stock_threshold IS NULL OR low_stock_threshold >= 0",
            name="chk_low_stock_threshold_nonnegative",
        ),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    on_hand: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    reserved: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class InventoryReservation(BaseModel):
    """A quantity temporarily committed to an order item."""

    __tablename__ = "inventory_reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_reservation_quantity_positive"),
        Index("idx_res_status", "status"),
        Index("idx_res_expiry", "expires_at", postgresql_where=text("status = 'ACTIVE'")),
        Index("idx_res_item", "order_item_id"),
    )

    balance_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_balances.id", ondelete="RESTRICT"), nullable=False
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status", native_enum=True),
        nullable=False,
        default=ReservationStatus.ACTIVE,
        server_default=ReservationStatus.ACTIVE.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InventoryMovement(BaseModel):
    """Immutable append-only stock change ledger."""

    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index("idx_mvmt_variant", "variant_id"),
        Index("idx_mvmt_location", "location_id"),
        Index("idx_mvmt_created", "created_at"),
        Index("idx_mvmt_order", "order_id", postgresql_where=text("order_id IS NOT NULL")),
        Index(
            "idx_mvmt_dedupe",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    delta_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_reserved: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    reason: Mapped[MovementReason] = mapped_column(
        Enum(MovementReason, name="movement_reason", native_enum=True), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    return_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reference_type: Mapped[str | None] = mapped_column(String(100))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id")
    )
    notes: Mapped[str | None] = mapped_column(Text)


__all__ = [
    "InventoryBalance",
    "InventoryLocation",
    "InventoryMovement",
    "InventoryReservation",
]
