"""Payment enums and persistence."""

import enum
import uuid

from sqlalchemy import (
    CHAR,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel


class PaymentProvider(enum.StrEnum):
    COD = "COD"
    PICKUP = "PICKUP"
    MANUAL = "MANUAL"


class PaymentEventType(enum.StrEnum):
    INITIATED = "INITIATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Payment(BaseModel):
    __tablename__ = "payments"
    __table_args__ = (Index("idx_payment_order", "order_id"),)

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="PKR")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    provider_txn_id: Mapped[str | None] = mapped_column(String(255))
    payment_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))


class PaymentEvent(BaseModel):
    __tablename__ = "payment_events"
    __table_args__ = (
        Index("idx_pevent_payment", "payment_id"),
        Index(
            "idx_pevent_dedupe",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_response: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))


__all__ = ["Payment", "PaymentEvent"]
