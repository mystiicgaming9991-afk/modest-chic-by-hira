"""Fulfillment — shipments, shipment items, shipment events, pickups."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class Shipment(BaseModel):
    __tablename__ = "shipments"
    __table_args__ = (
        Index("idx_shipment_order", "order_id"),
        Index(
            "uq_shipment_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "uq_shipment_merchant_reference",
            "merchant_reference",
            unique=True,
            postgresql_where=text("merchant_reference IS NOT NULL"),
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    courier: Mapped[str | None] = mapped_column(String(100))
    tracking_number: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    merchant_reference: Mapped[str | None] = mapped_column(String(100))


class ShipmentItem(BaseModel):
    __tablename__ = "shipment_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_shipitem_qty"),
        Index("idx_shipitem_shipment", "shipment_id"),
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class ShipmentEvent(BaseModel):
    __tablename__ = "shipment_events"
    __table_args__ = (Index("idx_sevent_shipment", "shipment_id"),)

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)


class Pickup(BaseModel):
    __tablename__ = "pickups"
    __table_args__ = (Index("idx_pickup_order", "order_id"),)

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["Pickup", "Shipment", "ShipmentEvent", "ShipmentItem"]
