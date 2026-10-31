"""Order persistence — orders, items, events, notes. Immutable snapshots at acceptance."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel
from modest_chic_backend.modules.orders.enums import (
    FulfillmentMethod,
    OrderSource,
    OrderState,
    PaymentMethod,
    PaymentState,
)


class Order(BaseModel):
    __tablename__ = "orders"
    __table_args__ = (
        Index("uq_order_number", "number", unique=True),
        Index("uq_order_idempotency", "checkout_idempotency_key", unique=True),
        Index("idx_order_customer", "customer_id"),
        Index("idx_order_state", "state"),
        Index("idx_order_created", "created_at"),
    )

    number: Mapped[str] = mapped_column(String(20), nullable=False)
    checkout_idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    checkout_request_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    source: Mapped[OrderSource] = mapped_column(
        Enum(OrderSource, name="order_source", native_enum=True),
        nullable=False,
        default=OrderSource.STOREFRONT,
        server_default=OrderSource.STOREFRONT.value,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    customer_name: Mapped[str | None] = mapped_column(String(255))
    customer_phone: Mapped[str | None] = mapped_column(String(30))
    customer_email: Mapped[str | None] = mapped_column(String(255))
    fulfillment_method: Mapped[FulfillmentMethod] = mapped_column(
        Enum(FulfillmentMethod, name="fulfillment_method", native_enum=True),
        nullable=False,
    )
    address_line1: Mapped[str | None] = mapped_column(String(500))
    address_line2: Mapped[str | None] = mapped_column(String(500))
    address_area: Mapped[str | None] = mapped_column(String(255))
    address_city: Mapped[str | None] = mapped_column(String(255))
    address_postal_code: Mapped[str | None] = mapped_column(String(20))
    address_country_code: Mapped[str | None] = mapped_column(CHAR(2), default="PK")
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    subtotal_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_minor: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    shipping_charge_minor: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="PKR", server_default="PKR"
    )
    state: Mapped[OrderState] = mapped_column(
        Enum(OrderState, name="order_state", native_enum=True),
        nullable=False,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", native_enum=True),
        nullable=False,
    )
    payment_state: Mapped[PaymentState] = mapped_column(
        Enum(PaymentState, name="payment_state", native_enum=True),
        nullable=False,
        default=PaymentState.PENDING,
        server_default=PaymentState.PENDING.value,
    )
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("policy_versions.id")
    )
    attribution_source: Mapped[str | None] = mapped_column(String(100))
    attribution_campaign: Mapped[str | None] = mapped_column(String(255))
    attribution_creator_code: Mapped[str | None] = mapped_column(String(100))
    order_placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderItem(BaseModel):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_item_quantity"),
        CheckConstraint("fulfilled_quantity <= quantity", name="chk_fulfilled"),
        CheckConstraint("returned_quantity <= quantity", name="chk_returned"),
        Index("idx_item_order", "order_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_title: Mapped[str] = mapped_column(String(500), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    color_name: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    sale_price_minor: Mapped[int | None] = mapped_column(Integer)
    discount_allocated_minor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="PKR", server_default="PKR"
    )
    fulfilled_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    returned_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )


class OrderPolicyAcceptance(BaseModel):
    """Record each immutable policy version accepted for an order."""

    __tablename__ = "order_policy_acceptances"
    __table_args__ = (
        UniqueConstraint("order_id", "policy_type", name="uq_order_policy_type"),
        Index("idx_order_policy_order", "order_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("policy_versions.id", ondelete="RESTRICT"), nullable=False
    )
    policy_type: Mapped[str] = mapped_column(String(100), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class OrderEvent(BaseModel):
    __tablename__ = "order_events"
    __table_args__ = (
        Index("idx_event_order", "order_id", "effective_at", "id"),
        Index("idx_event_type", "event_type"),
        Index("idx_event_time", "effective_at", "id"),
        Index(
            "idx_event_dedupe",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_state: Mapped[OrderState | None] = mapped_column(
        Enum(OrderState, name="order_state", native_enum=True),
    )
    new_state: Mapped[OrderState | None] = mapped_column(
        Enum(OrderState, name="order_state", native_enum=True),
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_users.id"),
    )
    event_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class OrderNote(BaseModel):
    __tablename__ = "order_notes"
    __table_args__ = (Index("idx_note_order", "order_id"),)

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_type: Mapped[str] = mapped_column(String(50), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_users.id"),
    )
    note_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="INTERNAL",
        server_default="INTERNAL",
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


__all__ = ["Order", "OrderEvent", "OrderItem", "OrderNote", "OrderPolicyAcceptance"]
